# Sidebar Organizer

[中文](README.md) · [Download ZIPs](https://github.com/VeraPyuyi/codex-sidebar-organizer/releases/latest)

A skills-only plugin that files desktop projects and chats into native sections by verified source. No server, API key, or extra MCP service. “Archive” means sidebar filing here: it does not hide, delete, or archive conversations.

The development branch also includes [top-level Remote desktop sections](#top-level-remote-desktop-sections-development-branch) and a [CLI session catalog](#cli-session-catalog-development-branch) for browsing, grouping, and resuming local or SSH remote sessions. The published GitHub v0.1.3 release does not include these new features.

## Install

With a Codex version supporting plugin commands:

```sh
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.3
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

Open a fresh **Codex desktop session**, select `organize-sidebar` (or `sidebar-organizer:organize-sidebar` when namespaced), and say:

```text
Use $organize-sidebar to organize my projects and chats by source. Preserve pins and project membership.
```

For a preview, add “Preview only; do not move anything.” Run again to file new items. Existing manual groups remain intact. The default source layout uses recent-update chat sorting, a shared sidebar preference; pinned sorting and the current grouping mode are preserved. The Remote layout below preserves all sorting preferences.

If `plugin add` is unavailable, add the marketplace and install Sidebar Organizer from the desktop Plugins Directory. Alternatively, download `organize-sidebar-skill-0.1.3.zip`, extract it, and copy the complete `organize-sidebar` folder into `~/.codex/skills/` (Windows: `%USERPROFILE%\.codex\skills\`; use your configured Codex home if different). Back up an existing folder before replacing it. Start a fresh desktop session. Install either the plugin or standalone skill, not both.

The separate `sidebar-organizer-plugin-0.1.3.zip` contains a standard plugin directory for clients supporting ZIP import or custom marketplaces. It is not the standalone skill folder.

### Upgrade from an older release

If you installed with an older version tag, replace this plugin's marketplace registration and reinstall. Adding the new ref directly may fail because the registered source differs. This locally verified sequence preserves chats and sections:

```sh
codex plugin marketplace remove sidebar-organizer-marketplace
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.3
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

Open a fresh desktop session to load the updated skill. Standalone skill users should back up and replace the skill folder instead.

## Top-level Remote desktop sections (development branch)

This layout creates one native sidebar section per remote host, alongside **Projects and Recents**. It holds the host's existing project nodes and chats without a project. Chats already assigned to a project keep that membership:

```text
▸ Projects
▸ Recents
▾ Remote · Devbox [host-a]
    ▸ Project A
        Project A chat
    Chat without a project
▸ Remote · Workstation [host-b]
```

This is a layout illustration, not a verified screenshot. Section names follow the request language, with a stable host ID suffix to distinguish machines sharing a display name. The layout does not create folders under Projects, assign chats to new projects, or create nested sections.

First follow the [official remote connection setup](https://learn.chatgpt.com/docs/remote-connections#connect-to-an-ssh-host): add or enable the SSH host in the desktop app's **Settings → Connections**, then choose a remote project folder. In a desktop session that exposes native sidebar tools and has loaded this development branch's skill, ask:

```text
Use $organize-sidebar to put each connected remote host in a top-level Remote section alongside Projects and Recents. Preserve project membership.
```

Name a registered host to limit the operation, or add “Preview only; do not move anything.” This mode only handles remote hosts verified by native desktop project metadata. It preserves pins, manual groups, existing split remote project/chat sections, and all global sorting preferences. It creates no empty sections when nothing can move, and adds no local or cloud sections.

The SSH CLI catalog does not import sessions into the desktop. Moves require identities exposed by native desktop lists; an SSH alias, working directory, or CLI session ID cannot substitute for that evidence. Missing tools are reported as unavailable. See [Remote section usage](plugins/sidebar-organizer/skills/organize-sidebar/references/remote-sidebar.md) for planning and verification. Validation currently covers synthetic metadata; visible desktop placement and opening still require manual acceptance.

## CLI session catalog (development branch)

Requires Python 3.10+ and a Codex CLI supporting `codex app-server`. From the repository root:

```sh
python3 scripts/session_cli.py list --group-by project
python3 scripts/session_cli.py list --group-by source --source cli
python3 scripts/session_cli.py browse
python3 scripts/session_cli.py group add "Research" SESSION_ID
python3 scripts/session_cli.py list --group-by group
python3 scripts/session_cli.py resume SESSION_ID --dry-run
python3 scripts/session_cli.py resume SESSION_ID
```

In an interactive terminal, `browse` lets you select a session by number and runs `codex resume`. Replace `SESSION_ID` with a listed ID; `resume` also accepts a unique ID prefix. The default catalog includes CLI, VS Code, exec, and app-server sessions, excluding subagents. Projects use exact working directories; source means the session entry point, not its physical creation computer.

Custom groups live in a separate local JSON file, scoped by `CODEX_HOME`. By default, the catalog paginates available sessions in the selected Codex home and filters; the official app-server scans that host's logs and repairs its index. The organizer only projects returned metadata and does not directly parse or edit client files. Use `python3 scripts/session_cli.py --index-only list` to read only the existing state index, which may omit older, unindexed sessions.

Put global options before the subcommand. If your CLI rejects `ultra` in its configuration, use the temporary override `python3 scripts/session_cli.py -c 'model_reasoning_effort="xhigh"' list` without changing the config file. See [CLI usage](plugins/sidebar-organizer/skills/organize-sidebar/references/cli.md) for filters, storage, and running from an installed skill. The v0.1.3 installation commands above still install the released desktop plugin.

### SSH remote sessions

The local machine needs Python 3.10+ and OpenSSH. The remote machine needs an authenticated Codex CLI and a POSIX shell (Linux/macOS); it does not need this project or Python. First log in with `ssh devbox` to confirm the host key and set up key or SSH agent authentication, where `devbox` is your SSH configuration alias. The organizer uses noninteractive authentication: it does not prompt for passwords or automatically accept new host keys.

```sh
python3 scripts/session_cli.py --host devbox list --source cli
python3 scripts/session_cli.py --host devbox group add "Research" SESSION_ID
python3 scripts/session_cli.py --host devbox browse --group "Research"
python3 scripts/session_cli.py --host devbox resume SESSION_ID --dry-run
```

`browse` and `resume` use interactive SSH to continue in the remote session's original working directory. If the remote noninteractive shell cannot find `codex`, pass `--codex /absolute/path/to/codex`. Select another remote Codex home with `--remote-home /home/user/.codex-other`. Remote `--cwd` also requires an absolute POSIX path; `-c` overrides apply to the remote Codex process.

Each command targets one host. Remote groups stay on the local machine, scoped by the effective SSH hostname, user, port, and actual remote `CODEX_HOME`. The catalog does not combine machines, copy session logs, or sync desktop groups. `--dry-run` connects to list sessions and check the remote working directory, then prints the resume command without starting a conversation.

For MFA such as Duo, authenticate in your own terminal first, then reuse the connection with `--ssh-control-path PATH`. See [SSH usage](plugins/sidebar-organizer/skills/organize-sidebar/references/cli.md#remote-sessions-over-ssh) for commands to create and close a private socket.

Future design notes distinguish VPN access, standalone campus servers, and HPC compute nodes: [remote access scenarios (Chinese)](docs/REMOTE_ACCESS_NOTES.md).

## Behavior

- Creates/reuses Local Projects, ChatGPT Cloud Projects, Local Chats, ChatGPT Cloud Chats, and Source Unconfirmed sections, with separate verified remote-host sections when applicable.
- Separately files Codex cloud execution records only after fresh, matching native per-record reads; internal local-prefixed storage keys never imply a creation device.
- Preserves pinned items and their order, project membership, paths, and existing custom groups.
- Skips ambiguous identities, unavailable sources, duplicate target names, and unroutable backing records.
- Rechecks metadata after changes and reports moved, protected, skipped, and unverified items.
- Uses native collapse controls; automatic collapse depends on permitted UI/tool capabilities.

## Requirements and limits

Desktop organization requires a desktop session exposing native sidebar list/create/move tools. Installing this package does not provide those capabilities in standalone CLI, ChatGPT web, or unsupported desktop versions. The `codex plugin` commands install the package; the development branch's CLI catalog uses separate groups.

The tested list tool returns up to 50 recent non-pinned chats and has no history cursor. The skill checks for supported history enumeration, but reports older history as **not covered, total unknown** when unavailable. A cloud record does not identify a creation browser or computer; “local” means the current execution host. Unknown physical provenance is not guessed from titles.

Metadata verification does not prove visible placement, opening, or collapsed state. Without a supported UI surface, click section headings to collapse them manually. Cross-device and web-deletion synchronization are unsupported. Background observation is opt-in through native automation.

## Refresh checks in 0.1.3

Ask “Use $organize-sidebar to check sidebar references” for a one-off observation, or “Check my sidebar every hour in the background and notify me only about new issues” to opt into a native thread heartbeat. Repeated requests reuse a matching automation. Installing the plugin alone enables no background tasks.

The new `refresh-check` command compares metadata only, with zero groups, moves, or deletions. It reports references missing from the limited recent list as **uncertain**, never as deleted. Cache freshness, complete history, and deletion status cannot be established by the tested tools; neither forced cache refresh nor independent stale-reference cleanup is available. This does **not** make web-deleted chats automatically disappear from the desktop. It never edits client state to bypass this limitation. Background execution depends on the host automation runtime and does not promise a sync deadline. See the [refresh procedure](plugins/sidebar-organizer/skills/organize-sidebar/references/refresh.md).

## Codex cloud records in 0.1.2

Fresh native `read_thread` metadata verifies each `codex` / `durable` identity against the list and its unique sidebar membership. The optional helper binds those projections to the exact snapshot and normalizes storage keys only in memory. Proven unfiled records use the optional **Codex Cloud · Chats** section; existing groups are reused, manual groups remain intact, and unproven records stay unchanged. Each before/after check and repeat run requires fresh evidence. Cloud execution does not establish the computer or browser where a chat was created.

Two live Windows passes each verified all 20 scoped cloud records before and after, with zero new groups, moves, exclusions, or verification errors. Six existing custom groups, 23 projects, and six pins were preserved. The 49-test suite and fresh-extracted ZIP checks cover the cloud workflow and its failure cases; see [validation scope](docs/VALIDATION.md).

## Privacy and validation

Version 0.1.1 fixes temporary `client-new-thread:` IDs using a read-only local membership check. When needed, the optional helper loads the current Codex home's `.codex-global-state.json` and exports only a uniquely matching set of custom-section IDs, names, and members. It never writes client state or guesses identity from titles. This is a version-sensitive compatibility adapter; missing or conflicting evidence blocks affected moves. Evidence is freshly captured before and after each run.

The earlier 0.1.1 live Windows passes each reconciled the already-filed temporary-ID chat with zero new groups, zero moves, and zero operation-check errors. Existing sections, pins, and project membership stayed unchanged. Its 20 previously excluded records are now covered by the separate 0.1.2 cloud regression. Older history remains outside coverage; operation success is reported separately from overall completeness.

No telemetry, credentials, or remote service is bundled. Native desktop tools perform sidebar changes; the CLI catalog reads metadata through local `codex app-server` or a remote app-server over system OpenSSH. Private metadata snapshots may be saved temporarily on the user's computer for verification; never publish them. Native identity reads may also return messages; the desktop workflow projects only identity fields and does not use or retain bodies. The CLI catalog does not read full conversations or display message previews; it displays session names, or `Untitled` when absent. The host's own service and data handling still apply.

The optional desktop helper `sidebar_plan.py` uses Python 3.10+ and the standard library to plan and verify; it cannot move sidebar items. If Python is missing, the agent can follow the desktop skill directly. The CLI catalog requires Python. All tests use synthetic data.

```sh
python -m unittest discover -s tests -v
python scripts/build_release.py
```

See [validation scope](docs/VALIDATION.md), [the skill](plugins/sidebar-organizer/skills/organize-sidebar/SKILL.md), and [the tool contract](plugins/sidebar-organizer/skills/organize-sidebar/references/native-tools.md). Packaging follows the [official plugin documentation](https://developers.openai.com/plugins/build/plugins). This is an independent community project, not affiliated with OpenAI. MIT licensed.
