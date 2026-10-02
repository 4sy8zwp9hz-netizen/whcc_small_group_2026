# Project status

Updated: 2026-10-02

## Purpose and boundaries
Original personal project for the owner's WHCC small group, co-led with his wife
Diana and another member. Practice internet-facing deployment while making the
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
5. Generate/store secrets, create private cloudrun.env.yaml with actual confirmed
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
