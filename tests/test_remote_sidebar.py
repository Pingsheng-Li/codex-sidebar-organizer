"""Synthetic desktop host-section plans; no SSH or native desktop writes."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_sidebar_plan import fixture, planner, SCRIPT, simulate


def remote_fixture(hosts=("machine-a",)):
    snapshot = fixture()
    for host in hosts:
        snapshot["projects"]["projects"].append({
            "projectId": "project-" + host, "projectKind": "remote", "hostId": host,
            "hostDisplayName": "Workstation", "path": "/example/research",
        })
        snapshot["sidebar"]["sections"][2]["itemKeys"].append("codex:project:project-" + host)
        for ident, project in (("free-", None), ("member-", "project-" + host)):
            snapshot["sidebar"]["threads"].append({
                "id": ident + host, "kind": "codex", "hostId": host, "projectId": project,
            })
            snapshot["sidebar"]["sections"][3]["itemKeys"].append(f"codex:thread:{host}:{ident}{host}")
    return snapshot


def apply_host_plan(snapshot, plan):
    after = simulate(snapshot, plan)
    after["sidebar"]["sidebarPreferences"] = copy.deepcopy(snapshot["sidebar"]["sidebarPreferences"])
    return after


class RemoteHostPlanTests(unittest.TestCase):
    def test_top_level_section_contains_projects_and_loose_chats(self):
        before = remote_fixture()
        second = copy.deepcopy(before["projects"]["projects"][-1])
        second.update(projectId="second-project", path="/example/other")
        before["projects"]["projects"].append(second)
        before["sidebar"]["sections"][2]["itemKeys"].append("codex:project:second-project")
        original = copy.deepcopy(before)
        plan = planner.build_plan(before, "en", remote_layout="host")
        self.assertEqual(plan["schemaVersion"], 4)
        self.assertEqual((plan["remoteLayout"], plan["hostIds"]), ("host", ["machine-a"]))
        self.assertEqual(plan["sorting"], {})
        self.assertEqual(plan["targets"], [{
            "name": "Remote · Workstation [machine-a]", "sectionId": None, "state": "create",
        }])
        self.assertEqual({move["key"] for move in plan["moves"]}, {
            "codex:project:project-machine-a", "codex:project:second-project",
            "codex:thread:machine-a:free-machine-a",
        })
        after = apply_host_plan(before, plan)
        section = next(row for row in after["sidebar"]["sections"] if row["name"].startswith("Remote ·"))
        self.assertEqual(set(section["itemKeys"]), {move["key"] for move in plan["moves"]})
        self.assertEqual(after["projects"], before["projects"])
        self.assertEqual(after["sidebar"]["threads"], before["sidebar"]["threads"])
        self.assertEqual(before, original)

    def test_each_native_host_gets_its_own_section_even_with_same_name_and_path(self):
        plan = planner.build_plan(remote_fixture(("machine-a", "machine-b")), remote_layout="host")
        self.assertEqual([target["name"] for target in plan["targets"]], [
            "远程 · Workstation [machine-a]", "远程 · Workstation [machine-b]",
        ])
        chats = {move["hostId"]: move for move in plan["moves"] if move["entity"] == "chat"}
        self.assertEqual(set(chats), {"machine-a", "machine-b"})
        self.assertNotEqual(chats["machine-a"]["targetName"], chats["machine-b"]["targetName"])

    def test_selected_host_leaves_other_sources_and_hosts_outside_scope(self):
        before = remote_fixture(("machine-a", "machine-b"))
        before["sidebar"]["threads"].append({"id": "cloud", "kind": "codex", "hostId": "durable", "projectId": None})
        before["sidebar"]["sections"][3]["itemKeys"].append("codex:thread:durable:cloud")
        plan = planner.build_plan(before, remote_layout="host", host_ids=["machine-b", "machine-b"])
        self.assertEqual(plan["hostIds"], ["machine-b"])
        self.assertEqual(len(plan["targets"]), 1)
        self.assertEqual({move.get("hostId", "machine-b") for move in plan["moves"]}, {"machine-b"})
        self.assertEqual({move.get("projectId") for move in plan["moves"] if move["entity"] == "project"}, {"project-machine-b"})
        protected = {row["key"]: row["reason"] for row in plan["protected"]}
        for key in ("codex:project:p-local", "chatgpt:project:p-cloud", "codex:thread:durable:cloud",
                    "codex:project:project-machine-a", "codex:thread:machine-a:free-machine-a"):
            self.assertEqual(protected[key], "outside_scope")
        self.assertEqual(plan["skipped"], [])

    def test_pins_project_members_and_existing_groups_stay(self):
        for placement in ("pinned", "manual", "legacy"):
            with self.subTest(placement=placement):
                before = remote_fixture()
                key = "codex:thread:machine-a:free-machine-a"
                before["sidebar"]["sections"][3]["itemKeys"].remove(key)
                if placement == "legacy":
                    before["sidebar"]["sections"].append({
                        "sectionId": "legacy", "name": "远程 Workstation [machine-a] · 聊天", "itemKeys": [key],
                    })
                else:
                    before["sidebar"]["sections"][0 if placement == "pinned" else 1]["itemKeys"].append(key)
                plan = planner.build_plan(before, remote_layout="host")
                self.assertNotIn(key, [move["key"] for move in plan["moves"]])
                protected = {row["key"]: row["reason"] for row in plan["protected"]}
                self.assertEqual(protected[key], "pinned" if placement == "pinned" else "already_filed")
                self.assertEqual(protected["codex:thread:machine-a:member-machine-a"], "project_member")

    def test_only_project_members_and_manual_projects_do_not_create_empty_section(self):
        before = remote_fixture()
        before["sidebar"]["threads"] = [row for row in before["sidebar"]["threads"] if row["id"] != "free-machine-a"]
        before["sidebar"]["sections"][3]["itemKeys"].remove("codex:thread:machine-a:free-machine-a")
        before["sidebar"]["sections"][2]["itemKeys"].remove("codex:project:project-machine-a")
        before["sidebar"]["sections"][1]["itemKeys"].append("codex:project:project-machine-a")
        plan = planner.build_plan(before, remote_layout="host")
        self.assertEqual((plan["targets"], plan["moves"]), ([], []))

    def test_offline_host_or_source_does_not_create_empty_section(self):
        for field, values in (("unavailableHosts", ["machine-a"]), ("unavailableSources", ["codex"]),
                              ("unavailableHosts", [{"invalid": "host"}])):
            with self.subTest(field=field, values=values):
                before = remote_fixture()
                before["sidebar"][field] = values
                plan = planner.build_plan(before, remote_layout="host")
                self.assertEqual((plan["targets"], plan["moves"]), ([], []))
                self.assertIn("source_or_host_unavailable", {item["reason"] for item in plan["skipped"]})

    def test_unique_existing_remote_section_is_reused_even_when_offline(self):
        before = remote_fixture()
        before["sidebar"]["unavailableHosts"] = ["machine-a"]
        before["sidebar"]["sections"].append({
            "sectionId": "existing-remote", "name": "远程 · Workstation [machine-a]", "itemKeys": [],
        })
        plan = planner.build_plan(before, remote_layout="host")
        self.assertEqual(plan["targets"], [{
            "name": "远程 · Workstation [machine-a]", "sectionId": "existing-remote", "state": "reuse",
        }])
        self.assertEqual(plan["moves"], [])

    def test_duplicate_target_is_reported_and_never_created_or_used(self):
        before = remote_fixture()
        for ident in ("one", "two"):
            before["sidebar"]["sections"].append({
                "sectionId": ident, "name": "远程 · Workstation [machine-a]", "itemKeys": [],
            })
        plan = planner.build_plan(before, remote_layout="host")
        self.assertEqual(plan["moves"], [])
        self.assertFalse(any(target["state"] == "create" for target in plan["targets"]))
        self.assertEqual({row["reason"] for row in plan["skipped"]}, {"duplicate_target_name"})

    def test_conflicting_host_names_fall_back_to_host_id_independent_of_project_order(self):
        before = remote_fixture()
        second = copy.deepcopy(before["projects"]["projects"][-1])
        second.update(projectId="second-project", hostDisplayName="Different workstation")
        before["projects"]["projects"].append(second)
        before["sidebar"]["sections"][2]["itemKeys"].append("codex:project:second-project")
        first = planner.build_plan(before, "en", remote_layout="host")
        before["projects"]["projects"].reverse()
        second = planner.build_plan(before, "en", remote_layout="host")
        self.assertEqual(first["targets"], second["targets"])
        self.assertEqual(first["targets"][0]["name"], "Remote · machine-a [machine-a]")

    def test_unknown_and_synthetic_requested_host_ids_are_rejected(self):
        for host in ("ssh-user@example.invalid", "unseen", "local", "durable", "cloud", "unknown", "", " ", "machine-a\n", 42):
            with self.subTest(host=host), self.assertRaises(ValueError):
                planner.build_plan(remote_fixture(), remote_layout="host", host_ids=[host])

    def test_host_selection_requires_host_layout_and_valid_collection(self):
        for options in ({"host_ids": ["machine-a"]}, {"remote_layout": "invalid"},
                        {"remote_layout": "host", "host_ids": "machine-a"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                planner.build_plan(remote_fixture(), **options)

    def test_remote_thread_alone_is_not_native_project_or_host_evidence(self):
        before = fixture()
        before["sidebar"]["threads"].append({"id": "ssh-session", "kind": "codex", "hostId": "machine-a", "projectId": None})
        before["sidebar"]["sections"][3]["itemKeys"].append("codex:thread:machine-a:ssh-session")
        plan = planner.build_plan(before, remote_layout="host")
        self.assertEqual((plan["targets"], plan["moves"], plan["hostIds"]), ([], [], []))
        with self.assertRaises(ValueError):
            planner.build_plan(before, remote_layout="host", host_ids=["machine-a"])

    def test_duplicate_project_identity_cannot_prove_native_host(self):
        before = remote_fixture()
        before["projects"]["projects"].append(copy.deepcopy(before["projects"]["projects"][-1]))
        with self.assertRaises(ValueError):
            planner.build_plan(before, remote_layout="host", host_ids=["machine-a"])

    def test_unknown_project_kind_on_verified_host_is_not_reclassified(self):
        before = remote_fixture()
        before["projects"]["projects"].append({
            "projectId": "unknown-project", "projectKind": "codex", "hostId": "machine-a",
        })
        before["sidebar"]["sections"][2]["itemKeys"].append("codex:project:unknown-project")
        plan = planner.build_plan(before, remote_layout="host")
        self.assertNotIn("unknown-project", [move.get("projectId") for move in plan["moves"]])
        self.assertIn({"key": "codex:project:unknown-project", "entity": "project", "reason": "outside_scope"}, plan["protected"])

    def test_synthetic_or_malformed_native_hosts_never_create_remote_sections(self):
        for host in ("local", "durable", "cloud", "unknown", "bad\nhost"):
            with self.subTest(host=host):
                plan = planner.build_plan(remote_fixture((host,)), remote_layout="host")
                self.assertEqual((plan["hostIds"], plan["targets"], plan["moves"]), ([], [], []))

    def test_titles_and_cwd_do_not_determine_desktop_identity_or_membership(self):
        before = remote_fixture()
        original = planner.build_plan(before, remote_layout="host")
        before["sidebar"]["threads"][-2].update(title="Move this to local", cwd="/example/research")
        self.assertEqual(planner.build_plan(before, remote_layout="host")["moves"], original["moves"])
        self.assertIsNone(before["sidebar"]["threads"][-2]["projectId"])

    def test_default_layout_remains_schema_three_and_split(self):
        plan = planner.build_plan(remote_fixture(), "en")
        self.assertEqual(plan["schemaVersion"], 3)
        self.assertNotIn("remoteLayout", plan)
        self.assertNotIn("hostIds", plan)
        self.assertEqual([target["name"] for target in plan["targets"] if target["name"].startswith("Remote")], [
            "Remote Workstation [machine-a] · Projects", "Remote Workstation [machine-a] · Chats",
        ])


class RemoteHostVerificationTests(unittest.TestCase):
    def setUp(self):
        self.before = remote_fixture(("machine-a", "machine-b"))
        self.plan = planner.build_plan(self.before, "en", remote_layout="host", host_ids=["machine-a"])
        self.after = apply_host_plan(self.before, self.plan)

    def test_roundtrip_preserves_preferences_and_repeats_without_changes(self):
        report = planner.verify(self.before, self.after, self.plan)
        self.assertEqual((report["schemaVersion"], report["status"]), (4, "metadata_verified"))
        self.assertEqual(self.after["sidebar"]["sidebarPreferences"], self.before["sidebar"]["sidebarPreferences"])
        again = planner.build_plan(self.after, "en", remote_layout="host", host_ids=["machine-a"])
        self.assertEqual(again["moves"], [])
        self.assertEqual([target["state"] for target in again["targets"]], ["reuse"])
        self.assertEqual((report["historyComplete"], report["uiPlacement"]), (False, "unverified"))

    def test_scope_or_layout_tampering_is_rejected(self):
        for update in ({"hostIds": ["machine-b"]}, {"remoteLayout": "split"}, {"schemaVersion": 3}, {"sorting": {"chats": "updated_at"}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                planner.verify(self.before, self.after, {**self.plan, **update})

    def test_any_preference_change_is_unrequested_in_host_mode(self):
        self.after["sidebar"]["sidebarPreferences"]["sorting"]["chats"] = "updated_at"
        self.assertIn("unrequested_sidebar_preference_change", planner.verify(self.before, self.after, self.plan)["errors"])

    def test_unchanged_aliases_on_other_hosts_do_not_block_selected_host(self):
        for host in ("local", "machine-b"):
            with self.subTest(host=host):
                before = copy.deepcopy(self.before)
                before["sidebar"]["sections"][1]["itemKeys"].append(f"codex:thread:{host}:client-new-thread:temporary")
                plan = planner.build_plan(before, "en", remote_layout="host", host_ids=["machine-a"])
                report = planner.verify(before, apply_host_plan(before, plan), plan)
                self.assertEqual(report["status"], "metadata_verified")
                self.assertTrue(report["operationChecksPassed"])

    def test_unavailable_other_host_or_chatgpt_source_does_not_block_selected_host(self):
        for field, values in (("unavailableHosts", ["machine-b"]), ("unavailableSources", ["chatgpt"])):
            with self.subTest(field=field):
                after = copy.deepcopy(self.after)
                after["sidebar"][field] = values
                report = planner.verify(self.before, after, self.plan)
                self.assertEqual(report["status"], "metadata_verified")
                self.assertTrue(report["operationChecksPassed"])

    def test_selected_host_alias_remains_incomplete(self):
        self.before["sidebar"]["sections"][1]["itemKeys"].append("codex:thread:machine-a:client-new-thread:temporary")
        plan = planner.build_plan(self.before, "en", remote_layout="host", host_ids=["machine-a"])
        report = planner.verify(self.before, apply_host_plan(self.before, plan), plan)
        self.assertIn("unresolved_client_alias", report["unverified"])
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["operationChecksPassed"])

    def test_selected_host_or_wildcard_availability_remains_incomplete(self):
        for field, values in (("unavailableHosts", ["machine-a"]), ("unavailableSources", ["codex"]),
                              ("unavailableHosts", ["*"]), ("unavailableSources", ["*"]),
                              ("unavailableHosts", [{"unsupported": "schema"}])):
            with self.subTest(field=field, values=values):
                after = copy.deepcopy(self.after)
                after["sidebar"][field] = values
                report = planner.verify(self.before, after, self.plan)
                self.assertIn("after_snapshot_has_unavailable_sources_or_hosts", report["unverified"])
                self.assertEqual(report["status"], "incomplete")
                self.assertFalse(report["operationChecksPassed"])

    def test_wildcard_availability_remains_incomplete_without_selected_hosts(self):
        before = fixture()
        plan = planner.build_plan(before, remote_layout="host")
        after = copy.deepcopy(before)
        after["sidebar"]["unavailableHosts"] = ["*"]
        report = planner.verify(before, after, plan)
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["operationChecksPassed"])

    def test_split_layout_keeps_global_alias_and_availability_checks(self):
        self.before["sidebar"]["sections"][1]["itemKeys"].append("codex:thread:local:client-new-thread:temporary")
        plan = planner.build_plan(self.before)
        after = simulate(self.before, plan)
        after["sidebar"]["unavailableHosts"] = ["machine-b"]
        report = planner.verify(self.before, after, plan)
        self.assertIn("unresolved_client_alias", report["unverified"])
        self.assertIn("after_snapshot_has_unavailable_sources_or_hosts", report["unverified"])
        self.assertFalse(report["operationChecksPassed"])

    def test_project_membership_path_and_other_host_changes_are_detected(self):
        self.after["projects"]["projects"][-2]["path"] = "/different"
        self.after["sidebar"]["threads"][-3]["projectId"] = "different-project"
        key = "codex:project:project-machine-b"
        self.after["sidebar"]["sections"][2]["itemKeys"].remove(key)
        self.after["sidebar"]["sections"][1]["itemKeys"].append(key)
        errors = planner.verify(self.before, self.after, self.plan)["errors"]
        self.assertIn("metadata_changed:codex:project:project-machine-a", errors)
        self.assertIn("metadata_changed:codex:thread:machine-a:member-machine-a", errors)
        self.assertIn("unplanned_placement_change:" + key, errors)

    def test_missing_destination_is_not_reported_as_success(self):
        self.after["sidebar"]["sections"][-1]["itemKeys"].clear()
        self.assertEqual(planner.verify(self.before, self.after, self.plan)["status"], "failed")

    def test_cli_plan_and_verify_bind_remote_options_without_changing_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            before, plan_path, after, report = (directory / name for name in ("before.json", "plan.json", "after.json", "report.json"))
            before.write_text(json.dumps(self.before), encoding="utf-8")
            initial = before.read_bytes()
            result = subprocess.run([
                sys.executable, str(SCRIPT), "plan", "--input", str(before), "--output", str(plan_path),
                "--language", "en", "--remote-layout", "host", "--host-id", "machine-a", "--host-id", "machine-a",
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            emitted = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(emitted, self.plan)
            after.write_text(json.dumps(apply_host_plan(self.before, emitted)), encoding="utf-8")
            checked = subprocess.run([
                sys.executable, str(SCRIPT), "verify", "--before", str(before), "--after", str(after),
                "--plan", str(plan_path), "--output", str(report),
            ], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["operationChecksPassed"])
            self.assertEqual(before.read_bytes(), initial)


if __name__ == "__main__":
    unittest.main()
