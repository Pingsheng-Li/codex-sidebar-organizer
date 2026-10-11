#!/usr/bin/env python3
"""Build deterministic, allowlisted plugin/skill ZIPs and test extracted bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sidebar-organizer"
SKILL = PLUGIN / "skills/organize-sidebar"
SKILL_FILES = ["SKILL.md", "agents/openai.yaml", "references/native-tools.md", "scripts/sidebar_plan.py"]


def checked_bytes(path):
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"Refusing non-contained file: {path.name}")
    data = path.read_bytes()
    text = data.decode("utf-8")
    if text.startswith("\ufeff"):
        raise ValueError(f"Unexpected UTF-8 BOM: {path.name}")
    return text.replace("\r\n", "\n").encode("utf-8")


def validate():
    manifest = json.loads(checked_bytes(PLUGIN / "plugin.json"))
    assert manifest["name"] == PLUGIN.name
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert not {"skills", "mcpServers", "apps", "interface"}.intersection(manifest)
    ui = manifest["extensions"]["com.openai"]["interface"]
    assert 1 <= len(ui["shortDescription"]) <= 30
    assert ui["capabilities"] == ["Interactive"]
    market = json.loads(checked_bytes(ROOT / ".agents/plugins/marketplace.json"))
    assert market["name"] == "sidebar-organizer-marketplace"
    assert len(market["plugins"]) == 1
    entry = market["plugins"][0]
    assert entry["name"] == manifest["name"]
    assert entry["source"] == {"source": "local", "path": "./plugins/sidebar-organizer"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    front = checked_bytes(SKILL / "SKILL.md").decode("utf-8").split("---", 2)[1]
    fields = dict(line.split(": ", 1) for line in front.strip().splitlines())
    assert set(fields) == {"name", "description"}
    assert fields["name"] == SKILL.name
    assert len(fields["description"]) <= 1024
    yaml = checked_bytes(SKILL / "agents/openai.yaml").decode("utf-8")
    assert "$organize-sidebar" in yaml
    assert not any(marker in checked_bytes(SKILL / file).decode("utf-8") for file in SKILL_FILES for marker in ("[TODO", "TODO:"))
    return manifest["version"]


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("Unsafe archive path")
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(entries)
        for name, data in entries.items():
            assert archive.read(name) == data


def smoke(path, script_relative):
    # Synthetic fixture/model only. Read the helper from the extracted release.
    spec = importlib.util.spec_from_file_location("synthetic_fixture", ROOT / "tests/test_sidebar_plan.py")
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    with tempfile.TemporaryDirectory(prefix="sidebar-release-check-") as tmp:
        directory = Path(tmp)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(directory)
        script = directory / script_relative
        before = fixture_module.fixture()
        before_path = directory / "synthetic-before.json"
        before_path.write_text(json.dumps(before), encoding="utf-8")
        plan_path = directory / "synthetic-plan.json"
        subprocess.run([sys.executable, str(script), "plan", "--input", str(before_path), "--output", str(plan_path)], check=True, capture_output=True)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert len(plan["moves"]) == 5 and not plan["coverage"]["complete"]
        after_path = directory / "synthetic-after.json"
        after_path.write_text(json.dumps(fixture_module.simulate(before, plan)), encoding="utf-8")
        result_path = directory / "synthetic-verification.json"
        subprocess.run([sys.executable, str(script), "verify", "--before", str(before_path), "--after", str(after_path), "--plan", str(plan_path), "--output", str(result_path)], check=True, capture_output=True)
        assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "metadata_verified"
        alias_native, alias_state = fixture_module.alias_fixture()
        alias_input, state_path = directory / "alias-native.json", directory / "local-state.json"
        alias_input.write_text(json.dumps(alias_native), encoding="utf-8")
        state_path.write_text(json.dumps(alias_state), encoding="utf-8")
        state_bytes = state_path.read_bytes()
        alias_snapshot, alias_plan = directory / "alias-captured.json", directory / "alias-plan.json"
        subprocess.run([sys.executable, str(script), "capture-identity", "--input", str(alias_input),
                        "--state", str(state_path), "--output", str(alias_snapshot)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(script), "plan", "--input", str(alias_snapshot),
                        "--output", str(alias_plan)], check=True, capture_output=True)
        result = json.loads(alias_plan.read_text(encoding="utf-8"))
        assert len(result["identityReconciliation"]["resolvedMemberships"]) == 1
        assert not any(m.get("threadId") == "t-new" for m in result["moves"])
        assert state_path.read_bytes() == state_bytes


def main():
    version = validate()
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    license_bytes = checked_bytes(ROOT / "LICENSE")
    install = ("# Sidebar Organizer\n\n"
               "Use in a Codex desktop session exposing native sidebar tools.\n"
               "Standalone skill: copy the complete organize-sidebar folder into ~/.codex/skills/, then start a fresh desktop session.\n"
               "Plugin: import this plugin directory in a supported client or install from its GitHub marketplace.\n"
               "Choose either the plugin or standalone skill; do not install both.\n\n"
               "Request: Use $organize-sidebar to organize my sidebar by source.\n"
               "Preview: Use $organize-sidebar to preview only, without moving anything.\n\n"
               "Preserves pins, project membership, and manual groups. Recent list coverage may be partial.\n"
               "Automatic collapse requires a supported UI surface. No cross-device sync guarantee.\n"
               "No server/API key; optional helper needs Python 3.10+.\n\n"
               "Full Chinese/English instructions: https://github.com/VeraPyuyi/codex-sidebar-organizer\n").encode("utf-8")
    skill_entries = {"organize-sidebar/" + file: checked_bytes(SKILL / file) for file in SKILL_FILES}
    skill_entries.update({"organize-sidebar/LICENSE": license_bytes, "organize-sidebar/INSTALL.md": install})
    plugin_entries = {"sidebar-organizer/skills/" + name: data for name, data in skill_entries.items() if not name.endswith(("/LICENSE", "/INSTALL.md"))}
    plugin_entries.update({"sidebar-organizer/plugin.json": checked_bytes(PLUGIN / "plugin.json"),
                           "sidebar-organizer/LICENSE": license_bytes, "sidebar-organizer/INSTALL.md": install})
    jobs = [(f"sidebar-organizer-plugin-{version}.zip", plugin_entries, "sidebar-organizer/skills/organize-sidebar/scripts/sidebar_plan.py"),
            (f"organize-sidebar-skill-{version}.zip", skill_entries, "organize-sidebar/scripts/sidebar_plan.py")]
    checksums = []
    for name, entries, script in jobs:
        path = output / name
        write_zip(path, entries)
        smoke(path, script)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {name}\n")
        print(json.dumps({"file": name, "bytes": path.stat().st_size, "sha256": digest, "extractedSmokeTest": "passed"}))
    (output / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
