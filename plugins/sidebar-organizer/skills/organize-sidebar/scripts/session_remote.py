"""Single-host SSH transport; requires only OpenSSH, a remote POSIX shell and Codex."""
from __future__ import annotations

import json
import math
import os
from pathlib import PurePosixPath
import re
import shlex
import subprocess
import unicodedata


class RemoteError(ValueError):
    """The SSH endpoint or its remote Codex home could not be used."""


def _text(value, label):
    if (not isinstance(value, str) or not value.strip()
            or any(unicodedata.category(c).startswith("C") or c in "\u2028\u2029" for c in value)):
        raise RemoteError(f"{label} must be nonempty text without control characters.")
    return value


def _absolute_path(value, label):
    value = _text(value, label)
    if not PurePosixPath(value).is_absolute():
        raise RemoteError(f"{label} must be an absolute path on the remote machine.")
    return value


def _safe_error(value):
    return "".join(c if not unicodedata.category(c).startswith("C") else " "
                   for c in str(value)[:1000])


class RemoteHost:
    def __init__(self, host, codex="codex", config=(), home=None, timeout=15, control_path=None):
        if (not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_.@:%\[\]-]+", host)
                or host.startswith("-") or host.count("@") > 1):
            raise RemoteError("SSH host must be a host alias or [user@]hostname, without options or whitespace.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise RemoteError("SSH timeout must be a positive finite number.")
        self.host, self.timeout = host, timeout
        self.codex = _text(codex, "Remote Codex executable")
        if self.codex.startswith("-") or ("/" in self.codex and not self.codex.startswith("/")):
            raise RemoteError("Remote Codex executable must be a command name or an absolute remote path.")
        if isinstance(config, (str, bytes)):
            raise RemoteError("Codex configuration overrides must be a sequence of strings.")
        self.config = tuple(_text(value, "Codex configuration override") for value in config)
        self._requested_home = _absolute_path(home, "Remote Codex home") if home is not None else None
        self.control_path = _text(os.fspath(control_path), "SSH control socket") if control_path is not None else None
        self.home = self.scope = None

    def _ssh(self, mode):
        argv = ["ssh", mode, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                "-o", "RemoteCommand=none", "-o", "SessionType=default",
                "-o", f"ConnectTimeout={max(1, math.ceil(self.timeout))}"]
        if self.control_path is not None:
            argv.extend(["-S", self.control_path])
        return argv + ["--", self.host]

    def _run(self, argv, action):
        # Do not let a configured SendEnv copy the local Codex home to this host.
        env = dict(os.environ)
        env.pop("CODEX_HOME", None)
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, encoding="utf-8", timeout=self.timeout, env=env)
        except subprocess.TimeoutExpired:
            raise RemoteError(f"SSH {action} timed out.") from None
        except (OSError, UnicodeError) as exc:
            raise RemoteError("Cannot run SSH: " + _safe_error(exc)) from None
        if result.returncode:
            detail = _safe_error(result.stderr).strip()
            raise RemoteError(f"SSH {action} failed (exit {result.returncode})"
                              + (": " + detail if detail else "."))
        return result.stdout

    @staticmethod
    def _shell(script):
        # OpenSSH sends a single command string through the remote login shell.
        # All dynamic arguments inside the POSIX script are quoted separately.
        return "exec sh -c " + shlex.quote(script)

    def resolve(self):
        if self.scope is not None:
            return self
        output = self._run(self._ssh("-G"), "configuration lookup")
        endpoint = {}
        for line in output.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2 or parts[0] not in {"hostname", "user", "port"}:
                continue
            key, value = parts
            if key in endpoint:
                raise RemoteError("SSH configuration contains duplicate endpoint fields.")
            endpoint[key] = _text(value, "SSH endpoint " + key)
        if set(endpoint) != {"hostname", "user", "port"}:
            raise RemoteError("SSH configuration is missing hostname, user or port.")
        port = endpoint["port"]
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise RemoteError("SSH configuration has an invalid port.")
        endpoint["port"] = int(port)
        endpoint["hostname"] = endpoint["hostname"].lower()
        home = shlex.quote(self._requested_home) if self._requested_home is not None else '${CODEX_HOME:-"$HOME/.codex"}'
        script = ('set -eu\norganizer_home=' + home
                  + '\ncase "$organizer_home" in /*) ;; *) organizer_home="$PWD/$organizer_home" ;; esac'
                  + '\ncd "$organizer_home"'
                  + '\nprintf \'codex-organizer-home-v1\\n%s\\n\' "$(pwd -P)"')
        output = self._run(self._ssh("-T") + [self._shell(script)], "Codex home lookup")
        lines = output.split("\n")
        if len(lines) != 3 or lines[0] != "codex-organizer-home-v1" or lines[2] != "":
            raise RemoteError("SSH home lookup returned unexpected output; remote shell startup must keep stdout clean.")
        resolved_home = _absolute_path(lines[1], "Resolved remote Codex home")
        self.home = resolved_home
        self.scope = "ssh:" + json.dumps({**endpoint, "home": resolved_home}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return self

    def _codex_command(self, arguments):
        self.resolve()
        argv = [self.codex]
        for value in self.config:
            argv.extend(["-c", value])
        argv.extend(arguments)
        setup = "export CODEX_HOME=" + shlex.quote(self.home) + "; "
        if self.codex.startswith("/"):
            # npm/nvm launchers need their sibling Node runtime on noninteractive SSH PATH.
            setup += "export PATH=" + shlex.quote(str(PurePosixPath(self.codex).parent)) + ':"${PATH:-}"; '
        return setup + "exec " + shlex.join(argv)

    def app_server_argv(self):
        script = self._codex_command(["app-server", "--listen", "stdio://"])
        return self._ssh("-T") + [self._shell(script)]

    @staticmethod
    def _cwd_check(cwd):
        cwd = _absolute_path(cwd, "Session working directory")
        return ("test -d " + shlex.quote(cwd)
                + " || { printf '%s\\n' 'Remote session working directory is unavailable.' >&2; exit 1; }")

    def validate_cwd(self, cwd):
        self.resolve()
        self._run(self._ssh("-T") + [self._shell(self._cwd_check(cwd))], "working directory check")

    def resume_argv(self, cwd, session_id):
        _text(session_id, "Session ID")
        if session_id.startswith("-") or any(c.isspace() for c in session_id):
            raise RemoteError("Session ID cannot contain whitespace or start with '-'.")
        script = (self._cwd_check(cwd) + "; cd " + shlex.quote(cwd) + " || exit 1; "
                  + self._codex_command(["resume", "--all", session_id]))
        return self._ssh("-t") + [self._shell(script)]
