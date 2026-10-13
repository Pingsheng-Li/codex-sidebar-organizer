"""CLI group persistence tests use synthetic IDs and temporary directories only."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sidebar-organizer/skills/organize-sidebar/scripts/session_groups.py"
spec = importlib.util.spec_from_file_location("session_groups", SCRIPT)
groups = importlib.util.module_from_spec(spec)
spec.loader.exec_module(groups)


class GroupStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private" / "groups.json"
        self.store = groups.GroupStore(self.path, "/example/codex-home")

    def test_missing_store_is_empty_without_creating_files(self):
        self.assertEqual(self.store.groups(), {})
        self.assertIsNone(self.store.group_for("thread-1"))
        self.assertFalse(self.path.parent.exists())

    def test_groups_persist_and_return_independent_values(self):
        self.store.assign("论文 工作", ["thread-1", "thread-2"])
        reloaded = groups.GroupStore(self.path, "/example/codex-home")
        self.assertEqual(reloaded.groups(), {"论文 工作": ["thread-1", "thread-2"]})
        self.assertEqual(reloaded.group_for("thread-2"), "论文 工作")
        result = reloaded.groups()
        result["论文 工作"].append("local-only")
        self.assertEqual(reloaded.groups(), {"论文 工作": ["thread-1", "thread-2"]})
        self.assertEqual(json.loads(self.path.read_text()), {
            "schemaVersion": 1,
            "scopes": {"/example/codex-home": {"论文 工作": ["thread-1", "thread-2"]}},
        })

    def test_reassignment_is_exclusive_and_idempotent(self):
        self.store.assign("first", ["thread-1", "thread-2"])
        self.store.assign("second", ["thread-1", "thread-1"])
        before = self.path.read_bytes()
        self.store.assign("second", ["thread-1"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.groups(), {"first": ["thread-2"], "second": ["thread-1"]})

    def test_unassign_preserves_empty_groups(self):
        self.store.assign("keep", ["thread-1"])
        self.store.unassign(["thread-1", "unknown"])
        self.assertEqual(self.store.groups(), {"keep": []})
        self.assertIsNone(self.store.group_for("thread-1"))

    def test_remove_only_removes_named_group(self):
        self.store.assign("remove", ["thread-1"])
        self.store.assign("keep", ["thread-2"])
        self.store.remove("remove")
        self.store.remove("missing")
        self.assertEqual(self.store.groups(), {"keep": ["thread-2"]})

    def test_updates_preserve_other_scopes(self):
        other = groups.GroupStore(self.path, "/other/codex-home")
        other.assign("other", ["thread-1"])
        self.store.assign("here", ["thread-1"])
        self.store.unassign(["thread-1"])
        self.store.remove("here")
        self.assertEqual(other.groups(), {"other": ["thread-1"]})

    def test_unicode_group_names_are_exact_not_normalized(self):
        self.store.assign("é", ["thread-1"])
        self.store.assign("e\u0301", ["thread-2"])
        self.assertEqual(self.store.groups(), {"é": ["thread-1"], "e\u0301": ["thread-2"]})

    def test_invalid_input_never_modifies_existing_store(self):
        self.store.assign("safe", ["thread-1"])
        before = self.path.read_bytes()
        for name in ["", "  ", "bad\nname", "bad\x1bname", "bad\u202ename"]:
            with self.subTest(name=repr(name)), self.assertRaises(groups.GroupError):
                self.store.assign(name, ["thread-2"])
        for thread_id in ["", " ", "bad id", "bad\n", "bad\x1b", "-flag", "bad\u200b"]:
            with self.subTest(thread_id=repr(thread_id)), self.assertRaises(groups.GroupError):
                self.store.assign("next", ["thread-2", thread_id])
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_store_is_rejected_without_overwriting(self):
        invalid = [
            "broken json", "[]", '{"schemaVersion":2,"scopes":{}}',
            '{"schemaVersion":true,"scopes":{}}',
            '{"schemaVersion":1,"scopes":[]}',
            '{"schemaVersion":1,"scopes":{"other":{"g":"thread-1"}}}',
            '{"schemaVersion":1,"scopes":{"other":{"g":["thread-1","thread-1"]}}}',
            '{"schemaVersion":1,"scopes":{"other":{"g":["thread-1"],"h":["thread-1"]}}}',
            '{"schemaVersion":1,"scopes":{},"extra":"preserve me"}',
            '{"schemaVersion":1,"scopes":{},"scopes":{}}',
        ]
        self.path.parent.mkdir()
        for content in invalid:
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(groups.GroupError):
                    self.store.assign("new", ["thread-2"])
                self.assertEqual(self.path.read_text(), content)
                self.assertFalse(self.path.with_name("groups.json.lock").exists())

    def test_lock_contention_fails_without_removing_other_lock(self):
        self.store.assign("before", ["thread-1"])
        before = self.path.read_bytes()
        lock = self.path.with_name("groups.json.lock")
        lock.mkdir()
        with self.assertRaisesRegex(groups.GroupError, "lock"):
            self.store.assign("after", ["thread-2"])
        self.assertTrue(lock.exists())
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_atomic_replace_preserves_store_and_releases_lock(self):
        self.store.assign("before", ["thread-1"])
        before = self.path.read_bytes()
        with mock.patch.object(groups.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(groups.GroupError):
                self.store.assign("after", ["thread-2"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["groups.json"])
        self.store.assign("after", ["thread-2"])
        self.assertEqual(self.store.group_for("thread-2"), "after")

    @unittest.skipIf(os.name == "nt", "POSIX modes are not supported on Windows")
    def test_new_directory_and_store_are_private(self):
        nested = Path(self.temp.name) / "a" / "b" / "groups.json"
        groups.GroupStore(nested, "/scope").assign("g", ["thread-1"])
        self.assertEqual(stat.S_IMODE(nested.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(nested.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(nested.parent.parent.stat().st_mode), 0o700)

    @unittest.skipIf(os.name == "nt", "POSIX modes are not supported on Windows")
    def test_existing_parent_permissions_are_unchanged(self):
        self.path.parent.mkdir(mode=0o755)
        self.store.assign("g", ["thread-1"])
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o755)

    def test_symlink_store_is_rejected_without_touching_target(self):
        self.path.parent.mkdir()
        target = self.path.parent / "other.json"
        target.write_text("do not change")
        try:
            self.path.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(groups.GroupError):
            self.store.assign("g", ["thread-1"])
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_text(), "do not change")


if __name__ == "__main__":
    unittest.main()
