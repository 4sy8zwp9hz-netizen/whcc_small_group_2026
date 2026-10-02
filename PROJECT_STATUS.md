# Project status

Updated: 2026-10-02

## Purpose and boundaries
Original personal project for a WHCC small group. Practice internet-facing deployment
while making the
existing Google Sheets schedule readable on phones. Existing work applications
were not modified; no company code, configuration, data, or archives were copied.
No paid services or public app deployment are authorized.

## Completed
- Flask + Jinja + responsive CSS; no frontend build pipeline.
- Fictional CSV demo and read-only, server-authenticated Google Sheets adapter.
- Configurable columns, formats, and required assignments.
- Next gathering, chronological upcoming/past views, canceled meetings.
- America/Chicago times with DST validation.
- Process-local 60-second cache, safe stale fallback, last-successful timestamp,
  useful no-data error, and atomic validation before replacing cached data.
- Git exclusions, .env.example, Windows/Wi-Fi instructions, future production command.
- 92 automated tests passed on Python 3.12.14. Python compilation passed.
- Added an optional school-year calendar reader with two-row assignments, header
  mapping, merged event titles, off weeks, optional notes, and footer exclusion.
- Added configurable leader-confirmed off-date overrides and visible warnings
  for other duplicate dates. The original CSV/table mode remains the default.
- Inspected the supplied calendar read-only and prepared ignored .env.google and
  private/GOOGLE_SETUP.md files locally. No real sheet ID, rows, or private connection
  values are tracked. These ignored files must be recreated privately at home.
- Verified authenticated Google Sheets reads using the owner's externally stored
  service-account key. Both meeting views returned HTTP 200 using live data.
- Verified 60-second cache reuse, the leader-confirmed off-week override, stale
  fallback after a simulated refresh failure, and recovery with another live read.
- Key contents, local key path, spreadsheet ID, and real rows remain outside Git.
  The key is referenced by ignored .env.google and was not copied into the project.
- Rechecked the calendar UI with fictional paired assignments at 375 and 1440 px,
  with no horizontal overflow.
- Browser inspection at 375x812 and 1440x1000. Upcoming and past pages checked;
  no horizontal overflow (document widths 360 and 1425, allowing scrollbars).
  Corrected a text-encoding issue found during the first phone inspection.
- Source and tracked-file allowlist reviewed for secrets/unrelated content.
  Only original project code, documentation, and fictional sample data are included.

## Household attendance update
- Compact top card with expandable assignments and notes.
- Household setup once; one-tap all/none and individual checkbox autosave.
- Counts and attendee names, clear-response control, and non-JavaScript fallback.
- Persistent signed cookie; server-side SQLite and signing secret excluded from Git.
- CSRF checks, escaped names, membership validation, and transactional updates.
- Tests reject stale, canceled, past, ambiguous, and missing-meeting writes.
- Browser checks verified initial setup, all going, child opt-out, not going, and
  cookie/response persistence after reload. Fixed a browser-discovered form action
  property collision. Test households use a separate fictional preview database.
- New-layout browser checks: 375-pixel phone viewport (360-pixel content width)
  and desktop (1265-pixel content width), with no horizontal overflow. The top
  card starts about 63 pixels from the top on phone. Expanded past assignments
  also fit the phone width. Physical phone testing remains pending.
- Earlier production gaps (now addressed by Cloud Run readiness below) included
  website access decisions, durable storage, HTTPS cookie
  settings, and a stable signing secret. No public app deployment was performed.

## Admin and Google backend update
- Owner requested an admin editor and a new backend tab while keeping the original
  calendar editable. Implemented field-by-field three-way merging with explicit
  conflict resolution, stale-form rejection, and removed-date review.
- Created and verified the real App Backend tab using the existing service account.
  Original calendar content was not edited. Private settings stay in .env.google.
- Added leader login, 30-minute sessions, CSRF protection, password hashing, and
  process-local login throttling. Shared-password setup is the prototype assumption.
- Local initial admin access instructions are in ignored private/ADMIN_ACCESS.txt.
- Admin edits and member attendance persist locally, then publish with retry status.
  The sheet stores normalized schedule fields, counts, and restorable app state.
  Browser identity secrets, admin credentials, and Google credentials are excluded.
- An empty database restores from the backend. Restored households use one-way IDs;
  browser cookies and the original signing secret are still needed to recognize them.
- Tests cover auth/expiry/throttling, field merges, both conflict resolutions, stale
  forms, source failures, removals, stable identity after app date edits, failed writes,
  lost acknowledgments, foreign changes, restoration, and scoped literal Sheets writes.
- Browser validation with fictional data verified admin login, schedule editing,
  conflict detection/resolution and member-facing results. Phone (360-pixel content)
  and desktop (1265-pixel content) had no horizontal overflow. The populated Google
  backend was also visually inspected; its technical ID/state columns are hidden.
- App Backend is machine-managed. Direct edits or competing writers stop publication.
  Only one running app instance is supported. Google has no conditional-update
  primitive, so the read/compare/write check is not a distributed lock.
- App edits update the effective backend copy, not the original calendar. New entries
  can be added in the original calendar; the admin editor changes existing meetings.

## Assumptions and tradeoffs
- Default required assignments: discussion leader, host, food, childcare.
- Topic, location, notes, and status are optional; blank location is unconfirmed.
- Meetings become past at their start time (no end time provided).
- This week is featured above navigation, including off weeks or already-started
  gatherings. Otherwise the next gathering is featured; it is not duplicated.
- Sample dates are fixed in September-November 2026.
- Refreshes happen on page requests. The raw cache is process-local; the effective
  schedule, app edits, and pending sync survive in private SQLite.
- Entire refresh fails if any populated row is malformed, preserving last-good data.
- In table mode, Google formatted values must match configured Python formats.
  Calendar mode uses explicit school-year and confirmed start-time configuration,
  then normalizes month/day rows into the same meeting interface.
- Special events do not request missing regular-meeting assignments. Unmapped
  source columns are discarded; only selected schedule fields are rendered.
- Explicit off-date overrides are local configuration and should be reconciled
  after the owner corrects the source sheet.
- The owner expanded scope to household attendance: one remembered household,
  everyone initially selected, individual opt-outs, and All going / Not going.
- SQLite stores durable attendance and pending writes. The original calendar is
  read-only to the app; the new App Backend tab receives schedule and attendance.
- Shared-password admin sign-in is now authorized. No member accounts, reminders,
  payments, or prayer requests.
- Cookies identify a browser, not a verified person. Clearing cookies or switching
  devices can create duplicate households. Forgetting preserves old responses.
- Roster editing, household recovery, and leader correction tools remain future work.
- Authenticated Google connectivity is verified locally. A physical phone test remains.

## Repository and handoff
Repository: https://github.com/4sy8zwp9hz-netizen/whcc_small_group_2026
Owner 4sy8zwp9hz-netizen was verified with the authenticated GitHub connector.
The user signed in, created this empty repository, and explicitly authorized keeping
it PUBLIC, superseding the original private-repository request.
The local directory remains whcc-small-group-schedule, outside existing work repos.
Publication uses the authenticated GitHub connector; the local checkout tracks main.
Published on main; remote contents matched the reviewed local Git tree.
Git Credential Manager initially had no usable credential. Public cloning needs no
authentication; future pushes from home require authenticating the personal account.
No website has been deployed. Public source code is not permission to publish real data.

## Remaining decisions and next tasks
1. On another computer, supply the service-account key outside the repository and
   set its local path in ignored .env.google. Recheck authenticated reads there.
2. Recreate the private sheet configuration at home using the supplied sheet and
   local private notes. Do not publish these values through Git.
3. Confirm meeting locations separately; a host assignment is not an address.
4. Decide website access and acceptable displayed information before sharing real
   group data online. A private sheet does not make the website private.
5. Test on a physical phone on trusted Wi-Fi.
6. Decide household recovery, roster editing, and leader correction before wider use.
7. Perform the documented Cloud Run manual setup only after explicit deployment
   authorization; container and real deployment verification remain pending.


## Cloud Run readiness completed (2026-10-02)
The inspected checkout/remote had no separate earlier production-readiness commit;
this work preserves the existing Flask/calendar/admin/attendance implementation and
adds the missing deployment and access features. No Google credentials were used,
no live sheet was read/changed, and no cloud resources, billing or deployment were
created during this task.

### Completed
- Official Python 3.12 slim Dockerfile, non-root runtime, explicit COPY paths,
  source-upload/image allowlists and separate development test requirements.
- PORT-aware Gunicorn config: one worker, four threads, timeout 120.
- Lazy server ADC on Cloud Run; explicit external local key remains supported.
- Production requires stable SECRET_KEY, separate group/admin hashes and durable
  Google backend; cookies forced Secure. Group login/logout/CSRF/throttling protects
  member/private routes and admin remains independently authenticated.
- Public minimal /health has no cookie, private fields or Google calls.
- Opt-in narrowly scoped proxy handling (scheme only) for Cloud Run TLS termination.
- Production restores Sheets before writing, rolls back unconfirmed cache changes,
  and never claims queued ephemeral writes are durable. Development still queues.
- Same-tab append-only optimistic update log tolerates replacement overlap without
  overwriting accepted history. Duplicate IDs are idempotent; stale writers rejected.
- Durable household profiles persist even when their last RSVP is cleared.
- Exact manual setup/deploy, least-privilege IAM, secrets/config matrix, cost controls,
  upload review, verification and recovery guide in README.

### Architecture
Browser HTTPS -> Cloud Run -> Flask/Gunicorn -> Sheets API -> original calendar
(read-only) and App Backend (durable initial snapshot plus append-only updates).
SQLite under /tmp is a runtime cache in production, rebuilt from the App Backend.
No SQL/Redis/Firebase or persistent disk, no CI/CD and no unattended sync process.

### Remaining manual steps
1. Install gcloud/Docker Desktop if desired; verify Docker build and health locally.
2. Choose/create personal project, attach billing, enable Run/Build/Artifact Registry/
   Secret Manager/Sheets APIs, and configure an alerts-only budget.
3. Create whcc-runtime and whcc-build identities; grant build run.builder and grant
   runtime Secret Accessor only on the three secrets. Your user needs setup IAM and
   ongoing source deploy/actAs permissions; see README's exact commands.
4. Restrict sheet sharing, share as Editor with runtime email, back up the full App
   Backend and stop all older/full-tab writers. No live migration was done here.
5. Explicitly select migrate/fresh mode; preserve the effective signing key for
   existing state. Prepare secrets and private cloudrun.env.yaml with actual confirmed
   source layout/year/time/mappings. Review gcloud upload file list.
6. Deploy manually only when authorized, then execute the post-deployment checklist.

### Secrets
Create whcc-secret-key -> SECRET_KEY, whcc-group-password-hash ->
GROUP_ACCESS_PASSWORD_HASH, whcc-admin-password-hash -> ADMIN_PASSWORD_HASH.
Use pinned Secret Manager versions (initially 1). Keep the signing key unchanged
across revisions. tools/create_deployment_secrets.py creates ignored local files
interactively, never logs their values and makes no cloud requests.

### Service Account
whcc-runtime@YOUR_PROJECT_ID.iam.gserviceaccount.com is the runtime identity.
It has no Google Cloud Owner/Editor role, no downloaded key, and no build role.
Share the intended spreadsheet as Editor with that email; Sheets grants file-level
access, while the application restricts writes to the configured backend tab.
whcc-build is separate and has run.builder. Do not reuse old local keys in Cloud Run.

### Deployment
Use README's exact PowerShell `gcloud run deploy --source .` command with runtime
and build accounts, private env YAML, pinned secrets, --min=0 --max=1 --concurrency=4
--cpu=1 --memory=512Mi --cpu-throttling --timeout=120 --port=8080. Browser invocation
is public at Cloud Run but all group information is password-gated in Flask.
The Dockerfile is used by source deployment. The prior hosting target has been removed.

### Verification
Current preparation: 112 fictional-only tests passed, including filesystem deletion,
fresh-instance restore with the same cookie, overrides/RSVP, strict failed writes,
ADC selection, public health, production config rejection, group/CSRF/throttling,
secure cookies/proxy and stale writer/lost append acknowledgment handling.
Docker and gcloud are unavailable on this workstation; container build/start and
real Cloud Run ADC/HTTPS checks remain pending. Prior schedule/admin phone/desktop
browser checks predate this change; new group login visual inspection remains pending.
After deployment verify /health, group/admin login separation, cookie/CSRF behavior,
RSVP member opt-outs, source merge/conflicts, backend updates, sanitized logs, and
redeploy with identical signing key to force empty-filesystem recovery.

### Recovery and limitations
Confirmed writes survive scale-to-zero and replacement because the full state lives
in Sheets. If the original calendar fails, restored backend data is shown stale;
RSVP closes. If no backend/cache is readable, return a useful unavailable state.
Unknown network acknowledgment may have persisted: reload before retrying. Cookies
are browser identities, not individual authentication. Throttling is process-local
and resets on replacement; shared passwords are a proof-of-concept access gate.
Do not sort/edit/delete managed rows or run a pre-log app version against the log.
Initial visible backend rows are a baseline; latest effective values/counts appear
in the app, while appended updates retain history in the managed column.
The log grows and updates have a 49,000-character payload limit. Future maintenance
needs offline verified-backup compaction, household recovery and roster editing.
A production runtime must use its own empty single-source cache; do not point it at
an unrelated shared database. Backend replacement imports only that app's data.

### Cost
Request-based billing, min 0, max 1, CPU 1 and 512 MiB target near-zero use for a few
dozen users. No guaranteed $0: build/image storage, secrets, logs/egress and shared
free allowances matter. Set $5 alerts-only project budget at 20/50/90/100% and
forecast 100%, verify notifications and inspect billing after deployment. Alerts
and instance limits are not hard spending caps. README gives cleanup considerations.


## Independent-review targeted fixes (local, 2026-10-02)
User chose to KEEP Sheets as the authoritative backend and accept accidental history
changes/manual recovery. No other database or external history checkpoint was added.
The original review request permitted implementation/local verification only: no live spreadsheet
changes, cloud resources, deployment, commit or push. The reviewed commit remains
821f7d8d9af9f89ed3644da0db6bf91a2fdffab6; changes below are uncommitted locally.

### Changes made
- Canonical A1 source-title spelling and legacy SQLite scope migration preserve
  existing IDs/pending overrides. Restored source-date matching retains historical
  meeting IDs and RSVP URLs; ambiguous preexisting dates fail closed.
- Bounded per-signed-browser failure limits for independent group/admin gates;
  successful logins do not consume allowance and proxy IP headers are not trusted.
- Reuse pre-write snapshot and verified commit results; five-minute metadata cache.
  Warm RSVP: two values GETs instead of eight GETs. GET retries once; append retries
  at most once with identical content-derived event ID/payload. Delayed duplicates
  deduplicate; unknown acknowledgment returns an error and may later recover.
- Version-two granular record/profile/response/clear mutations avoid embedding all
  household rosters/responses on each small update. Legacy baseline/version-one
  replay remains supported. No live conversion/rewrite was performed.
- Migration secret helper explicitly requires --mode migrate or fresh. Migration
  preserves effective signing-key precedence, refuses missing/conflicting keys and
  never creates a replacement. Fresh refuses detected old key/local SQLite state.
  Key continuity does not move a cookie to a different hostname; no automatic
  cross-device/cross-host household recovery UI exists.
- Unnecessary co-leader name/family context removed from current documentation.
  Existing published commits are unchanged because commit/push/history edits were
  not authorized in this task.
- Runtime full-tab write method fails before contacting Sheets. New-tab creation
  remains explicit and refuses to replace an existing backend.
- README/AGENTS explain draining/revoking old writers, complete hidden-state backups,
  managed-tab protection, stopped-writer restoration, payload/maintenance limits.

### Verification and deployment readiness
At the end of that task, 136 tests passed, including real reader/append replay via shared fake Sheets,
two independent SQLite/backend writers with append barriers (RSVP vs RSVP and admin
vs RSVP), stale rejection with safe retry, delayed acceptance after HTTP error and
empty-cache restart, eight-response burst within mocked 60-read quota, 429 retries,
large non-ASCII rosters/historical meetings, clear preserving profiles/member IDs,
old RSVP URLs with equivalent A1 spelling, cookie key versus host migration,
per-browser isolation, and disabled legacy replacement. Final validation: full suite passed, compileall passed for app.py/schedule/tests/tools,
and git diff --check passed. Working-tree files were reviewed for unrelated/private
content; no new credential or real sheet identifiers were introduced. No real credentials or API calls used.
Docker is unavailable here: actual container build/execution, UID 10001 /tmp access,
Cloud Run ADC and managed HTTPS checks remain outstanding. Prior browser checks
still apply to the unchanged schedule/admin layouts; new runtime behavior was tested
server-side. No deployment was attempted or authorized.

### Accepted limitations and operations
Sheets is editable history, not immutable storage or transactional compare-and-swap.
Stale predecessor checking protects ordinary intact-log writes. It cannot reliably
detect deleted/reordered history or restoration of an outdated tab on a cold instance.
Ordinary restart recovery is supported; altered/deleted history may need manual
complete-backup recovery. Stop/drain every writer before migration/restoration;
revoke old identities' write access where practical. Protect the whole managed tab,
including appended rows and hidden state. Never hand-sort/edit/delete event rows.
Unknown acknowledgment may persist after the caller saw an error: reload before
retrying. Signed-browser throttling is basic, bypassable by clearing cookies and
resets on replacement; limiter storage remains bounded. The full log is reread and
replayed; inspect growth/latency monthly and plan private-copy maintenance around
2,000 events or recurring quota/latency problems. No automatic compaction exists.
Keep stable signing-key versions; new hostnames require deliberate household
reconciliation rather than a promise of transparent browser migration.


## Optional remembered group access (local, 2026-10-02)
All preceding uncommitted review fixes remain in place. Added an unchecked native
"Remember this device for 30 days" group-login checkbox, associated label, helper
text, keyboard focus styling and a 44-pixel label target. Login spacing remains
usable on phones. No admin checkbox, database, device registry, session records in
Sheets, or additional login/logout Sheets calls were introduced.

Successful login sets a fixed server-enforced group_until: 24 hours by default,
30 days only for the explicit checked value. Duplicate/unrecognized values and
submitted deadlines cannot select longer access. Browsing/RSVP/restart retain the
original deadline; later unchecked success replaces remembered access with 24 hours.
Wrong passwords and invalid CSRF do not grant or extend access. Credential-hash
rotation invalidates remembered group authorization; browser failure limits remain.
Admin password and 30-minute deadline remain independent. Household-cookie lifetime
remains 365 days with refresh disabled. Expiry/logout preserve household, roster and
responses; group logout clears both authorizations and rotates CSRF. Recognition
requires the same cookie/browser/hostname/key. Cookie clearing loses identity.
Logout cannot revoke an already-copied signed cookie. Use only on personal devices;
shared-device users should sign out. No fingerprinting or remote device revocation.

Validation: actual pre-feature baseline 136 passed; final full suite 157 passed.
21 new cases cover duration selection, exact expiry, no sliding, re-login, failure,
CSRF, throttling, admin separation, logout, recovery with empty SQLite and mocked
durable state, password rotation, tampering, secure cookies and public health.
Login inspected in browser at 375/1440 pixels: no overflow, readable helper text,
44-pixel label target, label tap and keyboard Tab/Space work. Native form submission
succeeds with all scripts blocked by a preview-only Content-Security-Policy
(script-src 'none'); login contains no scripts. No browser-setting disable test
is claimed. Docker is unavailable:
container build/execution and real Cloud Run ADC/HTTPS checks remain outstanding.
Compileall and git diff --check passed. No secrets/settings/helper changes, live
Google API calls, staging, commit, push, deployment or cloud-resource changes.
HEAD remains 821f7d8d9af9f89ed3644da0db6bf91a2fdffab6 and index hash unchanged.
At the end of that task, changes were LOCAL AND UNCOMMITTED. The publication
authorization below supersedes that restriction; the stopped-writer backup
procedure still applies before any future migration/deployment.


## Combined publication review (2026-10-02)
The owner authorized review, staging, commit and normal push of the completed
reliability fixes and optional remembered group login to the existing personal
repository main branch. No deployment, Google Cloud changes, live spreadsheet
access or real secret generation/rotation is authorized. This revision includes
those combined changes; preceding local-only reports describe earlier task states.

The current checkout branch/origin and authenticated personal GitHub account were
verified. Fetched origin/main matched the starting HEAD with no divergence. All
publication candidates and ignore rules were reviewed: original project source,
documentation and fictional fixtures only; private runtime files remain ignored.
No CI/CD workflow was added and no deployment triggers were configured.
Final suite: 157 tests passed; app.py/schedule/tests/tools compileall and working
and staged diff whitespace checks passed. Prior 375/1440-pixel login, keyboard,
label-tap and script-blocked native form checks remain applicable.
Docker build/execution, non-root /tmp access, real Cloud Run ADC and managed HTTPS
verification remain outstanding. Sheets remains authoritative with editable history
and manual stopped-writer backup/recovery limitations. The secret helper's --help
was inspected only; neither mode was run against real settings.


## Admin backend recovery (local, 2026-10-02)
The owner reported invalid backend records after manual sheet edits and a version
history rewind. An owner-supplied CSV under ignored private/ was inspected offline;
no private rows, IDs or values were copied into source, tests or public docs. The
CSV itself was unchanged. A narrow recovery preview validated all retained records
and identified only unidentified rows missing hidden app state as candidates.

Added /admin/recovery, accessible through existing group/admin authentication even
when the backend cannot refresh. Preview is read-only; POST requires CSRF, admin
expiry checks, a fresh table fingerprint and explicit stopped-writer confirmation.
The runtime first creates a new backup tab with literal copies of managed A:Q data
and verifies it. It rechecks for competing changes and clears only eligible incomplete
A:Q ranges, preserving valid meetings, profiles/member IDs, replies and update events.
No original calendar writes, full-tab replacement, row deletion or automatic reset.
Malformed identified records, edited retained cells, bad events and headers fail
closed. Extra columns are untouched, not included in the managed backup; keep a
complete spreadsheet backup as well. Clearing acknowledgment is checked without a
blind retry. An interrupted attempt may leave a backup tab for manual inspection.
Sheets has no CAS; all other writers/manual edits must stop for maintenance.

Admin home shows the underlying refresh error and warns that Cloud Run local storage
is temporary/unconfirmed. Sync retry skips publication when refresh remains stale.
Validation: full suite 172 passed; 15 new recovery cases cover preserved legacy/v2
history, household data, strict refusals, verified literal backups, stale previews,
backup failure/mismatch, overlapping edits, lost acknowledgment, auth/CSRF/confirmation
and cold admin availability. An offline preview of the supplied CSV passed without
changing it. Fictional browser checks passed at 375/1440 pixels without overflow,
including keyboard confirmation, recovery, and return to editable admin home.
Compilation and whitespace checks passed. Changes are LOCAL AND UNCOMMITTED; HEAD
and index unchanged from the previously published revision. No live Google API calls,
cloud changes, deployment, real secrets, staging, commit or push in this task.
The owner separately reports Docker build/isolated production startup passed in
Cloud Shell and a running Cloud Run website; these were not independently verified
here. This new recovery code has not been container-tested or deployed. Review and
publish it, then perform an explicitly authorized rollout before it appears on the
running website. Never deploy or repair the live backend without that authorization.

## Explicit backed-up backend rebuild (local, 2026-10-02)
The owner requested repair despite backend validation errors and supplied pasted
backup/current managed cells. Inspected attachments offline only; no private data
was copied into project files. Both supplied backup copies were identical. Current
pasted hidden state validates: 39 baseline records and three valid update rows
replay successfully. The paste omits a hidden column on baseline rows, so it is not
proof of actual live alignment. No live API inspection or root-cause claim is made.

Added /admin/recovery/rebuild as explicit authenticated maintenance. Preview uses
validated hidden baseline/events despite damaged visible projections, preserves
meeting IDs/links, profiles/member IDs and effective historical attendance, and
reports archived unidentified rows. Typed REBUILD plus stopped-writer confirmation,
CSRF and group/admin gates are required. Verified literal A:Q backup precedes a
fresh fingerprint check and a single A:Q snapshot replacement. Events are compacted
into effective state; original history stays in the backup. Visible-only manual
changes are not imported. Corrupt hidden records, invalid events/headers and missing
state on identified rows still refuse. Unknown replacement acknowledgement is
verified without blind retry. Original calendar and extra columns remain untouched.
Normal write() stays disabled. Normal append searches only the identity column A
to avoid sparse logical-table column shifts; 17 values still write A:Q. Google API
append placement has not been verified live; it remains a deployment check.

Validation: 186 tests passed (14 new rebuild cases), compilation and whitespace
checks passed. Tests cover damaged projections, duplicate/stale events, historical
RSVP/clear/profile preservation, stable links, cold SQLite restore, backup failures,
stale previews/competing writers, unknown replacement acknowledgement, auth/CSRF
and explicit confirmations. Offline rebuild preview and regenerated strict reader
passed for supplied hidden data after accounting for the omitted hidden column.
Fictional-only browser inspection at 375/1440 pixels passed without horizontal
overflow; form submission rebuilt successfully and admin home became editable.
No live Sheets access, secrets, cloud resources, staging, commit, push or deployment.
All changes remain local and uncommitted. Publish and roll out only when authorized;
then verify backup, rebuild, later admin/RSVP appends and empty-cache restart on the
real runtime. User-reported prior Cloud Shell container/startup checks predate this
change. New container/live verification remains pending. Sheets still has no CAS;
maintenance requires no concurrent writers, and corrupted history may require
manual backup recovery. Rebuild does not solve calendar/access/network failures.

## Attendance availability during calendar outages (local, 2026-10-02)
The owner requested that a refresh warning not unnecessarily close attendance.
Production now distinguishes a successfully validated App Backend from a failing
original calendar. When only calendar refresh fails, upcoming noncanceled,
unambiguous saved meetings retain attendance controls. Each POST still rereads the
backend, checks the current meeting and requires confirmed Sheets persistence;
backend validation/network failures and failed writes cannot claim a saved response.
Past/canceled/conflicting meetings stay closed. Demo/read-only stale data retains
its previous refusal. Admin schedule editing remains paused during source outages.

Replaced the blanket closure text with specific past/conflict/unavailable reasons.
The schedule warning now explains saved-backend attendance availability, while
unverifiable data still shows a truthful retry message. Documentation updated.
Six new regression cases cover cold-instance calendar failure, all/custom/none/clear,
profile preservation, changed canceled/past/conflicting backend meetings, unreadable
backend and failed-write rollback. Existing message assertions updated to new copy.
Final full suite 192 passed; compileall and whitespace checks passed. Initial suite
failures were old copy expectations (and a Windows cleanup error caused by an early
failed assertion); after updating those expectations the complete suite passed.
Fictional browser checks at 375/1440 pixels passed without overflow. Household
submission and one-tap member deselection both saved during a simulated calendar
outage. No live Sheets access, secret changes, cloud changes, staging, commit, push
or deployment. This and the preceding rebuild remain local and uncommitted; actual
container/live Cloud Run verification of these changes is outstanding.

## Admin outage fix and combined publication (2026-10-02)
The owner authorized pushing the combined rebuild/availability changes and updating
the app. Admin editing now uses a verified production backend during source-calendar
outages, with fresh backend reads, revision checks and confirmed persistence. Source
recovery still preserves overrides and flags simultaneous changes. Unverifiable
backend data continues to block edits. Prior statements that admin edits stay paused
describe the preceding task state and are superseded by this fix.

Full suite: 194 passed; compileall and whitespace checks passed. Two new admin cases
cover outage edits, source recovery/conflict merge, stale revisions and failed-save
rollback. Actual fictional browser edit at 375 pixels saved a location during a
simulated source outage; saved value survived reload without horizontal overflow.
Combined files reviewed for publication; private configuration/credentials/CSV stay
ignored. Personal account, branch and origin verified; fetched main matches starting
HEAD without divergence. Publication includes only original app source/docs/tests.
No live spreadsheet or secrets accessed/modified. gcloud and Docker are unavailable
on this workstation. User must perform Cloud Shell source deployment and verify real
backend rebuild, subsequent admin/attendance writes and empty-cache restart. No live
repair/deployment has been performed by the agent. Keep backup tabs until verified.

## Header displacement writer fix (2026-10-02)
After the previous rollout, the owner reported successful rebuild followed by an
empty version-two App update in row 1 and the header in row 2. The earlier tests
modeled values.append as always appending below all rows and missed this observed
runtime placement failure. The previous repair was insufficient because a later
refresh could damage the repaired layout again. No live sheet was accessed here.

Replaced values.append/logical-table detection with numeric-sheetId appendCells in
batchUpdate, explicit userEnteredValue string literals, same stable event IDs and
bounded verification/retry. According to the official Sheets API, appendCells adds
after the last data row. No normal replacement path is enabled. Empty semantic
patches now skip mutation and return freshly verified state, handling optional empty
household-list serialization differences without repeated empty events.

Explicit rebuild can locate the exact header below validated EMPTY version-two
updates, replay retained data, verify a literal backup and restore the header to row
1. It refuses meaningful/unrecognized leading rows and invalid stored payloads.
Auth/CSRF/stale preview/stopped-writer confirmation and unknown-ack checks remain.
Existing meeting links, profiles/member IDs and historical responses remain preserved.
Deploy this corrected writer before repairing again; stop all old writers/revisions.

Full suite: 201 passed, including seven new cases for one/multiple empty prepended
updates, preservation and subsequent write placement, unsupported leading data,
no-op suppression with a newer writer, and route rebuild plus automatic refresh.
Existing two-writer/stale-event/unknown-ack/empty-cache tests now exercise appendCells.
Compileall and whitespace checks passed. Source/docs/fictional fixtures reviewed for
publication; no copied private event IDs, sheet rows or credentials. The owner
previously authorized publication to main; this is the follow-up reliability fix.
Container and actual Google/Cloud Run append/recovery checks remain outstanding.
No deployment, live repair, cloud resources or real secret changes were performed.

## Admin households and member/guest entry (2026-10-02)
Added /admin/households with existing group/admin gates, CSRF and stale-form tokens.
Leaders can create profiles, correct household/member names, add people, and record
all/none/per-person/clear responses for upcoming confirmed meetings. Existing member
IDs and historical responses are preserved; no deletion UI is provided. Production
rereads Sheets, rechecks profile/meeting/response state and requires confirmed append
persistence; failed saves restore the verified previous state. Other writers'
unrelated updates are retained and same-profile stale forms are rejected.

Members can select an existing household on the schedule; selection remembers it
without submitting attendance. Guests can enter their own names with an optional
household label. These are shared-group selections, not verified individual accounts:
anyone with the group password can select a household and edit its response.
No new secrets or identity services were introduced. Authentication/CSRF remain.

With the owner's explicit live-access authorization, a read-only backend inspection
confirmed 39 valid meetings and three schedule update events; the latest included a
location override. No live sheet values were modified. App saves are append events
below the baseline snapshot; visible baseline cells/counts need not reflect current
state. Admin home and README now explain this. Original calendar remains read-only.

Validation: 210 passing tests, compilation and whitespace checks passed. The first
full run found the prior test requiring a household label; that expectation was
updated for authorized guest entry and the complete suite passed. New regressions
cover stale profiles/responses, independent admin writers using real append adapter
with mocked transport, granular payloads, stable member IDs, empty-cache restoration,
invalid names/rosters, failed append rollback and remembered profile selection.
Isolated fictional browser submissions verified admin all/custom attendance, member
selection and one-tap change, guest name-only submission, persistence after reload,
and 375/1440 layouts without horizontal overflow. Real Sheets was only read; no test
households were created there. Cloud Run must be redeployed to expose these forms.
Docker/gcloud are unavailable locally; this revision's container/live write checks
remain outstanding. Prior user-reported container checks predate this revision.

## Requested form examples (2026-10-02)
Updated member/admin placeholders to the owner-requested household and people
examples. These are hints only; no profiles, attendance or live Sheet data are
created. Fictional tests/fixtures remain unchanged. Render and whitespace checks
passed. Cloud Run needs redeployment for the updated placeholders.

## Household back navigation and collapsed guest setup (2026-10-02)
Added a CSRF-protected Back to household selection action that changes only the
browser household choice, preserving group/admin access, CSRF and stored profiles
and attendance. Guest setup is a native details/summary section, initially collapsed,
with a visible rotating caret and keyboard focus. No JavaScript dependency added.
212 tests passed, compilation and whitespace checks passed. Fictional browser checks
at 375/1440 verified collapsed/expanded setup, selected-household back navigation,
preserved attendance and no horizontal overflow. No live Sheet/cloud changes.
Cloud Run needs redeployment to expose this update.

Login throttling uses a separate stable browser identity so household back/selection
does not reset failed group/admin login allowances; regression coverage added.

## Full admin cards and past-event filter (2026-10-02)
Show past events is checked by default; the GET filter hides passed start times
when unchecked. Classification uses America/Chicago meeting times, including
canceled meetings; a meeting starting now remains included. Each card exposes all
11 editable fields using a shared partial with the standalone editor. Blank
required assignments are marked and optional fields are identified. Existing
CSRF, revision/conflict checks, strict persistence and error behavior are retained.
214 tests passed, compilation and whitespace checks passed. Fictional browser
checks at 375/1440 verified default checkbox, hiding past cards, all fields visible,
inline location save/persistence and no horizontal overflow. No live Google or
cloud changes performed. Redeployment is required to expose these changes.

## Household example wording correction (2026-10-02)
Pluralized the requested household placeholder in both member/admin forms.
Render and whitespace checks passed; no saved household or live Sheet data changed.

## Single guest/new-household Submit (2026-10-02)
Guest/new-household setup now has one Submit button using the existing all-going
action. All entered people are marked going; existing remembered households retain
all/none and individual controls. Native and JavaScript submissions remain supported.
215 tests passed, compilation and whitespace checks passed. Fictional browser Submit
confirmed both entered people, remembered identity and response persistence on reload.
No live Sheet/cloud changes. Redeployment is required to show the new button.

## Expanded upcoming assignments (2026-10-02)
Assignment/note details start open on the upcoming page, including the featured
this-week card. Native carets still collapse them; past details retain their
collapsed default. Render checks and fictional browser checks at 375/1440 passed
without overflow; collapse and reload/default expansion verified. Whitespace checks
passed. No live Sheet/cloud changes. Redeploy to expose this display-only update.

## Collapsed planned attendance on upcoming cards (2026-10-02)
Later upcoming cards use a native collapsed Can you make it? disclosure around
existing attendance controls. The featured card retains visible attendance and
upcoming assignments retain their open default. Canceled/past behavior is preserved.
AJAX replaces only the panel inside the disclosure, keeping it open after saves.
216 tests passed, compilation and whitespace checks passed. Fictional browser
checks at 375/1440 verified expanded form, one-tap future selection, unchanged
this-week response, persisted plans after reload and no horizontal overflow.
No live Sheet/cloud changes; redeployment is required for this display update.

## Compact remembered-household highlights (2026-10-02)
Removed the household-picker instruction at the owner's request. Future card
summaries show the browser's remembered household in a highlighted badge; checked
member choices are highlighted inside forms. No attendance is submitted by selection
or highlighting. Existing cookie/auth/CSRF and explicit-save behavior is unchanged.
217 tests passed, compilation and whitespace checks passed. Fictional browser
checks verified household selection, remembered badge after reload, checked-name
highlight styling, and no overflow on upcoming/past at 375/1440 widths.
No live Sheet/cloud changes. Redeploy to expose this interface update.

## Admin maintenance tab and roster assignment selectors (2026-10-02)
Admin home now defaults Show past events off. Checking/applying includes past events.
Backend sync status and refresh/retry controls moved to /admin/backend, linked from
admin navigation as Backend sync and recovery. That tab links incomplete-row repair
and /admin/recovery/rebuild; existing repair previews/backups/stopped-writer/auth/CSRF
requirements remain intact. Sync retry returns to the maintenance tab.
Discussion leader/childcare use full roster names with household context in checkbox
dropdowns and save short first names separated by /; host/food select households.
Custom text and untouched historical assignments remain supported. Server validates
selected roster IDs, handles explicit empty selections and keeps revision checks.
Optional family surname in household setup appends only to single-word names,
preserving IDs/history; surnames are never inferred from household titles.
220 tests passed, compilation and whitespace checks passed. Fictional browser checks
at 375/1440 verified filters/navigation, repair links, multiple member choices,
household choices, saved values after reload and no overflow. Browser-discovered
blank household preselection bug fixed and rechecked (food saves correctly).
No live Sheet/cloud changes, no secrets changed. Cloud Run redeploy required.
Changes ready for reviewed commit/push to existing personal main. If interrupted,
inspect Git status/HEAD/origin before publishing; preserve all work.
