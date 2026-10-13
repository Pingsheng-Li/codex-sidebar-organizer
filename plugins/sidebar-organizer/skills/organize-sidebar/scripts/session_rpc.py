"""Codex metadata-listing transport. Python 3.10+, standard library only."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import unicodedata

FIELDS = ("id", "name", "cwd", "source", "createdAt", "updatedAt", "modelProvider")
DEFAULT_SOURCES = ("cli", "vscode", "exec", "appServer")


class RpcError(RuntimeError):
    """The app-server could not provide a valid metadata response."""


def safe_text(value, limit=1000):
    return "".join(c if unicodedata.category(c) not in {"Cc", "Cf", "Cs"} else " "
                   for c in str(value)[:limit])


class AppServer:
    def __init__(self, codex="codex", config=(), timeout=15.0, launch_argv=None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a finite positive number")
        self.codex, self.config, self.timeout = codex, tuple(config), timeout
        if launch_argv is not None:
            if (not isinstance(launch_argv, (list, tuple)) or not launch_argv
                    or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in launch_argv)):
                raise RpcError("Transport command must be a nonempty argv sequence without NUL characters")
            launch_argv = tuple(launch_argv)
        self.launch_argv = launch_argv
        self.process = None
        self._next_id = 0
        self._initialized = False

    def __enter__(self):
        if self.process is not None:
            raise RpcError("App-server is already running")
        self._messages = queue.Queue(maxsize=128)
        self._stop = threading.Event()
        self._stderr = b""
        child_env = dict(os.environ)
        if self.launch_argv is not None:
            argv = list(self.launch_argv)
            child_env.pop("CODEX_HOME", None)
        else:
            argv = [self.codex]
            for value in self.config:
                argv.extend(("-c", value))
            argv.extend(("app-server", "--listen", "stdio://"))
            if "CODEX_HOME" in child_env:
                child_env["CODEX_HOME"] = str(Path(child_env["CODEX_HOME"]).expanduser().resolve())
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, bufsize=0, env=child_env)
            self._readers = [threading.Thread(target=self._read_stdout, daemon=True),
                             threading.Thread(target=self._read_stderr, daemon=True)]
            for reader in self._readers:
                reader.start()
            self._call("initialize", {"clientInfo": {"name": "sidebar_organizer_cli", "version": "0.1.0"}})
            self._send({"method": "initialized"})
            self._initialized = True
            return self
        except OSError as exc:
            self.close()
            raise RpcError("Cannot start app-server: " + safe_text(exc)) from None
        except BaseException:
            self.close()
            raise

    def __exit__(self, *_):
        self.close()

    def _enqueue(self, message):
        while not self._stop.is_set():
            try:
                self._messages.put(message, timeout=0.1)
                return
            except queue.Full:
                pass

    def _read_stdout(self):
        stream = self.process.stdout
        try:
            while not self._stop.is_set():
                # Bound individual JSONL records, including malformed unterminated lines.
                line = stream.readline(8 * 1024 * 1024 + 1)
                if len(line) > 8 * 1024 * 1024:
                    self._enqueue(RpcError("App-server JSON record exceeds the size limit"))
                    return
                if not line:
                    break
                self._enqueue(line)
        except (OSError, ValueError):
            pass
        finally:
            self._enqueue(None)

    def _read_stderr(self):
        stream = self.process.stderr
        try:
            while chunk := stream.read(4096):
                self._stderr = (self._stderr + chunk)[-8192:]
        except (OSError, ValueError):
            pass

    def _failure(self, message):
        # Before initialization, stderr may explain a bad local CLI configuration.
        # Once listing starts, never forward logs that could include session content.
        detail = safe_text(self._stderr.decode("utf-8", errors="replace")) if not self._initialized else ""
        return RpcError(message + (": " + detail if detail else ""))

    def _send(self, message):
        if self.process is None:
            raise RpcError("App-server is not running; use it as a context manager")
        try:
            self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except (OSError, ValueError, UnicodeError):
            raise self._failure("App-server input pipe is unavailable") from None

    def _call(self, method, params):
        self._next_id += 1
        ident = self._next_id
        self._send({"id": ident, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._failure("App-server request timed out")
            try:
                raw = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise self._failure("App-server request timed out") from None
            if raw is None:
                try:
                    self.process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
                self._readers[1].join(timeout=0.2)
                raise self._failure(f"App-server exited or closed stdout (exit code {self.process.poll()})")
            if isinstance(raw, RpcError):
                raise raw
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError):
                raise RpcError("App-server returned invalid JSON") from None
            if not isinstance(message, dict):
                raise RpcError("App-server returned an invalid RPC envelope")
            if "method" in message:
                if "id" in message:
                    self._send({"id": message["id"], "error": {"code": -32601,
                                "message": "Server requests are unsupported by this metadata-listing client"}})
                    raise RpcError("Server request refused by metadata-listing client")
                continue
            if type(message.get("id")) is not int or message["id"] != ident:
                continue
            if "error" in message:
                error = message["error"]
                detail = safe_text(error.get("message", "unspecified error")) if isinstance(error, dict) else "invalid error"
                raise RpcError("App-server RPC error: " + detail)
            if not isinstance(message.get("result"), dict):
                raise RpcError("App-server returned an invalid result object")
            return message["result"]

    def request(self, method, params):
        if method != "thread/list":
            raise RpcError("Only thread/list is allowed by this metadata-listing client")
        if not self._initialized:
            raise RpcError("App-server is not initialized")
        if not isinstance(params, dict):
            raise RpcError("thread/list params must be an object")
        try:
            return self._call(method, params)
        except BaseException:
            self.close()
            raise

    def list_threads(self, *, sources=None, cwd=None, search=None, index_only=False):
        # Normal native listing can scan rollouts and repair the host's index.
        params = {"limit": 100, "sortKey": "updated_at", "sortDirection": "desc", "archived": False, "modelProviders": [],
                  "useStateDbOnly": index_only, "sourceKinds": list(DEFAULT_SOURCES if sources is None else sources)}
        if cwd is not None:
            params["cwd"] = cwd
        if search is not None:
            params["searchTerm"] = search
        rows, ids, cursors = [], set(), set()
        while True:
            result = self.request("thread/list", params)
            if not isinstance(result.get("data"), list):
                raise RpcError("thread/list requires a data array")
            for row in result["data"]:
                ident = row.get("id") if isinstance(row, dict) else None
                if (not isinstance(ident, str) or not ident.strip() or ident != ident.strip()
                        or ident.startswith("-") or safe_text(ident, len(ident)) != ident):
                    raise RpcError("thread/list returned an invalid session ID")
                if ident in ids:
                    raise RpcError("thread/list returned duplicate session IDs; retry with a fresh list")
                ids.add(ident)
                rows.append({key: row[key] for key in FIELDS if key in row})
            cursor = result.get("nextCursor")
            if cursor is None:
                return rows
            if not isinstance(cursor, str) or not cursor.strip():
                raise RpcError("thread/list returned an invalid nextCursor")
            if cursor in cursors:
                raise RpcError("thread/list pagination cursor repeated")
            cursors.add(cursor)
            params["cursor"] = cursor

    def close(self):
        process = self.process
        if process is None:
            return
        self._stop.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        for reader in getattr(self, "_readers", []):
            reader.join(timeout=0.5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        self.process = None
        self._initialized = False
