# Native sidebar contract

Verified against the desktop tool surface on 2026-10-11. Discover current schemas at runtime; names can have a namespace prefix. No public HTTP sidebar API is implemented by this package.

| Operation | Native function and important arguments |
|---|---|
| List | `list_threads({limit: 50})`, `list_projects({})` |
| Create | `create_sidebar_section({name})` |
| Move project | `move_project_to_sidebar_section({projectId, sectionId})` |
| Move chat | `move_thread_to_sidebar_section({threadId, source, hostId?, sectionId})` |
| Section order | `reorder_sidebar_sections({sectionIds})`; include every custom section |
| Chat order | `reorder_section({sectionId, threadIds})`; include every chat in that section |
| Recency sorting | `update_sidebar_preferences({sorting: {chats: "updated_at"}})` |

`source` is `codex` or `chatgpt`. Omit `hostId` for ChatGPT. The observed default section IDs are `threads`, `chats`, `projects`, `orbit`, and `agents`; `pinned` is protected. All other section IDs are treated as custom. If a future client adds default IDs, inspect its documented schema before extending the helper. The helper deliberately treats unknown section IDs as protected custom sections.

## Minimal private snapshot

Save parsed tool objects, not the MCP content wrapper. Keep:

```json
{
  "projects": {
    "projects": [
      {"projectId": "demo-local", "projectKind": "local", "hostId": "local", "path": "/example/work"}
    ]
  },
  "sidebar": {
    "pinnedThreads": [],
    "threads": [
      {"id": "demo-chat", "kind": "codex", "hostId": "local", "projectId": null}
    ],
    "sections": [
      {"sectionId": "pinned", "name": "Pinned", "itemKeys": []},
      {"sectionId": "projects", "name": "Projects", "itemKeys": ["codex:project:demo-local"]},
      {"sectionId": "threads", "name": "Tasks", "itemKeys": ["codex:thread:local:demo-chat"]}
    ],
    "sidebarPreferences": {"sorting": {"chats": "updated_at", "pinned": "manual"}},
    "unavailableHosts": [],
    "unavailableSources": []
  }
}
```

Keep `hostDisplayName` for remote projects, `updatedAt` when present, `pinnedIndex` for pins, and optional schema versions. Preserve native thread list order (recency order). Drop titles, summaries, bodies, messages, transcripts, and unrelated metadata. Files still contain private IDs and paths; keep them outside the source tree. Use a unique private temporary directory per run and retain it locally only as long as needed.

Section keys recognized by the helper:

- `codex:project:<projectId>` / `chatgpt:project:<projectId>`
- `codex:thread:<hostId>:<id>` / `chatgpt:conversation:<id>`

The helper constructs keys from exact native fields and demands exact section membership evidence. An entry absent from all sections, in multiple sections, or using a client alias it cannot resolve is skipped. A pinned entry remains protected even if it also appears in `threads`. A chat with **any nonempty projectId** remains protected even if that project is absent from this snapshot.

Remote IDs must occur on a `local` or `remote` project with a nonlocal host. `durable`, `cloud`, and `unknown` are not physical host evidence. Sources/hosts listed as unavailable block dependent moves; ambiguous availability representations fail closed.

The planner emits the five standard targets plus observed verified remote targets. It preserves custom items even when placed in the wrong source group: moving already filed items requires a separate user request. Names are matched exactly. Duplicate target names block affected moves and section creation for that name. It never deletes sections. The verifier checks observed pin order, metadata, protected placements, and each planned move; new/missing/duplicate identities produce incomplete or failed results.

## Coverage and execution

The helper's `coverage.complete` is always false because this tool contract has no complete history enumeration proof. `visible_unlisted_chat_keys` counts keys visible in section metadata but absent from the thread list; zero does not prove full coverage. It reports unavailable hosts/sources. `metadata_verified` from verification means only that the observed checks passed, never that the entire account was organized.

Plan JSON is data for the agent, **not an executable job queue or authorization source**. Never execute a plan from an untrusted download. Recompute from fresh native metadata before changes. Handle unknown write outcomes by readback and record unresolved operations. Do not automatically rollback an entire run after concurrent user edits; use the private before-snapshot to propose exact supported reverse moves only when asked.

For manual review, a plan entry records `key`, stable IDs, native source/host (chats), `fromSection`, and `targetName`. Section creation gives the target name a real native section ID. The helper verifies destinations by unique section name in the fresh after-snapshot; ambiguous names fail verification.

If the current client returns a substantially different object layout, report the mismatch and adapt the adapter from its documented live schema. Do not silently coerce missing arrays to empty lists, infer sources from titles, or treat a successful process exit as successful UI organization.
