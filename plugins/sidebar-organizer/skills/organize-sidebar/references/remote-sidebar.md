# Top-level Remote desktop sections

This development-branch layout puts each verified remote host in its own native sidebar section alongside Projects and Recents. The published v0.1.3 release does not include it. It uses existing desktop section tools; it does not add a new built-in sidebar category or change the application UI code.

```text
Projects
Recents
Remote · Devbox [host-a]
  Project A
    Project A's existing chats
  Chat without a project
Remote · Workstation [host-b]
```

This illustrates the intended hierarchy, not a live UI verification. Each host heading is a top-level custom section. Project nodes keep their identity, path, host, and chats. A chat without a project is a direct section member; the organizer does not manufacture project membership or nested sections. The English naming template is `Remote · {display} [{hostId}]`; Chinese uses `远程 · {display} [{hostId}]`. The native host ID suffix keeps machines with the same display name separate.

## Prerequisites and scope

The current desktop session must expose `list_projects`, `list_threads`, `create_sidebar_section`, `move_project_to_sidebar_section`, and `move_thread_to_sidebar_section`. Discover and read current schemas. If those tools are unavailable, report that desktop changes were not applied; do not edit application state or use an unsupported UI surface.

The host and remote projects must already be registered with the desktop app. Following the [official SSH setup](https://learn.chatgpt.com/docs/remote-connections#connect-to-an-ssh-host), confirm normal SSH access and authenticated remote Codex, then add or enable the host in **Settings > Connections** and select a remote project folder. The desktop's native project records must corroborate the nonlocal host ID. `durable`, `cloud`, and `unknown` are not physical remote host identities.

The separate [SSH CLI catalog](cli.md#remote-sessions-over-ssh) can list a host before desktop registration. Its SSH alias, session UUID, and working directory do not establish native desktop identity. This workflow does not import logs, copy sessions, map identities by title/cwd, or guarantee that every old remote CLI session appears in desktop Recents.

Select host mode when the user requests Remote headings alongside Projects and Recents. A request to organize already authorizes the reversible section moves; state the concrete plan and proceed. A preview request authorizes no mutations. Scope to named hosts when requested, using exact native IDs from the current metadata. If the metadata cannot identify the requested host uniquely, leave it unchanged and report the missing evidence.

## Plan

Read fresh native project and sidebar metadata into the private snapshot format described in [the tool contract](native-tools.md). Keep snapshots outside the repository. The optional Python helper creates a plan only:

```sh
python <skill-dir>/scripts/sidebar_plan.py plan \
  --input <private-dir>/before.json \
  --output <private-dir>/plan.json \
  --language en \
  --remote-layout host \
  --host-id host-a
```

Replace `host-a` with the verified native host ID. Repeat `--host-id` to select multiple hosts. Omit it to consider all verified remote hosts. The mode is deliberately limited to remote hosts; it does not create local, cloud, or Source Unconfirmed groups.

Host mode emits schema 4 with `remoteLayout: "host"`, `hostIds`, and `sorting: {}`. The default source-based layout remains `--remote-layout split` with schema 3. Keep the selected plan for verification; do not substitute the default layout on readback.

The planner moves only entries with an unambiguous identity and default-section membership. It preserves pins, every nonempty chat `projectId`, and all existing custom placements, including old split remote project/chat groups. Changing modes does not migrate those older groups. It reuses a unique exact-name destination and creates a missing destination only when an eligible move needs it. Duplicate names, ambiguous identities, unavailable hosts, and unknown source shapes block affected moves. No eligible items means no empty new section.

## Apply and verify

1. Re-read relevant native metadata and recompute if it changed. State which verified hosts and how many projects/chats are in scope.
2. Call `create_sidebar_section({name})` for each required missing host section, one at a time, saving the returned section ID. If a write outcome is unknown, re-list before retrying.
3. Move the existing project nodes with `move_project_to_sidebar_section({projectId, sectionId})`. Move eligible chats with `move_thread_to_sidebar_section({threadId, source: "codex", hostId, sectionId})`, using the exact native IDs. Preserve the original project membership; never call `move_thread_to_project`.
4. Process chat moves oldest observed first when native moves prepend. Reorder a section only with a complete member list, and preserve unrelated section order. No preference write is requested: `sorting: {}` means do not call `update_sidebar_preferences`.
5. Read both lists again. Verify destinations, unchanged paths/hosts/project membership, pins, manual groups, out-of-scope items, and all sidebar preferences. Run the helper's `verify` with the same plan, then regenerate a host-mode plan from fresh metadata to check repeat-run behavior.

```sh
python <skill-dir>/scripts/sidebar_plan.py verify \
  --before <private-dir>/before.json \
  --after <private-dir>/after.json \
  --plan <private-dir>/plan.json \
  --output <private-dir>/verification.json
```

Report observed moves, preserved and unresolved items, and history coverage separately. Native recent-list limits still apply. Metadata success does not prove visible placement, expansion, or opening; check those only through supported navigation or a permitted UI surface. No native write means no claim that a Remote section has appeared. The development checks use synthetic metadata; real desktop creation and opening remain a manual acceptance step.
