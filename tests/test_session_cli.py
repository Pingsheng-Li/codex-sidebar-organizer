import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/sidebar-organizer/skills/organize-sidebar/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("session_cli", SCRIPTS / "session_cli.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class SessionCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.file = self.directory / "private/groups.json"
        self.threads = [
            {"id": "aaaa-1111", "name": "Fix parser", "cwd": str(self.directory), "source": "cli", "updatedAt": 100},
            {"id": "aaaa-2222", "name": "Review", "cwd": str(self.directory), "source": "vscode", "updatedAt": 99},
        ]
        self.rpc = patch.object(cli, "AppServer")
        self.server_class = self.rpc.start()
        self.addCleanup(self.rpc.stop)
        self.server = self.server_class.return_value.__enter__.return_value
        self.server.list_threads.return_value = self.threads

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-file", str(self.file), *args])
        return code, out.getvalue(), err.getvalue()

    def test_list_projects_without_creating_data_file(self):
        code, out, err = self.run_cli("list")
        self.assertEqual((code, err), (0, ""))
        self.assertIn(str(self.directory) + " (2)", out)
        self.assertIn("[1] Fix parser", out)
        self.assertFalse(self.file.exists())

    def test_source_view_and_json_have_only_projected_metadata(self):
        self.threads[0].update({"preview": "PRIVATE FIRST MESSAGE", "turns": [{"text": "BODY"}]})
        code, out, _ = self.run_cli("list", "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["coverage"], "current_home_saved_sessions")
        self.assertNotIn("PRIVATE", out)
        self.assertNotIn("BODY", out)
        self.assertEqual(report["sessions"][0]["source"], "cli")
        _, out, _ = self.run_cli("list", "--group-by", "source")
        self.assertIn("cli (1)", out)
        self.assertIn("vscode (1)", out)

    def test_filters_pass_to_native_listing(self):
        code, _, _ = self.run_cli("-c", 'model_reasoning_effort="xhigh"', "list", "--source", "cli", "--cwd", str(self.directory), "--search", "Fix")
        self.assertEqual(code, 0)
        self.server_class.assert_called_once_with(codex="codex", config=['model_reasoning_effort="xhigh"'], timeout=15.0)
        self.server.list_threads.assert_called_once_with(sources=["cli"], cwd=str(self.directory.resolve()), search="Fix", index_only=False)

    def test_index_only_is_explicit_and_reported(self):
        code, out, _ = self.run_cli("--index-only", "list", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["coverage"], "current_home_state_index")
        self.assertTrue(self.server.list_threads.call_args.kwargs["index_only"])

    def test_group_workflow_and_prefix_resolution(self):
        self.assertEqual(self.run_cli("group", "add", "研究任务", "aaaa-1")[0], 0)
        code, out, _ = self.run_cli("list", "--group", "研究任务", "--json")
        self.assertEqual(code, 0)
        self.assertEqual([row["id"] for row in json.loads(out)["sessions"]], ["aaaa-1111"])
        self.assertEqual(self.run_cli("group", "add", "论文", "aaaa-1")[0], 0)
        code, out, _ = self.run_cli("group", "list")
        self.assertEqual(code, 0)
        self.assertIn("研究任务 (0)", out)
        self.assertIn("论文 (1)", out)
        self.assertEqual(self.run_cli("group", "unassign", "aaaa-1111")[0], 0)
        self.assertEqual(self.run_cli("group", "remove", "论文")[0], 0)

    def test_group_add_validates_all_ids_before_writing(self):
        code, _, err = self.run_cli("group", "add", "Work", "aaaa-1", "missing")
        self.assertEqual(code, 1)
        self.assertIn("No listed session", err)
        self.assertFalse(self.file.exists())

    def test_ambiguous_ids_and_unknown_groups_fail(self):
        code, _, err = self.run_cli("resume", "aaaa", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("Ambiguous", err)
        self.assertEqual(self.run_cli("list", "--group", "missing")[0], 1)

    def test_local_group_listing_does_not_start_server(self):
        self.assertEqual(self.run_cli("group", "list")[0], 0)
        self.server_class.assert_not_called()
        self.assertFalse(self.file.exists())

    def test_resume_dry_run_uses_exact_argv_and_original_cwd(self):
        with patch.object(cli.subprocess, "call") as call:
            code, out, _ = self.run_cli("-c", 'model_reasoning_effort="xhigh"', "resume", "aaaa-1", "--dry-run")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["argv"], ["codex", "-c", 'model_reasoning_effort="xhigh"', "resume", "--all", "aaaa-1111"])
        self.assertEqual(result["cwd"], str(self.directory))
        call.assert_not_called()

    def test_resume_rejects_missing_cwd_and_non_tty(self):
        self.threads[0]["cwd"] = str(self.directory / "gone")
        self.assertEqual(self.run_cli("resume", "aaaa-1", "--dry-run")[0], 1)
        self.threads[0]["cwd"] = str(self.directory)
        code, _, err = self.run_cli("resume", "aaaa-1")
        self.assertEqual(code, 1)
        self.assertIn("interactive terminal", err)

    def test_actual_resume_uses_argv_and_propagates_exit_code(self):
        args = cli.parser().parse_args(["resume", "aaaa-1"])
        out = io.StringIO()
        out.isatty = lambda: True
        with patch.object(cli.sys.stdin, "isatty", return_value=True), contextlib.redirect_stdout(out), patch.object(cli.subprocess, "call", return_value=7) as call:
            code = cli.resume_session(args, self.threads[0])
        self.assertEqual(code, 7)
        self.assertEqual(call.call_args.args[0], ["codex", "resume", "--all", "aaaa-1111"])
        self.assertNotIn("shell", call.call_args.kwargs)

    def test_browse_selection_matches_display_order(self):
        self.threads.append({"id": "bbbb-3333", "name": "Third", "cwd": str(self.directory), "source": "cli"})
        with patch.object(cli.sys.stdin, "isatty", return_value=True), patch.object(cli, "resume_session", return_value=0) as resume, patch("builtins.input", side_effect=["bad", "2"]):
            # redirect_stdout's StringIO is non-TTY; use a stream whose isatty reports true.
            out = io.StringIO()
            out.isatty = lambda: True
            with contextlib.redirect_stdout(out):
                result = cli.main(["--data-file", str(self.file), "browse", "--group-by", "source"])
        self.assertEqual(result, 0)
        self.assertEqual(resume.call_args.args[1]["id"], "bbbb-3333")
        self.server_class.return_value.__exit__.assert_called_once()

    def test_browse_non_tty_does_not_start_server(self):
        code, _, err = self.run_cli("browse")
        self.assertEqual(code, 1)
        self.assertIn("interactive terminal", err)
        self.server_class.assert_not_called()

    def test_terminal_control_characters_are_not_emitted(self):
        self.threads[0]["name"] = "Bad\x1b[2J\nName\u202e"
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\u202e", out)
        self.assertNotIn("\nName", out)

    def test_invalid_timeout_is_rejected(self):
        for value in ["0", "-1", "nan", "inf"]:
            self.assertEqual(self.run_cli("--timeout", value, "list")[0], 1)


if __name__ == "__main__":
    unittest.main()
