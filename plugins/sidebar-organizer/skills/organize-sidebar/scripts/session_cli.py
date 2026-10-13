#!/usr/bin/env python3
"""Browse, group, and resume local Codex sessions. Python 3.10+, no dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata

from session_groups import GroupError, GroupStore
from session_rpc import AppServer, RpcError


SOURCES = ("cli", "vscode", "exec", "appServer", "subAgent", "subAgentReview",
           "subAgentCompact", "subAgentThreadSpawn", "subAgentOther", "unknown")


def display(value):
    """Treat names and paths as plain terminal text, including bidi/ANSI controls."""
    return "".join(c if not unicodedata.category(c).startswith("C") else " "
                   for c in str(value))


def default_data_file():
    base = os.environ.get("XDG_DATA_HOME")
    if not base and os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
    return (Path(base).expanduser() if base else Path.home() / ".local/share") / "codex-sidebar-organizer/groups.json"


def source_name(source):
    if isinstance(source, str):
        return source
    if isinstance(source, dict) and "subAgent" in source:
        return "subAgent"
    if isinstance(source, dict) and isinstance(source.get("custom"), str):
        return "custom: " + source["custom"]
    return "unknown"


def session_rows(threads, groups):
    memberships = {sid: name for name, ids in groups.items() for sid in ids}
    rows = []
    for thread in threads:
        name = thread.get("name")
        cwd = thread.get("cwd")
        updated = thread.get("updatedAt")
        rows.append({"id": thread["id"], "name": name if isinstance(name, str) and name.strip() else "Untitled",
                     "cwd": cwd if isinstance(cwd, str) else None,
                     "source": source_name(thread.get("source")),
                     "updatedAt": updated if type(updated) is int else None,
                     "group": memberships.get(thread["id"])})
    return rows


def render(rows, group_by, index_only=False):
    fields = {"project": "cwd", "source": "source", "group": "group"}
    buckets = {}
    for row in rows:
        label = row[fields[group_by]]
        buckets.setdefault(label, []).append(row)
    ordered = []
    for label, members in buckets.items():
        print(f"\n{display(label) if label is not None else '(unassigned)'} ({len(members)})")
        for row in members:
            ordered.append(row)
            try:
                updated = datetime.fromtimestamp(row["updatedAt"]).astimezone().strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError, OverflowError):
                updated = "unknown time"
            print(f"  [{len(ordered)}] {display(row['name'])[:100]}")
            print(f"      {display(row['id'])}  {updated}  {display(row['source'])}")
            if group_by != "project":
                print(f"      {display(row['cwd']) if row['cwd'] else '(unknown directory)'}")
            if group_by != "group" and row["group"] is not None:
                print(f"      group: {display(row['group'])}")
    scope = "state index" if index_only else "saved sessions"
    print(f"\n{len(rows)} session(s) from the current Codex home's {scope}, with the selected filters. Desktop groups are separate.")
    return ordered


def resolve_session(rows, selector):
    if not selector or selector.startswith("-") or any(c.isspace() or unicodedata.category(c).startswith("C") for c in selector):
        raise ValueError("Use a session ID or a unique ID prefix.")
    exact = [row for row in rows if row["id"] == selector]
    matches = exact or [row for row in rows if row["id"].startswith(selector)]
    if not matches:
        raise ValueError(f"No listed session matches {selector!r}.")
    if len(matches) != 1:
        raise ValueError(f"Ambiguous ID prefix {selector!r}; use a longer prefix.")
    return matches[0]


def resume_session(args, row):
    cwd = row.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise ValueError("The session's recorded working directory is unavailable; restore it before resuming.")
    command = [args.codex]
    for value in args.config:
        command.extend(["-c", value])
    command.extend(["resume", "--all", row["id"]])
    if args.dry_run:
        print(json.dumps({"argv": command, "cwd": cwd}, ensure_ascii=False, indent=2))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Resume requires an interactive terminal. Use resume ID --dry-run to inspect the command.")
    # Resolve a relative CODEX_HOME before changing cwd in the child process.
    child_env = dict(os.environ)
    if child_env.get("CODEX_HOME"):
        child_env["CODEX_HOME"] = str(Path(child_env["CODEX_HOME"]).expanduser().resolve())
    print(f"Resuming {display(row['id'])} in {display(cwd)}", flush=True)
    return subprocess.call(command, cwd=cwd, env=child_env)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--codex", default="codex", help="Codex executable path (not a shell command)")
    result.add_argument("-c", "--config", action="append", default=[], help="Codex KEY=VALUE override; repeat as needed")
    result.add_argument("--data-file", type=Path, default=default_data_file(), help="Independent CLI groups JSON file")
    result.add_argument("--timeout", type=float, default=15.0, help="App Server request timeout in seconds")
    result.add_argument("--index-only", action="store_true", help="Skip Codex's normal log scan and index repair; older sessions may be missing")
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("list", "browse"):
        command = sub.add_parser(name, help="List sessions" if name == "list" else "Choose a session and resume it")
        command.add_argument("--group-by", choices=("project", "source", "group"), default="project")
        command.add_argument("--source", choices=SOURCES, action="append", help="Filter by entry point; repeatable")
        command.add_argument("--cwd", type=Path, help="Filter by exact working directory")
        command.add_argument("--search", help="Native title substring filter")
        command.add_argument("--group", help="Filter by a saved CLI group")
        if name == "list":
            command.add_argument("--json", action="store_true", help="Output projected metadata as JSON")
        else:
            command.set_defaults(dry_run=False)
    resume = sub.add_parser("resume", help="Continue a session by ID or unique prefix")
    resume.add_argument("session_id")
    resume.add_argument("--dry-run", action="store_true", help="Print argv/cwd without starting a conversation")
    group = sub.add_parser("group", help="Manage independent local groups")
    operations = group.add_subparsers(dest="group_command", required=True)
    add = operations.add_parser("add", help="Assign listed sessions to a named group")
    add.add_argument("name")
    add.add_argument("session_ids", nargs="+")
    unassign = operations.add_parser("unassign", help="Remove exact IDs from their groups, keeping sessions")
    unassign.add_argument("session_ids", nargs="+")
    remove = operations.add_parser("remove", help="Remove only the local group, keeping sessions")
    remove.add_argument("name")
    operations.add_parser("list", help="Show saved groups without starting App Server")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not 0 < args.timeout < float("inf"):
            raise ValueError("--timeout must be a positive finite number.")
        # Resolve the executable once, before resume changes the working directory.
        if os.path.dirname(args.codex):
            args.codex = str(Path(args.codex).expanduser().resolve())
        scope = str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve())
        store = GroupStore(args.data_file.expanduser(), scope)
        if args.command == "group" and args.group_command != "add":
            if args.group_command == "unassign":
                store.unassign(args.session_ids)
                print("Removed group assignments; sessions are unchanged.")
            elif args.group_command == "remove":
                store.remove(args.name)
                print("Removed the CLI group; sessions are unchanged.")
            else:
                groups = store.groups()
                for name, ids in groups.items():
                    print(f"{display(name)} ({len(ids)})")
                    for sid in ids:
                        print(f"  {display(sid)}")
                if not groups:
                    print("No saved CLI groups.")
            return 0
        if args.command == "browse" and (not sys.stdin.isatty() or not sys.stdout.isatty()):
            raise ValueError("Browse requires an interactive terminal. Use list or resume ID --dry-run.")
        groups = store.groups()
        requested_group = getattr(args, "group", None)
        if requested_group is not None and requested_group not in groups:
            raise ValueError(f"Unknown CLI group {requested_group!r}.")
        sources = getattr(args, "source", None)
        if args.command in {"resume", "group"}:
            sources = list(SOURCES)
        cwd = getattr(args, "cwd", None)
        with AppServer(codex=args.codex, config=args.config, timeout=args.timeout) as server:
            threads = server.list_threads(sources=sources,
                                          cwd=str(cwd.expanduser().resolve()) if cwd else None,
                                          search=getattr(args, "search", None), index_only=args.index_only)
        rows = session_rows(threads, groups)
        if args.command == "resume":
            return resume_session(args, resolve_session(rows, args.session_id))
        if args.command == "group":
            ids = [resolve_session(rows, sid)["id"] for sid in args.session_ids]
            store.assign(args.name, ids)
            print(f"Assigned {len(set(ids))} session(s) to {display(args.name)}.")
            return 0
        if requested_group is not None:
            rows = [row for row in rows if row["group"] == requested_group]
        if args.command == "list" and args.json:
            print(json.dumps({"schemaVersion": 1, "scope": scope, "sessions": rows,
                              "coverage": "current_home_state_index" if args.index_only else "current_home_saved_sessions",
                              "desktopGroups": "separate"},
                             ensure_ascii=False, indent=2))
            return 0
        ordered = render(rows, args.group_by, args.index_only)
        if args.command == "browse" and ordered:
            while True:
                choice = input("Session number (q to quit): ").strip()
                if choice.lower() in {"q", "quit", ""}:
                    return 0
                if choice.isascii() and choice.isdigit() and 1 <= int(choice) <= len(ordered):
                    return resume_session(args, ordered[int(choice) - 1])
                print("Choose a displayed number, or q to quit.")
        return 0
    except (RpcError, GroupError, ValueError, OSError) as exc:
        print(f"Cannot complete command: {display(exc)}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
