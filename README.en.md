# Sidebar Organizer

[中文](README.md) · [Download ZIPs](https://github.com/VeraPyuyi/codex-sidebar-organizer/releases/latest)

A skills-only plugin that files desktop projects and chats into native sections by verified source. No server, API key, or extra MCP service. “Archive” means sidebar filing here: it does not hide, delete, or archive conversations.

## Install

With a Codex version supporting plugin commands:

```sh
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.1
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

Open a fresh **Codex desktop session**, select `organize-sidebar` (or `sidebar-organizer:organize-sidebar` when namespaced), and say:

```text
Use $organize-sidebar to organize my projects and chats by source. Preserve pins and project membership.
```

For a preview, add “Preview only; do not move anything.” Run again to file new items. Existing manual groups remain intact. The default uses recent-update chat sorting, a shared sidebar preference; pinned sorting and the current grouping mode are preserved.

If `plugin add` is unavailable, add the marketplace and install Sidebar Organizer from the desktop Plugins Directory. Alternatively, download `organize-sidebar-skill-0.1.1.zip`, extract it, and copy the complete `organize-sidebar` folder into `~/.codex/skills/` (Windows: `%USERPROFILE%\.codex\skills\`; use your configured Codex home if different). Back up an existing folder before replacing it. Start a fresh desktop session. Install either the plugin or standalone skill, not both.

The separate `sidebar-organizer-plugin-0.1.1.zip` contains a standard plugin directory for clients supporting ZIP import or custom marketplaces. It is not the standalone skill folder.

### Upgrade from 0.1.0

If you installed with `--ref v0.1.0`, replace this plugin's marketplace registration and reinstall. Adding the new ref directly may fail because the registered source differs. This locally verified sequence preserves chats and sections:

```sh
codex plugin marketplace remove sidebar-organizer-marketplace
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.1
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

Open a fresh desktop session to load the updated skill. Standalone skill users should back up and replace the skill folder instead.

## Behavior

- Creates/reuses Local Projects, ChatGPT Cloud Projects, Local Chats, ChatGPT Cloud Chats, and Source Unconfirmed sections, with separate verified remote-host sections when applicable.
- Preserves pinned items and their order, project membership, paths, and existing custom groups.
- Skips ambiguous identities, unavailable sources, duplicate target names, and unroutable backing records.
- Rechecks metadata after changes and reports moved, protected, skipped, and unverified items.
- Uses native collapse controls; automatic collapse depends on permitted UI/tool capabilities.

## Requirements and limits

Run in a desktop session exposing native sidebar list/create/move tools. Installing this package does not provide those capabilities in standalone CLI, ChatGPT web, or unsupported desktop versions. The CLI commands above install the package; they do not organize the sidebar.

The tested list tool returns up to 50 recent non-pinned chats and has no history cursor. The skill checks for supported history enumeration, but reports older history as **not covered, total unknown** when unavailable. A cloud record does not identify a creation browser or computer; “local” means the current execution host. Unknown physical provenance is not guessed from titles.

Metadata verification does not prove visible placement, opening, or collapsed state. Without a supported UI surface, click section headings to collapse them manually. Cross-device synchronization and background scheduling are outside this version's scope.

## Privacy and validation

Version 0.1.1 fixes temporary `client-new-thread:` IDs using a read-only local membership check. When needed, the optional helper loads the current Codex home's `.codex-global-state.json` and exports only a uniquely matching set of custom-section IDs, names, and members. It never writes client state or guesses identity from titles. This is a version-sensitive compatibility adapter; missing or conflicting evidence blocks affected moves. Evidence is freshly captured before and after each run.

Two independent live Windows passes each reconciled the already-filed chat with zero new groups, zero moves, and zero operation-check errors. Existing sections, pins, and project membership stayed unchanged. Previously unresolved records and older history remain explicitly outside coverage; operation success is reported separately from overall completeness.

No telemetry, credentials, network client, or remote service is bundled. Native host tools perform changes. Private metadata snapshots may be saved temporarily on the user's computer for verification; never publish them. Conversation bodies are unnecessary. The host's own service and data handling still apply.

The optional Python 3.10+ standard-library helper only plans and verifies; it cannot move sidebar items. If Python is missing, the agent can follow the skill directly. All tests use synthetic data.

```sh
python -m unittest discover -s tests -v
python scripts/build_release.py
```

See [validation scope](docs/VALIDATION.md), [the skill](plugins/sidebar-organizer/skills/organize-sidebar/SKILL.md), and [the tool contract](plugins/sidebar-organizer/skills/organize-sidebar/references/native-tools.md). Packaging follows the [official plugin documentation](https://developers.openai.com/plugins/build/plugins). This is an independent community project, not affiliated with OpenAI. MIT licensed.
