# Validation scope — 0.1.0

The workflow was designed against native desktop tool schemas observed on 2026-10-11. It does not guarantee that another account, platform, client version, or session exposes those tools. Discovery and capability checks are mandatory at runtime.

## Automated checks

`python -m unittest discover -s tests -v` exercises synthetic scenarios:

- Local/cloud classification and separate verified remote hosts with identical display names.
- Pinned chats/projects, project-owned chats including missing project records, and manual groups preserved.
- Duplicate names/IDs, missing or multiple memberships, unavailable sources/hosts, unknown schemas, and synthetic hosts handled conservatively.
- Repeated runs produce no extra moves or groups; later new chats are the only additions.
- Native prepend behavior preserves observed recency when applying oldest first.
- Titles cannot change provenance or supply instructions to the planner.
- Readback detects failed destinations, changed membership/paths/pins/preferences, missing records, and unplanned changes to older entries.
- Stale/tampered plans and report overwrites are rejected; input snapshots remain unchanged.
- Coverage never claims complete history; metadata checks never claim UI/collapse/opening success.

`python scripts/build_release.py` validates the manifest/marketplace/skill metadata, packages an explicit file allowlist, and fresh-extracts both archives. It imports and runs the shipped planner/verifier on synthetic data. Archive names, sizes, and SHA-256 values are recorded in `SHA256SUMS.txt` (hashes and names) and build output (sizes).

GitHub Actions runs these checks on Windows and Linux. The optional helper has no third-party dependencies; no real account is needed for these checks.

The initial Windows release checks passed with Codex CLI 0.144.1: `python scripts/check_local_install.py` added the local marketplace and installed the plugin using a separate temporary configuration, then confirmed the installed skill bytes matched the source. This did not change the user's installed plugins. The portable manifest also passed the published Agent Plugins 1.0 JSON schema; the skill passed the bundled Skill Creator validator using Python UTF-8 mode.

A read-only preview against the author's current native desktop lists confirmed that the helper accepts the live metadata layout, preserves existing groups, and reports unmatched identities as skipped. No real sidebar mutations were performed to test the released skill. Real account snapshots were kept outside this repository and are not distributed.

## Manual desktop acceptance

This is a checklist for a willing tester, not a claim that these checks have already passed on every client:

1. Confirm the installed skill appears in a fresh desktop session and the required native tools are exposed.
2. Preview a small sample including a pinned item, a project-owned chat, an unassigned local chat, a cloud chat, and a manually grouped item.
3. Apply with native tools; check the intended placements, preserved relations, and recent-update order.
4. Open a representative project and chat. Expand/collapse sections using the supported UI. Record unavailability honestly.
5. Run again: no duplicates or changes to previously filed items. Add a new unassigned chat and verify that only it is filed.
6. Verify that older history is explicitly reported as uncovered when enumeration is unavailable. Test partial failure on an unavailable host without changing unrelated items.

Do not use a populated private account for automated mutation tests. Do not attach real snapshots to public issues. Report tool names, client versions, sanitized schema shapes, and synthetic reproductions instead.
