"""SSH command tests use only local fake processes and temporary fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/sidebar-organizer/skills/organize-sidebar/scripts/session_remote.py"
spec = importlib.util.spec_from_file_location("session_remote", SCRIPT)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
REAL_RUN = subprocess.run
CONFIG = "hostname example.test\nuser researcher\nport 2222\nidentityfile ~/.ssh/id_fixture\n"
POSIX_SHELL = os.name == "posix" and Path("/bin/sh").is_file()


class RemoteHostTests(unittest.TestCase):
    def result(self, output="", code=0, error=""):
        return subprocess.CompletedProcess([], code, output, error)

    def resolved(self, host="lab", home="/srv/codex", **kwargs):
        with patch.object(remote.subprocess, "run", side_effect=[self.result(CONFIG), self.result("codex-organizer-home-v1\n" + home + "\n")]):
            return remote.RemoteHost(host, **kwargs).resolve()

    def test_scope_uses_effective_endpoint_and_remote_home(self):
        first = self.resolved("lab")
        self.assertIs(first.resolve(), first)
        self.assertEqual(first.home, "/srv/codex")
        self.assertEqual(first.scope, self.resolved("lab-alias").scope)
        self.assertNotEqual(first.scope, self.resolved(home="/other/home").scope)
        scope = json.loads(first.scope.removeprefix("ssh:"))
        self.assertEqual(scope, {"hostname": "example.test", "user": "researcher", "port": 2222, "home": "/srv/codex"})
        with patch.object(remote.subprocess, "run", side_effect=[self.result(CONFIG.replace("2222", "2223")), self.result("codex-organizer-home-v1\n/srv/codex\n")]):
            self.assertNotEqual(first.scope, remote.RemoteHost("lab").resolve().scope)

    def test_rejects_host_options_controls_and_relative_explicit_paths(self):
        for host in ("", "-oProxyCommand=anything", "lab host", "lab;touch-x", "lab\n", "lab\x1b", "user@host@other"):
            with self.subTest(host=host), self.assertRaises(remote.RemoteError):
                remote.RemoteHost(host)
        for home in ("relative", "~/codex", "/bad\npath"):
            with self.subTest(home=home), self.assertRaises(remote.RemoteError):
                remote.RemoteHost("lab", home=home)
        for codex in ("", "-flag", "~/bin/codex", "./codex", "codex\n"):
            with self.subTest(codex=codex), self.assertRaises(remote.RemoteError):
                remote.RemoteHost("lab", codex=codex)
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(remote.RemoteError):
                remote.RemoteHost("lab", timeout=timeout)

    def test_probe_rejects_mixed_output_missing_config_and_unresolved_home(self):
        for output in ("/srv/codex\n", "banner\ncodex-organizer-home-v1\n/srv/codex\n", "codex-organizer-home-v1\nrelative\n", "codex-organizer-home-v1\n/srv/codex\nextra\n"):
            with self.subTest(output=output), patch.object(remote.subprocess, "run", side_effect=[self.result(CONFIG), self.result(output)]), self.assertRaises(remote.RemoteError):
                remote.RemoteHost("lab").resolve()
        for config in ("hostname x\nuser y\n", CONFIG + "port 22\n", CONFIG.replace("2222", "bad")):
            with self.subTest(config=config), patch.object(remote.subprocess, "run", return_value=self.result(config)), self.assertRaises(remote.RemoteError):
                remote.RemoteHost("lab").resolve()

    def test_ssh_auth_failure_and_timeout_are_actionable(self):
        for failure, message in ((self.result(code=255, error="Permission denied\x1b[31m"), "Permission denied"),
                                 (subprocess.TimeoutExpired("ssh", 1), "timed out"),
                                 (FileNotFoundError("ssh"), "Cannot run SSH")):
            with self.subTest(failure=failure), patch.object(remote.subprocess, "run", side_effect=[failure]), self.assertRaises(remote.RemoteError) as caught:
                remote.RemoteHost("lab").resolve()
            self.assertIn(message, str(caught.exception))
            self.assertNotIn("\x1b", str(caught.exception))

    def test_transport_options_keep_metadata_unattended_and_resume_interactive(self):
        host = self.resolved()
        listing = host.app_server_argv()
        resume = host.resume_argv("/remote/project", "id-1")
        self.assertEqual(listing[0], "ssh")
        self.assertIn("-T", listing)
        self.assertIn("-t", resume)
        for argv in (listing, resume):
            self.assertIn("BatchMode=yes", argv)
            self.assertIn("StrictHostKeyChecking=yes", argv)
            self.assertIn("RemoteCommand=none", argv)
            self.assertIn("SessionType=default", argv)
            self.assertEqual(argv[-2], "lab")
            self.assertNotIn("StrictHostKeyChecking=no", argv)

    def test_control_socket_is_reused_for_all_connections_without_changing_scope(self):
        socket = "/tmp/existing ssh/socket"
        with patch.object(remote.subprocess, "run", side_effect=[self.result(CONFIG), self.result("codex-organizer-home-v1\n/srv/codex\n")]) as run:
            host = remote.RemoteHost("lab", control_path=Path(socket)).resolve()
        for call in run.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[argv.index("-S") + 1], socket)
        for argv in (host.app_server_argv(), host.resume_argv("/remote/project", "id-1")):
            self.assertEqual(argv[argv.index("-S") + 1], socket)
        self.assertEqual(host.scope, self.resolved().scope)

    def test_local_codex_home_is_not_forwarded_to_remote_probes(self):
        with patch.dict(os.environ, {"CODEX_HOME": "/local/home"}), patch.object(remote.subprocess, "run", side_effect=[self.result(CONFIG), self.result("codex-organizer-home-v1\n/srv/codex\n")]) as run:
            remote.RemoteHost("lab").resolve()
        for call in run.call_args_list:
            self.assertNotIn("CODEX_HOME", call.kwargs["env"])

    @unittest.skipUnless(POSIX_SHELL, "requires a local POSIX shell for synthetic remote commands")
    def test_explicit_executable_can_find_sibling_runtime(self):
        with tempfile.TemporaryDirectory(prefix="remote-runtime-test-") as temp:
            directory = Path(temp)
            executable = directory / "codex"
            runtime = directory / "fixture-runtime"
            executable.write_text("#!/bin/sh\nexec fixture-runtime\n", encoding="utf-8")
            runtime.write_text("#!/bin/sh\nprintf 'runtime-found\\n'\n", encoding="utf-8")
            executable.chmod(0o700)
            runtime.chmod(0o700)
            host = self.resolved(codex=str(executable))
            result = REAL_RUN(["/bin/sh", "-c", host.app_server_argv()[-1]], capture_output=True,
                              text=True, env=dict(os.environ, PATH="/usr/bin:/bin"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "runtime-found\n")

    @unittest.skipUnless(POSIX_SHELL, "requires a local POSIX shell for synthetic remote commands")
    def test_remote_shell_receives_literal_home_cwd_config_and_session_id(self):
        with tempfile.TemporaryDirectory(prefix="session-remote-test-") as temp:
            directory = Path(temp)
            cwd = directory / "project ' $(touch INJECTED); [中文]"
            cwd.mkdir()
            fake = directory / "fake ' codex"
            fake.write_text("#!" + sys.executable + "\nimport json, os, sys\nprint(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'home': os.environ.get('CODEX_HOME')}))\n", encoding="utf-8")
            fake.chmod(0o700)
            home = "/remote/home ' $(touch INJECTED); [中文]"
            setting = 'key="$(touch INJECTED);`echo no`"'
            host = self.resolved(home=home, codex=str(fake), config=(setting,))
            sid = "id-'$(touch${IFS}INJECTED)"
            command = host.resume_argv(str(cwd), sid)[-1]
            result = REAL_RUN(["/bin/sh", "-c", command], capture_output=True, text=True, check=True, cwd=temp)
            found = json.loads(result.stdout)
            self.assertEqual(found, {"argv": ["-c", setting, "resume", "--all", sid], "cwd": str(cwd.resolve()), "home": home})
            result = REAL_RUN(["/bin/sh", "-c", host.app_server_argv()[-1]], capture_output=True, text=True, check=True, cwd=temp)
            self.assertEqual(json.loads(result.stdout)["argv"], ["-c", setting, "app-server", "--listen", "stdio://"])
            self.assertFalse((directory / "INJECTED").exists())
            self.assertFalse((cwd / "INJECTED").exists())

    @unittest.skipUnless(POSIX_SHELL, "requires a local POSIX shell for synthetic remote commands")
    def test_home_probe_uses_remote_environment_and_canonicalizes_path(self):
        with tempfile.TemporaryDirectory(prefix="remote-home-test-") as temp:
            directory = Path(temp)
            home = directory / "a ' $(touch INJECTED)"
            home.mkdir()
            alias = directory / "alias"
            alias.symlink_to(home, target_is_directory=True)
            env = dict(os.environ, CODEX_HOME=str(alias), HOME="/wrong/local/home")
            def run(argv, **kwargs):
                if "-G" in argv:
                    return self.result(CONFIG)
                return REAL_RUN(["/bin/sh", "-c", argv[-1]], capture_output=True, text=True, env=env, cwd=temp)
            with patch.object(remote.subprocess, "run", side_effect=run):
                self.assertEqual(remote.RemoteHost("lab").resolve().home, str(home.resolve()))
                self.assertEqual(remote.RemoteHost("lab", home=str(alias)).resolve().home, str(home.resolve()))
            self.assertFalse((directory / "INJECTED").exists())

    @unittest.skipUnless(POSIX_SHELL, "requires a local POSIX shell for synthetic remote commands")
    def test_home_probe_defaults_to_remote_home_and_resolves_relative_remote_env(self):
        with tempfile.TemporaryDirectory(prefix="remote-default-home-test-") as temp:
            directory = Path(temp)
            default = directory / ".codex"
            default.mkdir()
            custom = directory / "relative-codex"
            custom.mkdir()
            env = dict(os.environ, HOME=str(directory))
            env.pop("CODEX_HOME", None)
            def run(argv, **kwargs):
                if "-G" in argv:
                    return self.result(CONFIG)
                return REAL_RUN(["/bin/sh", "-c", argv[-1]], capture_output=True, text=True, env=env, cwd=temp)
            with patch.object(remote.subprocess, "run", side_effect=run):
                self.assertEqual(remote.RemoteHost("lab").resolve().home, str(default.resolve()))
                env["CODEX_HOME"] = "relative-codex"
                self.assertEqual(remote.RemoteHost("lab").resolve().home, str(custom.resolve()))

    def test_cwd_validation_happens_remotely(self):
        host = self.resolved()
        with patch.object(remote.subprocess, "run", return_value=self.result()) as run:
            host.validate_cwd("/exists-only-remotely")
        self.assertIn("/exists-only-remotely", run.call_args.args[0][-1])
        with patch.object(remote.subprocess, "run", return_value=self.result(code=1)), self.assertRaisesRegex(remote.RemoteError, "directory"):
            host.validate_cwd("/missing")
        for cwd in (None, "relative", "~/project", "/bad\npath"):
            with self.subTest(cwd=cwd), self.assertRaises(remote.RemoteError):
                host.resume_argv(cwd, "id-1")

    @unittest.skipUnless(POSIX_SHELL, "requires a local POSIX shell for synthetic remote commands")
    def test_resume_rejects_missing_remote_directory(self):
        host = self.resolved()
        result = REAL_RUN(["/bin/sh", "-c", host.resume_argv("/missing-remote-organizer-test-directory", "id-1")[-1]], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
