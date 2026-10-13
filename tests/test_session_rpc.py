"""Synthetic subprocess tests: no real Codex server or account data."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/sidebar-organizer/skills/organize-sidebar/scripts/session_rpc.py"
spec = importlib.util.spec_from_file_location("session_rpc", SCRIPT)
rpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpc)
REAL_POPEN = subprocess.Popen
FAKE = r'''
import json, sys, time
from pathlib import Path
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
scenario = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
log = Path(sys.argv[2])
def read():
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    with log.open("a", encoding="utf-8") as out:
        out.write(line)
    return json.loads(line)
def send(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)
if scenario.get("startup"):
    sys.stderr.write(scenario["startup"])
    sys.stderr.flush()
    sys.exit(7)
request = read()
assert request["method"] == "initialize"
assert request["params"]["clientInfo"]["name"]
send({"id": request["id"], "result": {"userAgent": "synthetic"}})
assert read() == {"method": "initialized"}
for response in scenario.get("responses", []):
    request = read()
    assert request["method"] == "thread/list"
    if response.get("stderr"):
        sys.stderr.write("private-body " * 10000)
        sys.stderr.flush()
    if response.get("notify"):
        send({"method": "unrelated", "params": {"body": "SECRET"}})
        send({"id": "unrelated", "result": {"body": "SECRET"}})
    if response.get("sleep"):
        time.sleep(30)
    if response.get("exit"):
        sys.exit(9)
    if response.get("server_request"):
        send({"id": "server-1", "method": "item/commandExecution/requestApproval", "params": {"body": "SECRET"}})
        read()
        continue
    if "raw" in response:
        print(response["raw"], flush=True)
        continue
    send({"id": request["id"], **{k: v for k, v in response.items() if k in ("result", "error")}})
while True:
    read()
'''


class AppServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="session-rpc-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.fake = self.directory / "fake server.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.scenario = self.directory / "scenario.json"
        self.log = self.directory / "requests.jsonl"
        self.processes, self.argv, self.environments = [], [], []

    def start(self, responses=(), **scenario):
        self.scenario.write_text(json.dumps({"responses": responses, **scenario}), encoding="utf-8")
        def launch(argv, **kwargs):
            self.argv.append(argv)
            self.environments.append(kwargs.get("env"))
            child = REAL_POPEN([sys.executable, "-u", str(self.fake), str(self.scenario), str(self.log), *argv], **kwargs)
            self.processes.append(child)
            return child
        patcher = patch.object(rpc.subprocess, "Popen", side_effect=launch)
        patcher.start()
        self.addCleanup(patcher.stop)
        return rpc.AppServer(codex="path with spaces/codex", config=('model_reasoning_effort="xhigh"', 'key="$(touch nope);`echo no`"'), timeout=1)

    def requests(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_handshake_pagination_projection_unicode_and_safe_argv(self):
        rows = [{"id": "id-一", "name": "中文", "cwd": "/项目", "source": "cli", "createdAt": 1, "updatedAt": 2,
                 "modelProvider": "openai", "preview": "SECRET", "turns": [{"text": "SECRET"}], "unknown": "SECRET"}]
        server = self.start([{"notify": True, "stderr": True, "result": {"data": rows, "nextCursor": "next"}},
                             {"result": {"data": [{"id": "id-二", "source": "vscode"}], "nextCursor": None}}])
        with server:
            found = server.list_threads(cwd="/项目", search="中文")
        self.assertEqual(found[0], {key: rows[0][key] for key in ("id", "name", "cwd", "source", "createdAt", "updatedAt", "modelProvider")})
        self.assertEqual(len(found), 2)
        requests = self.requests()
        params = requests[2]["params"]
        self.assertEqual(params, {"limit": 100, "sortKey": "updated_at", "sortDirection": "desc", "archived": False, "modelProviders": [],
                                  "useStateDbOnly": False, "sourceKinds": ["cli", "vscode", "exec", "appServer"],
                                  "cwd": "/项目", "searchTerm": "中文"})
        self.assertEqual(requests[3]["params"]["cursor"], "next")
        self.assertEqual(self.argv[0], ["path with spaces/codex", "-c", 'model_reasoning_effort="xhigh"',
                                      "-c", 'key="$(touch nope);`echo no`"', "app-server", "--listen", "stdio://"])
        self.assertIsNotNone(self.processes[0].poll())

    def test_custom_sources_and_no_unauthorized_methods(self):
        with self.start([{"result": {"data": [], "nextCursor": None}}]) as server:
            self.assertEqual(server.list_threads(sources=["exec"]), [])
            with self.assertRaises(rpc.RpcError):
                server.request("thread/start", {})
        self.assertEqual(self.requests()[2]["params"]["sourceKinds"], ["exec"])

    def test_explicit_index_only_disables_native_rollout_scan(self):
        with self.start([{"result": {"data": []}}]) as server:
            server.list_threads(index_only=True)
        self.assertTrue(self.requests()[2]["params"]["useStateDbOnly"])

    def test_codex_home_is_absolute_for_tilde_and_relative_paths(self):
        for configured in ("~/session-fixture", "relative-session-fixture"):
            with self.subTest(configured=configured), patch.dict(os.environ, {"CODEX_HOME": configured}):
                with self.start() as server:
                    self.assertEqual(self.environments[-1]["CODEX_HOME"], str(Path(configured).expanduser().resolve()))
                    self.assertEqual(os.environ["CODEX_HOME"], configured)

    def test_explicit_transport_reuses_rpc_without_forwarding_local_codex_home(self):
        self.start([{"result": {"data": [{"id": "remote-session", "source": "cli"}]}}])
        argv = ["ssh", "-T", "lab", "exec remote-codex app-server --listen stdio://"]
        with patch.dict(os.environ, {"CODEX_HOME": "~/local-only"}):
            with rpc.AppServer(launch_argv=argv, timeout=1) as server:
                self.assertEqual(server.list_threads(), [{"id": "remote-session", "source": "cli"}])
            self.assertNotIn("CODEX_HOME", self.environments[-1])
            self.assertEqual(os.environ["CODEX_HOME"], "~/local-only")
        self.assertEqual(self.argv[-1], argv)
        self.assertIsNotNone(self.processes[-1].poll())

    def test_invalid_transport_argv_is_rejected(self):
        for argv in ([], "ssh lab", [""], ["ssh", "bad\x00"]):
            with self.subTest(argv=argv), self.assertRaises(rpc.RpcError):
                rpc.AppServer(launch_argv=argv)

    def test_rpc_error_is_bounded_sanitized_and_excludes_error_data(self):
        with self.start([{"error": {"code": -32602, "message": "invalid \x1b[31multra\x00 setting", "data": "SECRET"}}]) as server:
            with self.assertRaises(rpc.RpcError) as caught:
                server.list_threads()
        self.assertIn("ultra", str(caught.exception))
        self.assertNotIn("\x1b", str(caught.exception))
        self.assertNotIn("\x00", str(caught.exception))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_startup_config_error_is_preserved(self):
        with self.assertRaises(rpc.RpcError) as caught:
            with self.start(startup="invalid model_reasoning_effort: unknown variant `ultra`\n"):
                pass
        self.assertIn("ultra", str(caught.exception))
        self.assertIsNotNone(self.processes[0].poll())

    def test_timeout_early_exit_and_invalid_json_clean_up(self):
        for response, word in [({"sleep": True}, "timed out"), ({"exit": True}, "exited"), ({"raw": "SECRET not json"}, "JSON")]:
            with self.subTest(response=response):
                with self.assertRaises(rpc.RpcError) as caught:
                    with self.start([response]) as server:
                        server.timeout = 0.15
                        server.list_threads()
                self.assertIn(word, str(caught.exception))
                self.assertNotIn("SECRET", str(caught.exception))
                self.assertIsNotNone(self.processes[-1].poll())

    def test_server_request_is_rejected_without_execution(self):
        with self.assertRaisesRegex(rpc.RpcError, "Server request"):
            with self.start([{"server_request": True}]) as server:
                server.list_threads()
        self.assertIsNotNone(self.processes[0].poll())

    def test_invalid_pages_ids_duplicates_and_cursors_rejected(self):
        bad = [{}, {"data": {}}, {"data": [], "nextCursor": 4}, {"data": [{}]},
               *[{"data": [{"id": value}]} for value in ("", " ", "-flag", "bad\n", "bad\x1b")],
               {"data": [{"id": "same"}, {"id": "same"}]}]
        for result in bad:
            with self.subTest(result=result), self.assertRaises(rpc.RpcError):
                with self.start([{"result": result}]) as server:
                    server.list_threads()
        for responses in ([{"data": [{"id": "same"}], "nextCursor": "a"}, {"data": [{"id": "same"}]}],
                          [{"data": [], "nextCursor": "a"}, {"data": [], "nextCursor": "a"}]):
            with self.assertRaises(rpc.RpcError):
                with self.start([{"result": result} for result in responses]) as server:
                    server.list_threads()


if __name__ == "__main__":
    unittest.main()
