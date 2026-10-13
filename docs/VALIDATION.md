# Validation scope — 0.1.3

## Development branch: CLI session catalog

The CLI extension adds 38 synthetic tests (99 total) for the native JSONL handshake,
paginated metadata listing, all-provider queries, optional index-only mode,
timeouts and subprocess cleanup, independent group storage, command selection,
TTY handling, safe argument passing, and resume dry runs. The existing 61 desktop
tests remain unchanged. Both extracted release packages load the CLI and its
dependencies and run a local group-list smoke check without accessing an account.

On macOS with Codex CLI 0.133.0, native listing and a resume dry run were verified.
The real interactive resume was not launched. The installed CLI required an explicit
temporary `model_reasoning_effort="xhigh"` override for a configuration using `ultra`.
The first index-only read was empty; normal native scan-and-repair found available
sessions. Listing therefore defaults to the official scan-and-repair behavior,
with `--index-only` available explicitly. App-server needs permission to maintain
its own state database even when the organizer only requests metadata.

CLI groups were tested with synthetic identities in temporary files. No real
desktop groups or session content were changed by the organizer. Returned records
cover the current Codex home and selected filters, not other computers or all
account history. Saved CLI groups remain independent of desktop sections.

The workflow was designed against native desktop tool schemas observed on 2026-10-11. It does not guarantee that another account, platform, client version, or session exposes those tools. Discovery and capability checks are mandatory at runtime.

## 0.1.3 refresh checks

The 61-test suite includes 12 new refresh tests: stable repeated reads, missing baseline, recent-window eviction, manual membership removal, source outage/recovery, unknown availability shape, content/timestamp projection, pins and project members, invalid/duplicate metadata, Codex-only changes, exclusive CLI output, and incomplete CLI status during outages. Both fresh-extracted ZIPs run `refresh-check` and assert zero actions/deletions and explicit unsupported deletion sync. The skill validator and isolated native plugin installation passed on Windows.

Two real native observations on 2026-10-11 each listed 24 ChatGPT chats in the mixed recent window and 20 distinct ChatGPT section references. One reference was not listed; it stayed unchanged and was not classified as deleted. The second comparison reported `changed: false`, zero actions, and unsupported deletion sync. Separate native readback confirmed six custom sections, 23 projects, and six pins were unchanged. This is a refresh-observation regression, not an end-to-end deletion test.

Inspection of the installed Windows desktop 26.1007.2314.0 found that native ChatGPT list/read handlers can use cached queries. Moving a ChatGPT chat requires loading the conversation first. The exposed native tools provide no forced-refresh parameter, authoritative deletion event, or independent single-reference cleanup operation. The plugin therefore implements observation only. It does not alter client internals, probe private HTTP APIs, or delete a chat to manufacture an end-to-end test.

Background monitoring uses an explicitly requested native thread heartbeat; the package includes instructions, not a bundled daemon. Registration of a schedule is distinct from observing a later scheduled execution. No automatic deletion synchronization, complete historical coverage, UI disappearance, or fixed synchronization delay has been verified.

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

A read-only preview against the author's current native desktop lists confirmed that the helper accepts the live metadata layout, preserves existing groups, and reports unmatched identities as skipped. That initial preview did not perform sidebar mutations. Real account snapshots were kept outside this repository and are not distributed.

## 0.1.1 live regression and new tests

On 2026-10-11, two independent live runs each used fresh `list_projects` / `list_threads` observations and freshly captured local membership evidence before and after planning. The section record contained the canonical chat ID while the native list exposed a temporary alias; both runs resolved that membership with no title matching. Both reported 0 new groups, 0 requested moves, 0 verification errors, and `operationChecksPassed: true`. The five existing group IDs/order, 23 project paths/hosts, six pinned items/order, and observed chat project membership were unchanged. These were real no-op organization runs against an already-organized sidebar, not newly created test chats.

Twenty pre-existing unresolved backing records remained excluded. Consequently the overall result intentionally stayed `incomplete`, with `plan_contains_skipped_items` and `historyComplete: false`; the temporary-ID regression itself passed. UI opening, folding, complete history, and other clients' state schemas were not part of this regression.

The 0.1.1 suite had 37 tests. Added scenarios cover matching persisted membership, ghost Recents entries, unproven aliases blocking moves, fresh evidence across two passes, native graduation to canonical IDs, stale hashes, conflicting members, duplicate scopes, pins, remote hosts, missing identities, read-only state handling, and exclusion reporting. Both extracted ZIPs also exercise the new `capture-identity` command on synthetic data.

## 0.1.2 cloud identity regression

The 20 previously excluded records were individually read at their native `durable` host in a separate investigation. The installed Windows desktop 26.1007.2314.0 treats this routing host as cloud execution, while its sidebar can store an internal local-prefixed key. They were filed into a separate Codex Cloud Chats group through native tools before this release's regression runs. No physical creation device or ChatGPT conversation mapping was inferred.

Two independent live no-op organization runs on 2026-10-11 used the new helper against those already-filed records. Each run obtained new native lists and 20 fresh `read_thread` identity projections before planning, then new lists and another 20 fresh reads after planning: 80 per-record reads in total. Each snapshot also independently reconciled the existing temporary client ID. No conversation bodies were retained in the private evidence files.

| Live pass | Proven cloud records before / after | New groups | Moves | Exclusions | Check errors |
|---|---:|---:|---:|---:|---:|
| 1 | 20 / 20 | 0 | 0 | 0 | 0 |
| 2 | 20 / 20 | 0 | 0 | 0 | 0 |

Both reports returned `metadata_verified` and `operationChecksPassed: true`. Six existing custom group IDs/order, 23 project records, six pins/order, and observed project memberships were preserved. No artificial test chats were created or moved out and back to manufacture activity. Full history, UI visibility, opening, automatic collapse, and cross-device synchronization remain unverified by these metadata tests.

The suite now has 49 tests, adding cloud routing/storage-key separation, fresh evidence and repeat-run behavior, missing or stale evidence, failed after-readback, cross-host collisions, duplicate reads and native identities, conflicting memberships, unavailable sources, protected groups/pins/projects, metadata-only exports, and composition with temporary-ID evidence. Both release ZIPs are fresh-extracted and exercise `capture-cloud`, plan, verify, and a zero-change repeat plan. The isolated Codex marketplace install check also compares installed plugin bytes with source.

## Manual desktop acceptance

This is a checklist for a willing tester, not a claim that these checks have already passed on every client:

1. Confirm the installed skill appears in a fresh desktop session and the required native tools are exposed.
2. Preview a small sample including a pinned item, a project-owned chat, an unassigned local chat, a cloud chat, and a manually grouped item.
3. Apply with native tools; check the intended placements, preserved relations, and recent-update order.
4. Open a representative project and chat. Expand/collapse sections using the supported UI. Record unavailability honestly.
5. Run again: no duplicates or changes to previously filed items. Add a new unassigned chat and verify that only it is filed.
6. Verify that older history is explicitly reported as uncovered when enumeration is unavailable. Test partial failure on an unavailable host without changing unrelated items.

Do not use a populated private account for automated mutation tests. Do not attach real snapshots to public issues. Report tool names, client versions, sanitized schema shapes, and synthetic reproductions instead.
