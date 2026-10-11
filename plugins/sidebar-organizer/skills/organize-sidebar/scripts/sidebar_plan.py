#!/usr/bin/env python3
"""Read-only sidebar planner/verifier. Python 3.10+, standard library only."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

DEFAULTS = {"threads", "chats", "projects", "orbit", "agents"}
NON_HOSTS = {"durable", "cloud", "unknown"}
LABELS = {
    "zh": ["本机 · 项目", "ChatGPT 云端 · 项目", "本机 · 聊天", "ChatGPT 云端 · 聊天", "来源待确认"],
    "en": ["Local · Projects", "ChatGPT Cloud · Projects", "Local · Chats", "ChatGPT Cloud · Chats", "Source Unconfirmed"],
}


def stable(value):
    return isinstance(value, str) and bool(value.strip())


def fingerprint(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def chat_key(row):
    if not stable(row.get("id")):
        return None
    if row.get("kind") == "chatgpt":
        return "chatgpt:conversation:" + row["id"]
    if row.get("kind") == "codex" and stable(row.get("hostId")):
        return f"codex:thread:{row['hostId']}:{row['id']}"
    return None


def availability(values, field):
    result = set()
    for value in values:
        ident = value if isinstance(value, str) else value.get(field) if isinstance(value, dict) else None
        if not stable(ident):
            return {"*"}  # Unknown availability representation: fail closed.
        result.add(ident)
    return result


def array(obj, field):
    if not isinstance(obj, dict) or not isinstance(obj.get(field), list):
        raise ValueError(f"Expected an explicit {field} array; check the live native schema")
    return obj[field]


def index(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be an object")
    project_rows = array(snapshot.get("projects"), "projects")
    sidebar = snapshot.get("sidebar")
    recent = array(sidebar, "threads")
    pins = array(sidebar, "pinnedThreads")
    sections = array(sidebar, "sections")
    hosts = availability(array(sidebar, "unavailableHosts"), "hostId")
    sources = availability(array(sidebar, "unavailableSources"), "source")
    if not isinstance(sidebar.get("sidebarPreferences"), dict):
        raise ValueError("Expected sidebarPreferences object")
    section_map, locations, names = {}, defaultdict(list), defaultdict(list)
    for section in sections:
        if not isinstance(section, dict) or not stable(section.get("sectionId")) or not stable(section.get("name")):
            raise ValueError("Section must have a stable sectionId and name")
        sid = section["sectionId"]
        if sid in section_map:
            raise ValueError("Duplicate sectionId")
        section_map[sid] = section
        if sid not in DEFAULTS and sid != "pinned":
            names[section["name"]].append(sid)
        for key in array(section, "itemKeys"):
            if not stable(key):
                raise ValueError("Invalid section itemKey")
            locations[key].append(sid)
    projects, chats, invalid = {}, {}, []
    duplicates = set()
    ids = Counter(r.get("projectId") for r in project_rows if isinstance(r, dict) and stable(r.get("projectId")))
    for position, row in enumerate(project_rows):
        if not isinstance(row, dict):
            raise ValueError("Project row must be an object")
        pid = row.get("projectId")
        if not stable(pid):
            invalid.append({"entity": "project", "position": position, "reason": "missing_stable_id"})
            continue
        # For unknown kinds require explicit native section evidence of the namespace.
        candidates = [f"{source}:project:{pid}" for source in ("codex", "chatgpt")]
        if row.get("projectKind") == "chatgpt":
            key = candidates[1]
        elif row.get("projectKind") in {"local", "remote"}:
            key = candidates[0]
        else:
            present = [k for k in candidates if k in locations]
            key = present[0] if len(present) == 1 else None
        if key is None:
            invalid.append({"entity": "project", "id": pid, "reason": "unknown_project_namespace"})
            continue
        projects[key] = row
        if ids[pid] != 1:
            duplicates.add(key)
    for position, row in enumerate(recent + pins):
        if not isinstance(row, dict):
            raise ValueError("Chat row must be an object")
        key = chat_key(row)
        if key is None:
            invalid.append({"entity": "chat", "position": position, "reason": "unroutable_identity"})
            continue
        if key in chats:
            fields = ("id", "kind", "hostId", "projectId")
            if any(chats[key].get(f) != row.get(f) for f in fields):
                duplicates.add(key)
        else:
            chats[key] = row
    recent_counts = Counter(chat_key(r) for r in recent)
    duplicates.update(k for k, count in recent_counts.items() if k and count > 1)
    pin_keys = [chat_key(r) for r in pins]
    duplicates.update(k for k, count in Counter(pin_keys).items() if k and count > 1)
    return dict(projects=projects, chats=chats, sections=section_map, locations=locations,
                names=names, pins=pin_keys, invalid=invalid, duplicates=duplicates,
                hosts=hosts, sources=sources, preferences=sidebar["sidebarPreferences"], recent=recent)


def blocked(source, host, data):
    return "*" in data["sources"] or source in data["sources"] or (
        source == "codex" and ("*" in data["hosts"] or host in data["hosts"]))


def build_plan(snapshot, language="zh"):
    labels = LABELS[language]
    data = index(snapshot)
    remote = {}
    for key, row in data["projects"].items():
        host = row.get("hostId")
        if (key not in data["duplicates"] and row.get("projectKind") in {"local", "remote"}
                and stable(host) and host != "local" and host not in NON_HOSTS):
            remote[host] = row.get("hostDisplayName") or host
    remote_labels = {}
    for host in sorted(remote):
        prefix = "远程" if language == "zh" else "Remote"
        name = f"{prefix} {remote[host]} [{host}]"
        remote_labels[host] = [name + (" · 项目" if language == "zh" else " · Projects"),
                               name + (" · 聊天" if language == "zh" else " · Chats")]
    target_names = labels[:4] + [name for pair in remote_labels.values() for name in pair] + labels[4:]
    targets = [{"name": name, "sectionId": data["names"][name][0] if len(data["names"][name]) == 1 else None,
                "state": "ambiguous" if len(data["names"][name]) > 1 else "reuse" if data["names"][name] else "create"}
               for name in target_names]
    moves, protected, skipped = [], [], list(data["invalid"])

    def consider(key, row, entity):
        places = data["locations"].get(key, [])
        item = {"key": key, "entity": entity}
        if key in data["pins"] or "pinned" in places:
            protected.append({**item, "reason": "pinned"})
            return
        if entity == "chat" and row.get("projectId"):
            protected.append({**item, "reason": "project_member"})
            return
        if key in data["duplicates"]:
            skipped.append({**item, "reason": "duplicate_or_conflicting_identity"})
            return
        if len(places) != 1:
            skipped.append({**item, "reason": "ambiguous_or_missing_section"})
            return
        if places[0] not in DEFAULTS:
            protected.append({**item, "reason": "already_filed"})
            return
        source = key.split(":", 1)[0]
        host = row.get("hostId")
        if blocked(source, host, data):
            skipped.append({**item, "reason": "source_or_host_unavailable"})
            return
        kind = row.get("projectKind") if entity == "project" else row.get("kind")
        offset = 0 if entity == "project" else 2
        if source == "chatgpt" and kind == "chatgpt":
            target = labels[offset + 1]
        elif source == "codex" and kind in {"local", "remote", "codex"} and host == "local":
            target = labels[offset]
        elif source == "codex" and host in remote_labels and kind in {"local", "remote", "codex"}:
            target = remote_labels[host][0 if entity == "project" else 1]
        elif entity == "project":
            target = labels[4]
        else:
            skipped.append({**item, "reason": "unverified_host"})
            return
        if len(data["names"][target]) > 1:
            skipped.append({**item, "reason": "duplicate_target_name", "targetName": target})
            return
        move = {**item, "fromSection": places[0], "targetName": target}
        if entity == "project":
            move["projectId"] = row["projectId"]
        else:
            move.update(threadId=row["id"], source=source)
            if source == "codex":
                move["hostId"] = host
        moves.append(move)

    for key, row in data["projects"].items():
        consider(key, row, "project")
    # Native recent array is newest first. Moves prepend, so apply oldest first.
    visited = set()
    for row in list(reversed(data["recent"])) + snapshot["sidebar"]["pinnedThreads"]:
        key = chat_key(row)
        if key and key not in visited:
            visited.add(key)
            consider(key, row, "chat")
    known = set(data["chats"])
    unlisted = [k for k in data["locations"] if (k.startswith("codex:thread:") or k.startswith("chatgpt:conversation:")) and k not in known]
    return {
        "schemaVersion": 1, "language": language, "snapshotSha256": fingerprint(snapshot),
        "targets": targets, "moves": moves, "protected": protected, "skipped": skipped,
        "sorting": {"chats": "updated_at"},
        "coverage": {"complete": False, "totalHistory": None, "listedProjects": len(data["projects"]),
                     "listedChats": len(data["chats"]), "visible_unlisted_chat_keys": len(unlisted),
                     "unavailableHosts": sorted(data["hosts"]), "unavailableSources": sorted(data["sources"]),
                     "note": "Recent snapshot only; older history, visible UI, opening, and collapse are unverified."},
    }


def verify(before, after, plan):
    if plan != build_plan(before, plan.get("language", "zh")):
        raise ValueError("Plan does not match the before snapshot; regenerate it")
    old, new = index(before), index(after)
    errors, unknown, confirmed = [], [], []
    if old["pins"] != new["pins"] or old["sections"].get("pinned", {}).get("itemKeys") != new["sections"].get("pinned", {}).get("itemKeys"):
        errors.append("pinned_order_or_membership_changed")
    if "pinned" in old["sections"] and ("pinned" not in new["sections"] or list(old["sections"]).index("pinned") != list(new["sections"]).index("pinned")):
        errors.append("pinned_section_position_changed")
    if plan["skipped"]:
        unknown.append("plan_contains_skipped_items")
    for entity, fields in (("projects", ("projectId", "projectKind", "hostId", "path")),
                            ("chats", ("id", "kind", "hostId", "projectId", "pinnedIndex"))):
        for key, row in old[entity].items():
            if key not in new[entity]:
                unknown.append(f"record_missing:{key}")
            elif any(row.get(field) != new[entity][key].get(field) for field in fields):
                errors.append(f"metadata_changed:{key}")
        for key in new[entity].keys() - old[entity].keys():
            unknown.append(f"new_record_outside_plan:{key}")
    for field in ("invalid", "duplicates"):
        if old[field] or new[field]:
            unknown.append(f"unresolved_{field}")
    if new["hosts"] or new["sources"]:
        unknown.append("after_snapshot_has_unavailable_sources_or_hosts")
    if any(len(places) > 1 for places in new["locations"].values()):
        unknown.append("duplicate_after_section_membership")
    moved = {m["key"] for m in plan["moves"]}
    for key, sections in old["locations"].items():
        if key not in moved and sections != new["locations"].get(key, []):
            errors.append(f"unplanned_placement_change:{key}")
    for sid, section in old["sections"].items():
        if sid not in new["sections"] or new["sections"][sid]["name"] != section["name"]:
            errors.append(f"existing_section_missing_or_renamed:{sid}")
    for move in plan["moves"]:
        ids = new["names"].get(move["targetName"], [])
        if len(ids) == 1 and new["locations"].get(move["key"]) == ids:
            confirmed.append(move["key"])
        else:
            errors.append(f"destination_not_verified:{move['key']}")
    # Changes outside chats recency sorting are never requested by this helper.
    prefs_before, prefs_after = json.loads(json.dumps(old["preferences"])), json.loads(json.dumps(new["preferences"]))
    for prefs in (prefs_before, prefs_after):
        prefs.setdefault("sorting", {}).pop("chats", None)
    if prefs_before != prefs_after:
        errors.append("unrequested_sidebar_preference_change")
    if new["preferences"].get("sorting", {}).get("chats") != "updated_at":
        unknown.append("recency_sorting_not_verified")
    target_names = {t["name"] for t in plan["targets"]}
    def unrelated(data):
        return [sid for sid, s in data["sections"].items() if sid not in DEFAULTS and sid != "pinned" and s["name"] not in target_names]
    if unrelated(old) != unrelated(new):
        errors.append("unrelated_section_order_changed")
    desired = [t["name"] for t in plan["targets"] if t["state"] != "ambiguous"]
    actual = [s["name"] for sid, s in new["sections"].items() if sid not in DEFAULTS and sid != "pinned" and s["name"] in desired]
    if actual != desired:
        unknown.append("managed_section_order_or_creation_not_verified")
    return {"schemaVersion": 1, "status": "failed" if errors else "incomplete" if unknown else "metadata_verified",
            "confirmedMoves": confirmed, "errors": errors, "unverified": unknown,
            "historyComplete": False, "uiPlacement": "unverified", "collapse": "unverified", "opening": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    planner = sub.add_parser("plan", help="Generate a read-only plan")
    planner.add_argument("--input", required=True, type=Path)
    planner.add_argument("--language", choices=LABELS, default="zh")
    checker = sub.add_parser("verify", help="Verify observed metadata against a plan")
    for name in ("before", "after", "plan"):
        checker.add_argument("--" + name, required=True, type=Path)
    for command in (planner, checker):
        command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
    try:
        inputs = [args.input] if args.command == "plan" else [args.before, args.after, args.plan]
        if args.output.resolve() in {path.resolve() for path in inputs}:
            raise ValueError("Output must not overwrite an input snapshot")
        result = build_plan(read(args.input), args.language) if args.command == "plan" else verify(read(args.before), read(args.after), read(args.plan))
        # Exclusive creation avoids accidental overwrites of a previous private receipt.
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"reportWritten": True, "status": result.get("status", "planned"),
                          "moves": len(result.get("moves", result.get("confirmedMoves", [])))}, ensure_ascii=False))
        return 0 if result.get("status", "planned") in {"planned", "metadata_verified"} else 2
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Cannot produce report: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
