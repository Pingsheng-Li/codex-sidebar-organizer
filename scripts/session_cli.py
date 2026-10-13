#!/usr/bin/env python3
"""Run the bundled session organizer from a source checkout."""
from pathlib import Path
import runpy
import sys

scripts = Path(__file__).resolve().parents[1] / "plugins/sidebar-organizer/skills/organize-sidebar/scripts"
sys.path.insert(0, str(scripts))
if __name__ == "__main__":
    runpy.run_path(str(scripts / "session_cli.py"), run_name="__main__")
