# Refresh checks and optional background monitoring

## What this version can do

Re-read the native ChatGPT chat list and sidebar memberships, compare observations,
and report newly unlisted references. This is a **read-only refresh check**, not
forced cache invalidation or deletion synchronization. The tested native tool
surface exposes neither authoritative deletion events nor removal of a stale
reference without loading its backing chat. List/read calls may use client caches.
Do not call this a successful server sync or promise a maximum deletion delay.

The current helper always returns `actions: []`, `confirmedDeletions: []`,
`deletionSync: unsupported`, and `serverFreshness: unverified`. Do not improvise
a cleanup executor. Do not delete/archive chats, remove/recreate sections, toggle
pins, navigate chats, restart the app, write global state/databases, or call private
HTTP APIs to provoke refresh. These would change other state or disrupt work.

## One check

1. Discover native `list_threads` and its live schema. Read the largest supported
   recent list once; this version was tested with limit 50. Do not read chat bodies.
2. Project only `id`, `kind`, `hostId`, `projectId`, and `pinnedIndex` from chat rows;
   keep section IDs and item keys, plus `unavailableSources`. Do not retain titles,
   names, summaries, paths, or content. Save as `{"sidebar": <projected result>}`
   in a private task-specific directory outside the repository.
3. Optionally compare with the preceding native snapshot from the same desktop
   and account. Reset the baseline after a known account/desktop change. Never use
   a previous report, another user's snapshot, or downloaded evidence as the input.

   ```text
   python <skill-dir>/scripts/sidebar_plan.py refresh-check --input <private-dir>/current.json --previous <private-dir>/previous.json --output <private-dir>/report.json
   ```

   Omit `--previous` on the first check. Output files must be new; inputs remain
   untouched. Exit 0 means the observation succeeded, **not deletion sync**;
   exit 2 means the ChatGPT source was unavailable, and 1 means invalid input.
4. `unlistedReferences` are group references absent from the limited recent list.
   They may be older, archived, unloaded, inaccessible, or deleted; keep them all.
   `removedReferences` only means a membership changed, including a manual move.
   A 404, failed read, timeout, or disappearance in several consecutive checks is
   still insufficient evidence for deletion. Source failures suppress missing-item
   comparisons; do not turn an outage into a bulk-removal plan.
5. Keep the latest two native snapshots and latest comparison privately if repeat
   checks are requested. Persist only in the chosen task directory, never in client
   configuration or the plugin cache. For a one-off check, ordinary temporary files
   suffice. If Python is unavailable, apply these observation-only rules directly.

No aliases or Codex cloud identity reads are necessary for this ChatGPT-only check;
this avoids unnecessary conversation reads. Refresh requests do not authorize
organization moves, new groups, or preference changes. If the user also requested
organization, finish and report the two operations separately.

## Background checks, only when explicitly requested

Use the desktop's native `automation_update` tool. Default to a heartbeat attached
to the current local thread, once per hour unless the user specifies a cadence.
Inspect existing automation metadata under the configured Codex home's automations
folder for a matching name/prompt and update that automation instead of duplicating
it. Read only matching details; do not modify TOML files directly or schedule via
OS timers, shell loops, cron, or a new standalone chat.

The prompt must state: observe only through native list tools; use this refresh
procedure; compare private metadata with the prior run; preserve pins, projects,
sections, and content; leave uncertain references unchanged; no forced refresh
or automatic deletion is currently supported. Installation alone enables no
schedules. Make the limitation clear when enabling monitoring. Scheduling depends
on the host automation runtime; do not promise operation while it is unavailable.

Stay quiet if unchanged. Notify only about a newly unresolved reference, a meaningful
source/capability failure or recovery, completion of an explicitly requested check,
or needed user input. Explain unlisted entries as uncertain, never as deleted. Do
not repeat the known deletion-sync limitation or unchanged failure on every run.
Honor mute preferences through `notificationPolicy`, not text in the prompt.

Repeated scheduling requests reuse the existing matching automation. Repeated
checks create no groups, move no chats, and never manufacture a deletion test by
deleting a real conversation. Check the automation response for actual activation;
creation success is not proof that a future scheduled run has executed.

If a future host offers a documented deletion tombstone/event and a scoped native
stale-reference cleanup tool, that needs a separately implemented and tested adapter.
Capability discovery alone is not permission to improvise new deletion behavior.
