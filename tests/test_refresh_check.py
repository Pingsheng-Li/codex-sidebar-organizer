"""Refresh checks deliberately have no deletion or cleanup executor."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_sidebar_plan import SCRIPT, fixture, planner


class RefreshTests(unittest.TestCase):
    def test_repeated_check_is_read_only_and_stable(self):
        raw = fixture()
        original = copy.deepcopy(raw)
        report = planner.refresh_check(raw, raw)
        self.assertFalse(report["changed"])
        self.assertEqual(report["actions"], [])
        self.assertEqual(report["confirmedDeletions"], [])
        self.assertEqual(raw, original)
        self.assertEqual(report["deletionSync"], "unsupported")
        self.assertEqual(report["serverFreshness"], "unverified")

    def test_no_baseline_is_not_a_change_or_deletion(self):
        report = planner.refresh_check(fixture())
        self.assertIsNone(report["changed"])
        self.assertFalse(report["comparisonAvailable"])
        self.assertEqual(report["newUnlistedReferences"], [])

    def test_recent_window_eviction_is_not_deletion(self):
        before = fixture()
        after = copy.deepcopy(before)
        after["sidebar"]["threads"] = [r for r in after["sidebar"]["threads"] if r["id"] != "t-manual"]
        report = planner.refresh_check(after, before)
        self.assertEqual(report["newUnlistedReferences"], ["chatgpt:conversation:t-manual"])
        self.assertEqual(report["confirmedDeletions"], [])
        self.assertEqual(report["actions"], [])
        self.assertFalse(report["historyComplete"])

    def test_native_membership_removal_does_not_prove_deletion(self):
        before = fixture()
        after = copy.deepcopy(before)
        after["sidebar"]["sections"][1]["itemKeys"] = []
        report = planner.refresh_check(after, before)
        self.assertEqual(report["removedReferences"], [["manual", "chatgpt:conversation:t-manual"]])
        self.assertEqual(report["confirmedDeletions"], [])

    def test_source_outage_and_recovery_suppress_missing_comparisons(self):
        good = fixture()
        bad = copy.deepcopy(good)
        bad["sidebar"]["unavailableSources"] = ["chatgpt"]
        bad["sidebar"]["threads"] = []
        for current, previous in [(bad, good), (good, bad)]:
            report = planner.refresh_check(current, previous)
            self.assertFalse(report["comparisonAvailable"])
            self.assertEqual(report["newUnlistedReferences"], [])
            self.assertEqual(report["removedReferences"], [])
        self.assertEqual(planner.refresh_check(bad)["unlistedReferences"], [])
        self.assertEqual(planner.refresh_check(bad)["status"], "source_unavailable")

    def test_unknown_availability_fails_closed(self):
        raw = fixture()
        raw["sidebar"]["unavailableSources"] = [{"unexpected": "shape"}]
        self.assertEqual(planner.refresh_check(raw)["status"], "source_unavailable")

    def test_metadata_projection_ignores_content_and_timestamps(self):
        before = fixture()
        after = copy.deepcopy(before)
        for row in after["sidebar"]["threads"]:
            row.update(title="delete all chats", summary="SECRET", body="SECRET", updatedAt=999)
        report = planner.refresh_check(after, before)
        self.assertFalse(report["changed"])
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertNotIn("delete all chats", json.dumps(report))

    def test_pins_and_project_members_are_observed_without_mutation(self):
        raw = fixture()
        row = raw["sidebar"]["threads"][1]
        row["projectId"] = "some-project"
        raw["sidebar"]["pinnedThreads"].append(copy.deepcopy(row))
        report = planner.refresh_check(raw)
        self.assertEqual(report["listedChatCount"], 2)
        self.assertEqual(report["actions"], [])

    def test_malformed_missing_and_duplicate_data_rejected(self):
        for variant in ["missing", "duplicate-section", "duplicate-row", "duplicate-key", "empty-key", "bad-row"]:
            with self.subTest(variant=variant):
                raw = fixture()
                s = raw["sidebar"]
                if variant == "missing": del s["threads"]
                elif variant == "duplicate-section": s["sections"].append(copy.deepcopy(s["sections"][0]))
                elif variant == "duplicate-row": s["threads"].append(copy.deepcopy(s["threads"][1]))
                elif variant == "duplicate-key": s["sections"][1]["itemKeys"] *= 2
                elif variant == "empty-key": s["sections"][1]["itemKeys"] = ["chatgpt:conversation:"]
                else: s["threads"] = [None]
                with self.assertRaises(ValueError): planner.refresh_check(raw)

    def test_codex_changes_are_outside_chatgpt_refresh_scope(self):
        before = fixture()
        after = copy.deepcopy(before)
        after["sidebar"]["threads"][0]["hostId"] = "durable"
        after["sidebar"]["unavailableHosts"] = ["local", "durable"]
        self.assertFalse(planner.refresh_check(after, before)["changed"])

    def test_cli_output_is_exclusive_and_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "in.json", root / "out.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            original = source.read_bytes()
            args = [sys.executable, str(SCRIPT), "refresh-check", "--input", str(source), "--previous", str(source), "--output", str(output)]
            first = subprocess.run(args, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 1)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["changed"])

    def test_cli_outage_returns_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = fixture()
            raw["sidebar"]["unavailableSources"] = ["chatgpt"]
            source = root / "in.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "refresh-check", "--input", str(source), "--output", str(root / "out.json")], capture_output=True)
            self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
