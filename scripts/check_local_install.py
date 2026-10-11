#!/usr/bin/env python3
"""Optional Codex CLI install check with an isolated temporary configuration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = shutil.which("codex") or shutil.which("codex.cmd")
    if not executable:
        raise SystemExit("Codex CLI is required for this optional check")
    with tempfile.TemporaryDirectory(prefix="sidebar-install-check-") as tmp:
        test_root = Path(tmp).resolve()
        assert test_root.parent == Path(tempfile.gettempdir()).resolve()
        test_env = dict(os.environ, CODEX_HOME=str(test_root / "codex-config"))
        (test_root / "codex-config").mkdir()

        def run(*args):
            result = subprocess.run([executable, "plugin", *args], env=test_env, cwd=test_root,
                                    capture_output=True, text=True, encoding="utf-8", timeout=60)
            if result.returncode:
                raise RuntimeError(f"Codex {' '.join(args[:2])} failed: {result.stderr}")
            return json.loads(result.stdout)

        run("marketplace", "add", str(ROOT), "--json")
        listing = run("list", "--marketplace", "sidebar-organizer-marketplace", "--available", "--json")
        if "sidebar-organizer" not in json.dumps(listing.get("available", [])):
            raise RuntimeError("Plugin missing from isolated marketplace listing")
        run("add", "sidebar-organizer@sidebar-organizer-marketplace", "--json")
        copies = list((test_root / "codex-config/plugins/cache").rglob("skills/organize-sidebar/SKILL.md"))
        if len(copies) != 1:
            raise RuntimeError("Expected one installed skill copy")
        assert copies[0].read_bytes() == (ROOT / "plugins/sidebar-organizer/skills/organize-sidebar/SKILL.md").read_bytes()
        plugin_copy = copies[0].parents[2]
        for relative in ("plugin.json", "skills/organize-sidebar/scripts/sidebar_plan.py", "skills/organize-sidebar/references/native-tools.md"):
            assert (plugin_copy / relative).read_bytes() == (ROOT / "plugins/sidebar-organizer" / relative).read_bytes()
        print(json.dumps({"isolatedMarketplace": "passed", "install": "passed", "pluginBytesMatch": True}))


if __name__ == "__main__":
    main()
