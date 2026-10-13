"""Private, independent CLI groups; stores only scope, group names and thread IDs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable
import unicodedata


class GroupError(Exception):
    """Group data is invalid or cannot be safely read or changed."""


def _text(value: str, label: str, *, identifier: bool = False) -> str:
    if (not isinstance(value, str) or not value.strip()
            or any(unicodedata.category(c).startswith("C") or c in "\u2028\u2029" for c in value)):
        raise GroupError(f"{label} must be nonempty text without control characters.")
    if identifier and (value.startswith("-") or any(c.isspace() for c in value)):
        raise GroupError("Thread IDs cannot contain whitespace or start with '-'.")
    return value


def _ids(values: Iterable[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise GroupError("Thread IDs must be a sequence of strings.")
    try:
        return list(dict.fromkeys(_text(value, "Thread ID", identifier=True) for value in values))
    except TypeError as exc:
        raise GroupError("Thread IDs must be a sequence of strings.") from exc


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GroupError("Group data has duplicate JSON keys; refusing to overwrite it.")
        result[key] = value
    return result


class GroupStore:
    """Each thread has at most one manual group within its CODEX_HOME scope."""

    def __init__(self, path: Path, scope: str):
        self.path = Path(path)
        self.scope = _text(scope, "Scope")
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    def _load(self) -> dict:
        if self.path.is_symlink():
            raise GroupError("Group data file must not be a symbolic link.")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except FileNotFoundError:
            return {"schemaVersion": 1, "scopes": {}}
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GroupError(f"Cannot read group data safely: {self.path} ({exc})") from exc
        if (not isinstance(data, dict) or set(data) != {"schemaVersion", "scopes"}
                or type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1
                or not isinstance(data["scopes"], dict)):
            raise GroupError("Unsupported or invalid group schema; refusing to overwrite it.")
        for scope, groups in data["scopes"].items():
            _text(scope, "Stored scope")
            if not isinstance(groups, dict):
                raise GroupError("Stored groups must be an object.")
            seen = set()
            for name, thread_ids in groups.items():
                _text(name, "Stored group name")
                if not isinstance(thread_ids, list):
                    raise GroupError("Stored thread IDs must be a list.")
                for thread_id in thread_ids:
                    _text(thread_id, "Stored thread ID", identifier=True)
                    if thread_id in seen:
                        raise GroupError("A stored thread ID appears more than once in its scope.")
                    seen.add(thread_id)
        return data

    def groups(self) -> dict[str, list[str]]:
        return self._load()["scopes"].get(self.scope, {})

    def group_for(self, thread_id: str) -> str | None:
        _text(thread_id, "Thread ID", identifier=True)
        return next((name for name, ids in self.groups().items() if thread_id in ids), None)

    def assign(self, name: str, ids: Iterable[str]) -> None:
        _text(name, "Group name")
        thread_ids = _ids(ids)
        selected = set(thread_ids)

        def change(groups: dict) -> None:
            for other_name in groups:
                if other_name != name:
                    groups[other_name] = [i for i in groups[other_name] if i not in selected]
            members = groups.setdefault(name, [])
            members.extend(i for i in thread_ids if i not in members)

        self._update(change)

    def unassign(self, ids: Iterable[str]) -> None:
        selected = set(_ids(ids))

        def change(groups: dict) -> None:
            for name in groups:
                groups[name] = [i for i in groups[name] if i not in selected]

        self._update(change)

    def remove(self, name: str) -> None:
        _text(name, "Group name")
        self._update(lambda groups: groups.pop(name, None))

    def _prepare_parent(self) -> None:
        missing = []
        directory = self.path.parent
        while not directory.exists():
            missing.append(directory)
            directory = directory.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700, exist_ok=True)

    def _update(self, change: Callable[[dict], None]) -> None:
        try:
            self._prepare_parent()
            try:
                self.lock_path.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise GroupError(
                    f"Group data is locked: {self.lock_path}. Retry after the other command ends; "
                    "remove this lock only after confirming no organizer is writing."
                ) from exc
            try:
                data = self._load()
                change(data["scopes"].setdefault(self.scope, {}))
                self._save(data)
            finally:
                self.lock_path.rmdir()
        except OSError as exc:
            raise GroupError(f"Cannot update group data: {self.path} ({exc})") from exc

    def _save(self, data: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
