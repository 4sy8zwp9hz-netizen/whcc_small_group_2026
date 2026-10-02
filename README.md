# WHCC small group schedule

A mobile-friendly Flask schedule with household attendance and a leader admin area for a West Houston Christian Church
small group. Leaders continue editing Google Sheets. The app starts immediately
with fictional CSV data and needs no Google credentials in demo mode.

## Windows setup
Install Python 3.12 or newer and Git. In PowerShell, from your personal projects folder:
```powershell
git clone https://github.com/4sy8zwp9hz-netizen/whcc_small_group_2026.git whcc-small-group-schedule
cd whcc-small-group-schedule
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m flask --app app run
```
Open http://127.0.0.1:5000. No virtual environment activation or execution-policy
change is needed. Stop the server with Ctrl+C. The repository is public by your explicit choice; cloning needs no authentication.
Future pushes require signing in to your personal GitHub account via Git Credential
Manager or GitHub CLI. Never commit real group information or credentials.

Optional configuration:
```powershell
Copy-Item .env.example .env
notepad .env
```
The app loads only the project's .env; existing environment variables take precedence.

## Screens and behavior
- This week's card comes first, directly below the compact header. It also shows
  an off week or a gathering that has already started, with attendance closed.
  With no entry this week, the next gathering is featured instead.
- Upcoming and past lists are chronological. The featured meeting is not duplicated.
- Assignments and notes expand on demand to conserve phone space.
- A meeting becomes past at its start time; no duration/end time was supplied.
- Canceled meetings retain any recorded details but do not request missing assignments.
- Discussion leader, host, food, and childcare default to required assignments.
  Missing ones show "Needs assignment". Use "Not needed" for a role that does not apply.
- Blank topic uses "Small group gathering"; blank location says "Location to be confirmed".
  Blank notes and optional assignments are omitted without error styling.
- Times use America/Chicago, displaying CST/CDT as appropriate.
- Reads are cached for 60 seconds by default, on demand. Reloading within the TTL
  reuses the cache; the page does not automatically poll.
- Failed reads or malformed rows preserve the entire last successful snapshot and
  timestamp, with a stale warning. Failed retries are also throttled.
- First-load failure returns a useful HTTP 503 page. A valid header-only sheet is
  a successful empty schedule.
- The raw calendar cache is in memory per process. With SCHEDULE_EDITING=true,
  in development the effective schedule and pending changes persist in private SQLite.
  Production uses Sheets durability and treats SQLite as an ephemeral cache.
  On restart, a failed source refresh shows persisted data with a stale warning.


## Quick household attendance
Enter a household name and its members once (comma-separated names, up to 20).
Choose **All going** or **Not going** to save. On later visits, this browser
remembers the household. Everyone starts checked for each unanswered gathering;
nothing is counted until someone submits or changes a checkbox. Uncheck anyone
who cannot come and the change saves immediately. Without JavaScript, use
**Save selection**. The attendance summary expands to show who is coming.

Responses are per gathering. Repeated taps update the same response. **Clear
response** removes that gathering's answer while keeping the remembered household.
Canceled, past or ambiguous meetings reject attendance changes. A source-calendar
refresh failure does not close attendance when the production backend was successfully
validated. Each response rereads the backend, checks the latest meeting and requires
confirmed Sheets persistence. Unreadable backend data still blocks responses.

A signed, HttpOnly, SameSite=Lax cookie remembers a random household identifier
for up to a year. Names and responses stay out of the cookie. They are stored in
the private SQLite database and, when enabled, mirrored into the App Backend tab. The default database is private/attendance.sqlite3;
a locally generated signing secret persists in private/session.key. Both are
ignored by Git. Back up these files privately together to preserve local attendance.
Cloning source code does not transfer attendance or remembered households.

This prototype uses shared group access without verified individual identities.
Another browser or cleared cookies can reconnect by choosing the existing household.
Creating a new profile instead may produce duplicates. **Forget this household on
this browser** removes recognition and preserves existing responses. Leaders can
correct rosters and attendance at /admin/households. Decide what group members may
see and edit before broader use with real information.

Optional environment settings:
```dotenv
RSVP_DATABASE=private/attendance.sqlite3
RSVP_SECRET_FILE=private/session.key
RSVP_COOKIE_NAME=whcc_household
COOKIE_SECURE=false
```
For HTTPS hosting, set COOKIE_SECURE=true and provide a long random SECRET_KEY as
a server secret. Keep it stable across restarts. Do not commit its value.

## Data and column mapping
The default headers are:
```text
date,time,location,topic,discussion_leader,host,food,childcare,notes,status
```
Date and time headers/values are required. Other headers may be absent.
Use YYYY-MM-DD dates, 24-hour HH:MM times, and blank/scheduled/canceled/cancelled status.
Rows with unknown statuses or invalid times reject the whole refresh. Blank rows are
ignored. Headers must be unique and nonempty. Ambiguous/nonexistent DST transition
times are rejected; choose an unambiguous time if this rare case arises.

Configure different sheet headers and display formats in .env:
```dotenv
FIELD_MAPPING_JSON={"date":"Meeting Date","time":"Start Time","discussion_leader":"Leader","food":"Dinner"}
DATE_FORMAT=%m/%d/%Y
TIME_FORMAT=%I:%M %p
REQUIRED_ASSIGNMENTS=discussion_leader,host,food
```
This makes blank childcare optional. Python strptime format strings are used.
The Google adapter requests formatted cell values, so match formats to the actual
sheet display and locale. No real sheet column names have been assumed.
Set the Google spreadsheet's own time zone to Central Time as well.

For a private local CSV, store it under private/ and set CSV_PATH=private/schedule.csv.
Only data/sample.csv is eligible for tracking under data/. The fictional sample is
dated September-November 2026; advance those dates if demonstrating the app later.

## Google Sheets: local server credentials and read-only calendar
1. In your personal Google Cloud project, enable the Google Sheets API.
2. Create a dedicated service account. It does not need broad project roles.
3. Create/download its JSON key to a secure location outside this repository.
   Do not paste the key into chat, commit it, or put it in static/.
4. Share the target spreadsheet directly with the service account's client_email
   as **Viewer** for schedule reading alone, or **Editor** for the optional app
   backend. Keep the spreadsheet unpublished and otherwise private.
5. Configure your untracked .env:
```dotenv
DATA_SOURCE=google
GOOGLE_APPLICATION_CREDENTIALS=C:/Users/YOUR_NAME/private/whcc-service-account.json
GOOGLE_SHEET_ID=YOUR_SPREADSHEET_ID
GOOGLE_SHEET_RANGE="'Schedule'!A1:J500"
CACHE_SECONDS=60
```
The ID is the /d/ segment of the spreadsheet URL; the range includes the header row.
Adjust the range to include all meetings and only intended columns. Extend row 500
when needed. Restart after configuration changes.

The original-calendar adapter performs a values GET using only
https://www.googleapis.com/auth/spreadsheets.readonly and a 15-second read timeout.
Credentials and tokens stay server-side. No Drive write access, published CSV URL,
or browser Google authentication is used. The optional backend writer uses the
spreadsheets scope and is restricted in application code to its configured tab.

Troubleshooting: check the enabled API, Viewer sharing, key path, spreadsheet ID,
tab/range, unique headers, mapping, and displayed date/time formats. Raw exception
messages and source content are deliberately excluded from browser errors and logs.
Logs report the exception class. Authenticated live reads have been verified on
the original workstation. A new clone still needs its own local key path and private
configuration; credentials and real sheet settings are never distributed through Git.

## Test on your phone (same trusted Wi-Fi)
```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 0.0.0.0 --port 5000
ipconfig
```
Find your PC's Wi-Fi IPv4 address and open http://YOUR_PC_IPV4:5000 on the phone.
If Windows Firewall asks, allow Python only on the trusted Private network.
Do not enable debug mode, open router ports, or expose the development server to the
internet. VPNs and Wi-Fi client isolation can prevent devices from reaching each other.
Use fictional data for this test; anyone who can reach this server can see its pages.

## Validation
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app.py schedule tests
git diff --check
```
Tests use deterministic dates and mock Google authentication/HTTP calls.
See PROJECT_STATUS.md for the latest observed results and visual checks.


## Admin editing and the App Backend tab
Open /admin and sign in with the shared leader password. Admin access expires after
30 minutes; changing the password invalidates existing admin sessions. Forms use
CSRF checks and meeting revisions, so a stale edit cannot silently replace a newer
calendar or admin change. Failed logins are limited to ten per five minutes per signed browser identity;
successful logins do not consume this allowance. Group/admin limits are independent.
Limiter storage is bounded to 1,024 browser entries per gate, in process memory.
No IP is taken from arbitrary forwarded headers: Cloud Run proxy IPs are not useful
client identities here. Clearing cookies or replacing an instance resets the limit,
so this is basic abuse reduction, not comprehensive internet attack protection. Member attendance still needs no account.

Set or change the password locally (hidden interactive entry, minimum 12 characters):
```powershell
.\.venv\Scripts\python.exe -m flask --app app set-admin-password
```
Add --env-file .env.google before --app when using the private Google configuration.
Only the hash is stored in private/admin-password.hash. Alternatively configure
ADMIN_PASSWORD_HASH as a server secret. When that environment override is present,
change it through your secret configuration instead of the local command.
A generated initial password on the original workstation is in the ignored
private/ADMIN_ACCESS.txt note; neither password nor hash comes through Git.

SCHEDULE_EDITING=true (the default) enables a local effective schedule and admin UI.
Demo edits persist in the private database and do not modify data/sample.csv.
To keep the earlier read-only schedule mode, set SCHEDULE_EDITING=false.

To connect the new backend tab, add these private settings:
```dotenv
SCHEDULE_EDITING=true
BACKEND_SHEET_ENABLED=true
BACKEND_SHEET_TITLE=App Backend
```
Use the existing Google ID, credentials, original calendar range, and mapping.
The service account needs Editor access to this spreadsheet. The writer uses
Google's spreadsheets scope; Google does not provide a scope restricted to one
tab. Application code only writes the configured new backend tab and rejects
using the original calendar's name.

Create and verify the tab once:
```powershell
.\.venv\Scripts\python.exe -m flask --env-file .env.google --app app init-sheet-backend
.\.venv\Scripts\python.exe -m flask --env-file .env.google --app app run
```
Creation refuses to replace an existing tab. A fresh clone with an empty local
database restores existing app records automatically from the backend; do not
re-run initialization against a tab that already exists.

The backend has one row per meeting: normalized date/time, assignments, notes,
status, attendance counts, and conflict flags. Its hidden final column holds the
structured state needed for restoration, including household members and responses.
Hiding a column is only a layout choice, not access control. No passwords, service
account keys, session secrets, or raw browser identity tokens are sent to Sheets.

### Continuing to edit the original calendar
- The original calendar remains intact and editable by leaders. Source reads happen
  on demand, cached for about 60 seconds. An admin can refresh immediately.
- A change made only in the calendar flows into the app/backend. A change made only
  in the app remains as an override. Changes to different fields merge.
- If both sides change the same field differently, the admin page shows the previous
  value, current calendar value, and app value. Choose which to use before saving.
  Attendance is paused for meetings with unresolved conflicts.
- App edits do not rewrite the original calendar. Use the app or original calendar
  for human edits; the backend tab is managed by the app.
- Original dates identify imported meetings because the calendar has no stable ID
  column. Moving a date in the original calendar appears as a removed old entry and
  a new entry. An admin must keep/cancel the old entry; attendance is not silently
  transferred. Moving a date through the app preserves that meeting's identity.
- Removing a calendar row never silently deletes app data. An admin chooses to
  retain or cancel it. Duplicate source dates pause refresh until corrected.
- New meetings can be added to the original calendar and will import automatically.
  The admin UI edits existing meetings and can cancel them; it has no delete button.

### Writes, outages, and recovery
Development mode retains local SQLite and queues failed syncs; preserve the database
until pending writes finish. Production (`APP_ENV=production`) treats SQLite as an
ephemeral cache. Every write refreshes the durable backend under a process lock and
must receive confirmed Sheets persistence before the app reports success. Failures
return an error and roll back provisional cache changes. A lost network acknowledgment
can mean an update reached Sheets despite the error: reload before retrying.

The original calendar stays read-only. The App Backend starts with its existing
meeting rows, then receives append-only update rows during ordinary app operation. Each update includes
the digest of its expected predecessor. Replay in sheet order accepts only a matching
predecessor; overlapping stale writers are rejected, and duplicate update IDs are
idempotent. The runtime full-tab replacement path is disabled. Original visible
meeting rows are the initial snapshot; later logical values/counts are shown by the
app, not refreshed into those initial cells. Do not hand-edit, sort, delete, or add
formulas to this tab. Back up the full tab, including the hidden state column.

Stop older app versions before using this version: their full-tab writer can destroy
update history. Keep max instances 1 and one Gunicorn worker. The log protects against
brief replacement overlap, but Sheets remains a small proof-of-concept store, not a
general transactional database. Sheets does not provide immutable history or
transactional compare-and-swap. Reordering, deleting, or restoring old sheet rows
can silently change replayed state; this accepted low-risk limitation requires
manual recovery from a complete backup. No external checkpoint is used.
Updates exceeding 49,000 characters are rejected;
the log grows with use and is reread on refresh. New version-two updates contain
only changed schedule records, changed household profiles, and individual response
updates/clear operations. Profiles are not copied into every RSVP event. The reader
still accepts legacy meeting baselines and version-one events; no live migration
or baseline replacement is needed. Old versions cannot read version-two events. Compaction is a future maintenance
feature and must only happen offline with all writers stopped and a verified backup.

Fresh instances restore schedule overrides, profiles/members and responses from the
backend before reading the source calendar. A source outage preserves that restored
schedule with a stale warning and disables RSVP. If the backend cannot be read and no
cache exists, show the unavailable state. Browser identity survives only with the same
cookie and stable signing key. Shared group/admin passwords are separate; cookies
identify browsers, not verified people. Restrict the spreadsheet's own sharing too:
website login does not protect a sheet shared with anyone who has its link.

## Continue with Codex
Read AGENTS.md, README.md, and PROJECT_STATUS.md first. Run the validation commands,
then resolve the next recorded task within the agreed scope. Do not deploy publicly
or introduce real group information until website access has been decided.

## Two-row calendar layout
The optional calendar reader supports a school-year calendar with month/day dates,
a topic on a continuation row, paired assignments, and merged event/off-week titles.
It reads the existing layout without editing the spreadsheet.

Keep real connection settings in an ignored .env.google file. Example with fictional
settings (replace the year, headers, range, ID, and key path with your own):
```dotenv
DATA_SOURCE=google
SHEET_LAYOUT=calendar
GOOGLE_APPLICATION_CREDENTIALS=C:/Users/YOUR_NAME/private/whcc-service-account.json
GOOGLE_SHEET_ID=YOUR_SPREADSHEET_ID
GOOGLE_SHEET_RANGE="'Calendar'!A1:J200"
FIELD_MAPPING_JSON={"host":"Host","food":"Dinner","discussion_leader":"Discussion","childcare":"Childcare","notes":"Event notes"}
CALENDAR_START_YEAR=2030
CALENDAR_START_MONTH=9
CALENDAR_START_TIME=18:00
CALENDAR_DATE_COLUMN=A
CALENDAR_EVENT_COLUMN=D
CALENDAR_END_MARKER=Roles
CALENDAR_TOPIC_LABELS_JSON=["Sermon Series"]
CALENDAR_CANCELED_DATES=
```

Start that configuration explicitly:
```powershell
.\.venv\Scripts\python.exe -m flask --env-file .env.google --app app run
```

- Start the source range at column A and include its header row. The date header
  may be blank and host columns may be hidden; neither prevents reading.
- Map assignment headers exactly, ignoring leading/trailing whitespace. Four
  mapped role headers must each appear once. The notes mapping is optional.
- Dates such as "September 6" use the configured start year; months before the
  start month use the following year. This is independent of the current date.
  Update the year/range deliberately when rolling to a new school year.
- CALENDAR_START_TIME is required, in 24-hour HH:MM Central Time, and applies to
  every gathering. It must be confirmed by a leader, not inferred from bare times.
- A date row starts a meeting. A continuation row with a blank date or an allowed
  topic label adds assignments to that meeting. Distinct names are joined with " / ".
  If the topic label changes, update CALENDAR_TOPIC_LABELS_JSON.
- An event title in the configured event column becomes the topic when there are
  no mapped assignments or continuation topics. Off/break/canceled event titles
  are treated as no-meeting weeks. Social events do not show missing role warnings.
- Stop reading at CALENDAR_END_MARKER so role descriptions and timetables are not
  mistaken for meetings. Ensure the requested range includes every meeting.
- Optional mapped notes are included. All unmapped columns are discarded during
  normalization and never rendered. The reader does not read other tabs.
- Unexpected date labels or changed required headers fail the whole refresh,
  preserving the last successful schedule. Color and strikethrough are not status
  signals; the reader uses cell text only.
- Duplicate dates are preserved and visibly flagged. For a leader-confirmed off
  date, set CALENDAR_CANCELED_DATES to comma-separated ISO dates. Each explicit
  override keeps one off-week entry and suppresses incorrect regular entries on
  that date. These overrides are local configuration; reconcile them after the
  source sheet is corrected.
- A host assignment is not a location/address. Missing locations remain unconfirmed.
- In calendar mode, normalized dates/times use ISO and HH:MM internally; DATE_FORMAT
  and TIME_FORMAT apply only to the original table layout.

No real sheet IDs, participant data, connection files, or credentials are included
in Git. An ignored .env.google or private/ note on one computer will not come through
a clone; recreate it privately on the next computer. The default fictional CSV
still works without Google authentication.

A fully fictional calendar fixture lives at tests/fixtures/calendar.csv. Tests
cover two-row grouping, year rollover, events, off-week overrides, duplicate dates,
notes, ignored columns, malformed refreshes, and the authenticated adapter contract.

## Google Cloud Run Deployment

Preparation only: no cloud resources or deployment have been performed. Manual
source deployment uses this Dockerfile through Cloud Build. There is no CI/CD,
SQL database, Redis, or persistent disk. Later GitHub automation can reuse these
commands through Workload Identity Federation, after manual deployment works.

### 1. Install CLI, select project and billing (you perform these steps)
Install the [Google Cloud CLI for Windows](https://docs.cloud.google.com/sdk/docs/install).
Use a personal Google account. Commands below are PowerShell, from the repository.
Replace all placeholders. Stop on any command failure before proceeding.

```powershell
gcloud auth login
$ProjectId = "YOUR_GLOBALLY_UNIQUE_PROJECT_ID"
$Region = "us-central1"
$Service = "whcc-small-group"
$UserEmail = "YOUR_PERSONAL_GOOGLE_EMAIL"
gcloud projects create $ProjectId --name="WHCC small group"
# Skip creation if you already have the intended personal project.
gcloud config set project $ProjectId
gcloud billing accounts list
$BillingAccountId = "YOUR_BILLING_ACCOUNT_ID"
gcloud billing projects link $ProjectId --billing-account=$BillingAccountId
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com sheets.googleapis.com
```
Your Google user needs project creation permission (or an existing project), billing
account User and project Billing Manager to link billing, Service Usage Admin to
enable APIs, Service Account Admin to create identities/bind their policies, Secret
Manager Admin to create secrets, and project IAM policy permissions for setup grants.
These are setup permissions for your user, never the runtime identity. For ongoing
source deploys use Cloud Run Source Developer, Service Usage Consumer and Service
Account User on the two identities below. Changing public invocation/IAM also needs
Cloud Run Admin or an administrator performing that step; do not grant it to runtime.

### 2. Separate runtime and build service accounts
```powershell
gcloud iam service-accounts create whcc-runtime --display-name="WHCC runtime"
gcloud iam service-accounts create whcc-build --display-name="WHCC build"
$RuntimeEmail = "whcc-runtime@$ProjectId.iam.gserviceaccount.com"
$BuildEmail = "whcc-build@$ProjectId.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$BuildEmail" --role="roles/run.builder"
gcloud projects add-iam-policy-binding $ProjectId --member="user:$UserEmail" --role="roles/run.sourceDeveloper"
gcloud projects add-iam-policy-binding $ProjectId --member="user:$UserEmail" --role="roles/serviceusage.serviceUsageConsumer"
gcloud iam service-accounts add-iam-policy-binding $RuntimeEmail --member="user:$UserEmail" --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts add-iam-policy-binding $BuildEmail --member="user:$UserEmail" --role="roles/iam.serviceAccountUser"
```
Runtime needs no project Owner/Editor role, no build role, and no downloaded key.
Share the intended church spreadsheet with `$RuntimeEmail` as **Editor**, because
attendance/backend writes require it. Sheets permissions apply to the whole file;
the code restricts writes to App Backend, not IAM. If that broad sheet permission is
unacceptable, separate the backend into another spreadsheet in future work.
Remove Anyone-with-the-link sharing before storing private attendance information.
Cloud Run ADC discovers the assigned service account and requests Sheets scopes.
Local development can still use an external `GOOGLE_APPLICATION_CREDENTIALS` file.
Do not set that variable or upload a service-account JSON on Cloud Run.

### 3. Create three Secret Manager secrets
Select **migrate** to preserve an existing installation, or **fresh** only when
there is no existing state or signing key. Before migration, stop/drain the old runtime and
identify its effective signing key: process SECRET_KEY first, selected private env
file next, repository .env next, otherwise its configured RSVP_SECRET_FILE (default
private/session.key). Preserve the old private database, key, exact source config
and complete backend backup; reconcile pending development writes before switching.
The script never generates a signing key in migration mode, refuses missing/conflicting
keys, and refuses to overwrite existing deployment-secret files. It prompts twice
for each group/admin password and writes only hashes plus the preserved key.
Passwords should be distinct and kept privately.

Keeping the key lets existing signed cookies work **on the same hostname**. Browsers
do not send localhost/home-PC cookies to a new Cloud Run hostname. Changing the key
also invalidates old cookies. Historical households/responses remain in Sheets, but
this proof of concept has no cross-host household recovery UI. Before moving users
to a different hostname, plan leader-assisted reconciliation and avoid treating a
new household identity as automatic recovery of the old one. Do not weaken cookie
scope or expose browser identity tokens to transfer them.

```powershell
.\.venv\Scripts\python.exe tools/create_deployment_secrets.py --mode migrate --env-file .env.google
# If the original runtime uses a nondefault key file, add --key-file PRIVATE_SIGNING_KEY_PATH.
gcloud secrets create whcc-secret-key --replication-policy=automatic --data-file=private/deployment-secrets/secret-key
gcloud secrets create whcc-group-password-hash --replication-policy=automatic --data-file=private/deployment-secrets/group-password-hash
gcloud secrets create whcc-admin-password-hash --replication-policy=automatic --data-file=private/deployment-secrets/admin-password-hash
foreach ($SecretName in @("whcc-secret-key", "whcc-group-password-hash", "whcc-admin-password-hash")) {
    gcloud secrets add-iam-policy-binding $SecretName --member="serviceAccount:$RuntimeEmail" --role="roles/secretmanager.secretAccessor"
}
```
For a genuinely new installation with no existing state or key, use
`python tools/create_deployment_secrets.py --mode fresh` instead. Fresh mode refuses
a detected signing key or local SQLite state, preventing accidental migration key
replacement. Do not select fresh simply because the deployment computer is new;
bring the existing signing key privately from the original runtime. If a signing
secret already exists in Secret Manager, reuse that pinned version rather than
create a new secret or rotate its value during migration.

Grant Secret Accessor on these individual secrets only. Pin versions (initially `1`)
in the deployment command. Rotation uses `gcloud secrets versions add SECRET_NAME
--data-file=PRIVATE_FILE`, then deploy the chosen new version. Rotating a password
hash invalidates its login sessions; changing SECRET_KEY invalidates all cookies and
can orphan remembered household identities. Preserve SECRET_KEY across deployments.
Local files contain sensitive hashes/key material; protect them with your Windows
account permissions and never paste them into chat or commit them.

### 4. Nonsecret runtime configuration
Create ignored `cloudrun.env.yaml` locally. This fictional table-layout example is a
starting point; set the real ID/range/layout/field mapping privately. For the existing
two-row calendar use the earlier calendar instructions, explicit school year,
confirmed `18:00` start time, and leader-confirmed canceled-date overrides.
Quote all YAML values to make them strings. Omit GOOGLE_APPLICATION_CREDENTIALS.

```yaml
APP_ENV: "production"
DATA_SOURCE: "google"
GOOGLE_SHEET_ID: "YOUR_SPREADSHEET_ID"
GOOGLE_SHEET_RANGE: "'Schedule'!A1:J500"
SHEET_LAYOUT: "table"
FIELD_MAPPING_JSON: '{}'
SCHEDULE_EDITING: "true"
BACKEND_SHEET_ENABLED: "true"
BACKEND_SHEET_TITLE: "App Backend"
CACHE_SECONDS: "60"
COOKIE_SECURE: "true"
TRUST_PROXY: "true"
```
The App Backend must already exist. For a fresh sheet, use the documented local
`init-sheet-backend` CLI with private local credentials; it refuses to replace an
existing tab. No creation/migration of the real backend was performed in this task.
Back up its full contents and stop all older writers before the first deployment.

### 5. Review upload, then manually deploy
The `.gcloudignore` and `.dockerignore` allow only runtime source, requirements,
Dockerfile and fictional sample CSV. Dockerfile also uses explicit COPY paths.
Review the file list: no private/, .env, databases, keys, tests or archives may appear.

```powershell
gcloud meta list-files-for-upload
gcloud run deploy $Service --source . --region=$Region --service-account=$RuntimeEmail --build-service-account="projects/$ProjectId/serviceAccounts/$BuildEmail" --env-vars-file=cloudrun.env.yaml --set-secrets="SECRET_KEY=whcc-secret-key:1,GROUP_ACCESS_PASSWORD_HASH=whcc-group-password-hash:1,ADMIN_PASSWORD_HASH=whcc-admin-password-hash:1" --min=0 --max=1 --concurrency=4 --cpu=1 --memory=512Mi --cpu-throttling --timeout=120 --port=8080 --allow-unauthenticated
$ServiceUrl = gcloud run services describe $Service --region=$Region --format="value(status.url)"
Invoke-RestMethod "$ServiceUrl/health"
gcloud run services describe $Service --region=$Region
```
`--allow-unauthenticated` exposes the HTTPS entry point to ordinary browsers; the
Flask group password protects schedule/RSVP/admin routes. Health and static assets
are public and contain no group data. Organization policy may prohibit public
invocation; ask an administrator rather than weakening policy. Cloud Build can
prompt to create its Artifact Registry repository. Approve only when you are ready
for the first deployment and potential charges.

One worker, four Gunicorn threads and concurrency 4 keep slow API calls manageable;
SQLite/backend writes share a process lock. Normal warm RSVP mutations use two
backend values GETs (fresh pre-write state plus append verification), with tab
metadata cached for five minutes. GETs retry once after 0.2 seconds for timeout,
429 or retryable 5xx errors. Appends have at most two attempts with identical
content-derived event IDs/payloads, inspecting receipts before retry; delayed copies
are deduplicated on replay. Permanent permission/validation errors are not retried.
Unknown acknowledgments return an error, never an unverified success. Service-level `--min=0 --max=1` applies
across revisions. Cloud Run can briefly exceed its max during replacements, so the
append log also rejects stale independent writers. No persistent disk is required.
Cloud Run terminates TLS; narrow ProxyFix trusts only the final protocol header,
not forwarded IP/host/port. Enable TRUST_PROXY only behind Cloud Run's managed
proxy, never for a directly exposed Gunicorn server. Production forces Secure,
HttpOnly, SameSite=Lax cookies and requires both hashes plus a stable signing key.

### 6. Post-deployment verification and recovery
- Confirm `/health` returns only `{"status":"ok"}`, without login or Sheets calls.
- In a fresh/private browser confirm /, /past and /admin redirect to group login;
  unauthenticated POST cannot change attendance. Wrong passwords/CSRF fail.
- Sign in with the group password; verify actual schedule, Central times and refresh.
  Admin still requires its separate password. Sign out and verify access closes.
- Create a designated test household/RSVP, deselect one person, then check backend
  update rows and totals in the app. Clear the test response afterward.
- Make a reversible admin note edit and restore it. Change a source field separately
  and verify merge/conflict handling. Never manually edit the managed backend.
- Redeploy the same source/config/secrets to force a fresh revision; using the same
  browser, confirm household profile, RSVP and override restore. Verify actual new
  revision traffic in Cloud Run. Scale-to-zero/wake can then be checked after idle.
- Simulate missing sheet access only on a separate test sheet: stale data remains
  readable, writes fail clearly, cold unavailable state is useful, recovery works.
- Inspect Cloud Run logs for sanitized failure classes, never passwords/credentials.
  Check Secure cookies and HTTPS redirects in browser developer tools.

A fresh runtime needs the backend and source permissions plus Secret Manager access.
Local storage loss is safe for **confirmed** writes. Failed/unknown writes must be
reviewed after reload. If backend content is corrupt, stop writers, preserve a copy,
restore a verified full-tab backup with the same signing key, and verify before
resuming. Do not roll back to a pre-append-log app version against this backend.

### 7. Cost controls
Use request-based billing (`--cpu-throttling`), min 0, service max 1, CPU 1 and 512 MiB.
No always-on worker, VPC connector or database. A few dozen users may fit applicable
free allowances, shared across the billing account; **$0 is not guaranteed**.
Builds, stored container images/build artifacts, Secret Manager, logs and network
traffic can cost separately. Keep deployments infrequent initially; monitor and
remove unneeded old images/build artifacts deliberately after preserving rollback.
In Billing > Budgets & alerts create a project-scoped **alerts-only** monthly budget
of $5, with actual-spend alerts at 20%, 50%, 90% and 100%, plus forecast 100%.
Confirm email delivery. An alerts-only budget does not cap or stop spending; max
instances is also not a hard monetary cap. Review Billing after the first deploy
and weekly initially. Delete the service deliberately if you decide to stop hosting;
images, secrets and build storage may continue incurring costs until separately removed.

References: [source deployment](https://docs.cloud.google.com/run/docs/deploying-source-code),
[custom build identity](https://docs.cloud.google.com/run/docs/configuring/services/build-service-account),
[service identity](https://docs.cloud.google.com/run/docs/securing/service-identity),
[secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets),
[maximum instances](https://docs.cloud.google.com/run/docs/configuring/max-instances),
[pricing](https://cloud.google.com/run/pricing),
[budget alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets).

### Production configuration matrix
All variables read by the app are listed below; defaults apply when omitted.
Sheet identifiers/mappings are not authentication secrets but belong only in private
local configuration for this public repository.

| Variable | Purpose | Secret? | Local source | Cloud Run source |
|---|---|---|---|---|
| APP_ENV | development or production; production validates security/durability | No | .env, development | YAML, production |
| SECRET_KEY | Stable signed-cookie key, 32+ characters | Yes | .env or private/session.key | Secret Manager |
| GROUP_ACCESS_PASSWORD_HASH | Shared group gate, optional locally | Yes | .env | Secret Manager, mandatory |
| ADMIN_PASSWORD_HASH | Separate admin gate | Yes | .env or password file | Secret Manager, mandatory |
| ADMIN_PASSWORD_FILE | Local fallback hash path | Yes contents | private/admin-password.hash | Unused with hash configured |
| GOOGLE_APPLICATION_CREDENTIALS | Local external key path | Yes contents | Outside repo | Omit; runtime ADC |
| DATA_SOURCE | csv or google | No | csv by default | YAML, google |
| GOOGLE_SHEET_ID | Spreadsheet identifier | Private config | .env.google | YAML |
| GOOGLE_SHEET_RANGE | Original source range | Private config | .env.google | YAML |
| SHEET_LAYOUT | table or calendar | No | .env | YAML |
| FIELD_MAPPING_JSON | Internal field/header mapping | Private config | .env | YAML |
| CSV_PATH | Fictional demo input | No | data/sample.csv | Unused in Google mode |
| CACHE_SECONDS | Last-good refresh interval, 1..3600 | No | 60 | YAML, 60 |
| REQUIRED_ASSIGNMENTS | Fields marked when blank | No | discussion_leader,host,food,childcare | YAML optional |
| DATE_FORMAT / TIME_FORMAT | Table parsing formats | No | %Y-%m-%d / %H:%M | YAML optional |
| CALENDAR_START_YEAR / CALENDAR_START_MONTH | School-year rollover | No | Explicit year / 9 | YAML for calendar |
| CALENDAR_START_TIME | All calendar gatherings start time | No | Confirmed HH:MM | YAML for calendar |
| CALENDAR_DATE_COLUMN / CALENDAR_EVENT_COLUMN | Calendar columns | No | A / D | YAML optional |
| CALENDAR_END_MARKER | Stop before descriptive rows | No | Roles | YAML optional |
| CALENDAR_TOPIC_LABELS_JSON | Continuation labels | No | ["Sermon Series"] | YAML optional |
| CALENDAR_CANCELED_DATES | Confirmed off-date overrides | Private config | Comma-separated ISO dates | YAML optional |
| SCHEDULE_EDITING | Effective schedule/admin enabled | No | true | YAML, true |
| BACKEND_SHEET_ENABLED | Durable Google backend publication | No | false by default | YAML, true |
| BACKEND_SHEET_TITLE | Managed tab name | Private config | App Backend | YAML |
| RSVP_DATABASE | SQLite runtime/cache path | Private contents | private/attendance.sqlite3 | Default /tmp/whcc/attendance.sqlite3 |
| RSVP_SECRET_FILE | Development generated signing key path | Yes contents | private/session.key | Unused; SECRET_KEY required |
| RSVP_COOKIE_NAME | Browser cookie name | No | whcc_household | YAML optional |
| COOKIE_SECURE | HTTPS cookie flag | No | false for local HTTP | Forced true in production |
| TRUST_PROXY | Trust only managed proxy's scheme header | No | false | YAML, true for Cloud Run |
| PORT | Gunicorn binding | No | Docker 8080 | Cloud Run injected |

No GOOGLE_SERVICE_ACCOUNT_JSON mechanism existed in this checkout; none was added.
Authentication is lazy, so startup and /health require no Sheets request.

### Optional container verification at home
Docker was unavailable on the preparation workstation. With Docker Desktop using
Linux containers, this fictional configuration exercises startup/health without a
real credential or any Sheets request. Generate an ignored `.env.container-test`
with fictional long SECRET_KEY, password hashes (not plaintext), APP_ENV=production,
DATA_SOURCE=google, GOOGLE_SHEET_ID=fictional-sheet-id, SCHEDULE_EDITING=true and
BACKEND_SHEET_ENABLED=true. Omit a credential path. Then:

```powershell
docker build -t whcc-small-group .
docker run --rm -p 8080:8080 --env-file .env.container-test whcc-small-group
# In another terminal:
Invoke-RestMethod http://localhost:8080/health
```
The schedule is intentionally unavailable with fictional Google configuration.
Do not pass real credentials for this build/health check.

## Operational migration and backup procedure

1. **Stop and drain all legacy writers.** Close local development servers, stop old
   hosted revisions, block incoming mutations and wait for outstanding requests.
   Remove legacy service-account Editor access where practical; the new runtime
   should use its dedicated identity. Stopping a browser is not stopping a server.
2. **Preserve and reconcile.** Back up the old SQLite cache, effective signing key,
   private source config, and the complete App Backend tab, including hidden column
   Q and every accepted/rejected event row. Resolve any locally pending writes with
   the authoritative sheet deliberately before changing runtimes. Never initialize
   over an existing backend. Test the procedure on a private copy first.
3. **Protect the managed tab.** In Sheets use Data > Protect sheets and ranges to
   protect the whole App Backend sheet (including future appended rows), allowing
   only the runtime identity and designated recovery owners to edit. Avoid manual
   sorting, filtering that reorders rows, cell editing, deletion, and formulas.
   Protection reduces accidents; owners can still alter history, and it is not an
   independent integrity checkpoint. Keep ordinary leader edits in the source tab.
4. **Start the new version carefully.** Preserve the signing key, verify configured
   layout/year/time and source tab, then restore into an empty cache on a private
   test copy. Verify old meeting IDs/RSVP links, profiles/member IDs, historical
   answers, overrides and clear behavior. Equivalent quoted/unquoted A1 spellings
   retain restored IDs. If duplicate existing source dates/scopes are found, stop
   and reconcile them; do not select an arbitrary record. Enable controlled use
   only after verification and the outstanding container/Cloud Run checks.
5. **Restore only with all writers stopped and drained.** Preserve the damaged tab
   separately, restore a verified complete backup (never just visible columns),
   clear/recreate the ephemeral production cache, and test restoration with the
   same signing key before reopening. A restored older backup intentionally loses
   updates newer than that backup; communicate that and re-enter them deliberately.

Ordinary scale-to-zero/restart recovery is supported. Altered, reordered, or deleted
Sheets history can require manual recovery and is not reliably detected by an empty
instance. This is the accepted architecture: no external database or checkpoint.
Back up before migration/restoration and periodically during use, especially before
administrative changes. Choose frequency according to the amount of re-entry you
would tolerate (weekly is a reasonable starting point for this small group).

### Practical capacity and maintenance
Tests cover twenty households with twenty members each, maximum-length non-ASCII
member names, multiple meetings, historical responses, clear, and schedule edits.
An individual RSVP toggle/clear does not grow with the other households' rosters;
a schedule edit does not carry RSVP data. A single maximum-size profile still fits
one mutation cell. Large multi-record source imports can exceed the 49,000-character
aggregate event limit and fail clearly; no partial success is acknowledged.
This is a small-group proof of concept, not an unlimited-capacity service. Start with
no more than a few dozen households; inspect the managed row count and refresh time
monthly. At 2,000 event rows, consistently slow refreshes, or repeated quota errors,
pause growth and plan maintenance on a backed-up private copy. No automated log
compaction is implemented; do not delete rows to shorten the log while writers run.
Manual backup/recovery is preferable to adding infrastructure for this scope.

### Current verification
The combined reliability fixes and remembered group login are reviewed for
publication on main under explicit owner authorization. No live sheet/cloud changes
or deployment were performed. Tests cover independent admin/RSVP
writers with synchronized append barriers, stale rejection/retry, quota-sized bursts,
429 handling, delayed unknown acceptance, empty-cache cookie recovery, large rosters,
source identity, per-browser throttling, and explicit signing-key migration.
Docker is not installed/on PATH here; actual image execution as UID 10001, runtime
ADC and real managed-HTTPS verification remain outstanding before deployment.


## Remembering group access
The group login's native **Remember this device for 30 days** checkbox is unchecked
by default. A successful login grants a fixed 24 hours, or a fixed 30 days only
when explicitly checked. The server enforces the absolute deadline on every
protected request. Browsing, RSVPs, and restarts do not extend it. Existing cookies
are not upgraded; a later unchecked login replaces the deadline with 24 hours.
Failed passwords, invalid CSRF, and arbitrary submitted durations cannot extend it.

Household identity is separate: its existing signed cookie persists for up to
365 days, linking the saved roster and responses after ordinary group expiry or
logout. Admin access still requires its own password and expires after 30 minutes;
remembering or re-entering the group password does not extend or revive it.
Group logout requires a CSRF-protected POST, clears group and admin authorization,
rotates CSRF, and keeps household identity and stored responses. **Forget this
household** remains the separate action that clears this browser's identity.

Use remembered access only on a personal browser profile; sign out on shared
devices. "This device" means that profile retaining its cookie, without hardware
fingerprinting. Recognition requires the same browser, hostname, and signing key.
Clearing cookies loses recognition; cookies do not transfer to a different hostname.
Changing the group password hash invalidates group authorization, including remembered
sessions. These are stateless signed cookies: logout clears the receiving browser's
authorization but cannot independently revoke an already-copied valid cookie.

Validation before publication: baseline 136 tests, final
157 tests; controlled-clock authorization/recovery tests use fictional data and
mocked durable storage. Login inspected at 375 and 1440 pixels without horizontal
overflow; label tapping, keyboard Tab/Space, and native submission verified. The
login loads no scripts and native login also succeeded with all scripts blocked by
a preview-only Content-Security-Policy (script-src 'none'). Docker is unavailable; actual image execution,
Cloud Run ADC and managed HTTPS verification remain outstanding. No live Sheets or
cloud changes or deployment were performed. The owner subsequently authorized
staging, committing and pushing the reviewed project changes to main.


## Admin recovery for incomplete backend rows
If the Google backend cannot be validated, admin home remains reachable and offers
**Check backend and recover incomplete rows** at /admin/recovery. The preview is
read-only. It identifies populated managed rows that have neither a meeting ID nor
stored app state. Every retained baseline, visible cell and update event must pass
the existing strict validator; identified records or damaged history are not skipped.

Only after separate admin authentication, CSRF validation, a current preview and
confirmation that other writers/manual sheet edits have stopped, recovery creates a
new WHCC Recovery backup tab containing the entire fetched A:Q range as literal
values. It reads and verifies the backup, rechecks the original fingerprint, then
clears only the previewed incomplete rows in A:Q. It never deletes a row, rewrites
valid records/history, or edits the original calendar. Columns outside A:Q remain
untouched; keep a complete spreadsheet backup separately when extra columns exist.
Incomplete-row text is archived, not imported as meetings. Use the original calendar
for new meetings and the admin editor for changes to existing meetings.

If the backup fails verification or the sheet changes after preview, nothing is
cleared. An unknown clear acknowledgment is inspected without repeating the clear.
An interrupted recovery can leave a backup tab; inspect it before retrying. Sheets
has no transactional compare-and-swap: stopping competing writers remains necessary.
Do not use this screen to restore missing/deleted history or to force a malformed
identified record into validity; those cases still require stopped-writer recovery
from a complete verified backup. Current state restoration cannot recover data that
was already lost by a previous spreadsheet version-history rewind.

On Cloud Run, synchronization warnings now say that local storage is temporary and
writes are unconfirmed. Backend refresh errors appear directly on admin home rather
than implying that only the original calendar failed. Retry does not publish when
refresh remains stale. This recovery update is local and uncommitted/unpublished.
Validation: 172 tests passed (157 prior cases plus 15 new recovery cases); fictional
browser recovery and admin-home return passed at 375/1440 pixels without overflow.
No live Google read/write, deployment, secrets, commit or push was performed.

## Rebuild after visible backend damage
After deploying this revision, open **Admin → Check backend and recover incomplete
rows → Preview a backed-up backend rebuild**, or /admin/recovery/rebuild. This page
works when ordinary backend reads fail due to damaged visible managed cells.
It reads valid hidden meeting records and replays valid updates in their existing
order, preserving meeting IDs/links, household profiles/member IDs, historical
responses and cleared responses. Stale updates remain rejected; repeated update
IDs deduplicate. It does not import visible-only manual edits. Review the counts.
Damaged hidden JSON, missing state on identified rows, bad headers or invalid events
still refuse repair; a blind reset could discard household identity and attendance.

Back up the entire spreadsheet, including hidden state and extra columns. Stop all
other writers/revisions and manual edits; use only one current runtime and suspend
member edits/RSVPs for maintenance. Confirm this and type REBUILD. The app creates
and verifies a new WHCC Recovery tab containing literal managed A:Q values, rechecks
that the backend has not changed, then replaces A:Q with the recovered snapshot.
Previous event rows are compacted; their original history remains in that backup.
Extra columns are untouched and not included in the app-created backup. Keep backup
tabs until recovery and later writes are confirmed. Unknown replacement acknowledgments
are read back rather than blindly retried; an interrupted action may leave a backup.

Return to admin home and retry refresh. Rebuild does not repair calendar parsing,
permissions or network failures. The original calendar is never written. Sheets has
no transactional compare-and-swap: concurrent writes during repair are unsafe despite
fingerprint checks. Ordinary restart recovery remains supported; altered/deleted
stored history may still require manual stopped-writer recovery from backups.
Normal full-tab write() remains disabled. Normal updates use numeric-tab appendCells requests with literal values in A:Q,
appending after the last data row without logical-table detection. Semantically
empty changes do not create events. Real Sheets append placement and this repair
need post-deployment verification. No new secrets are required.

Admin editing also remains available during an original-calendar outage when the
production backend validates. Every save rereads the backend, requires the same
meeting revision and confirms Sheets persistence; failed writes roll back. When
calendar refresh resumes, the existing three-way merge preserves app overrides and
flags simultaneous changes for leader resolution. An invalid/unreachable backend
still blocks saves until repair/access succeeds.

### Header moved below empty updates
If old code inserted an empty App update above the header, deploy the writer fix
before rebuilding again. /admin/recovery/rebuild now locates the exact managed
header and can archive recognized version-two empty updates above it. Their IDs
and payloads must validate; meaningful/unrecognized rows before the header refuse
repair. Preview reports the displaced header row. After backup and confirmation,
rebuild restores the header to row 1. Do not manually delete/move rows or change
hidden state. Stop old revisions/writers before repair; verify refresh and a later
admin/attendance update after it. Numeric-tab appendCells replaces values.append;
normal full-tab replacement remains disabled. Backups are still retained.


## Household setup and where saves go
Admin home links to **Households and attendance** (/admin/households). Create a
household with 1–20 comma/newline-separated people, or load an existing household.
Correct names or add people without replacing existing member IDs. Choose an
upcoming confirmed gathering, then use All going, Not going, per-person checkboxes,
or Clear this response. Save household only leaves attendance unanswered/unchanged.
Removing people/households is deliberately unavailable to preserve history.
Admin forms reject newer profile/response/meeting changes rather than overwrite them.

On the member schedule, choose your existing household, then tap who is going.
Selecting a household remembers it on this browser and does not submit attendance.
Guests can enter their own name (and anyone joining them); household name is optional.
Before creating a household, look for an existing one to avoid duplicates.
This shared-group roster selection is not identity verification: anyone with group
access can select a household and edit its response. Use it only for this trusted
small group. Group/admin authentication and CSRF protection remain in place.

Google saves append literal **App update** rows below the data in **App Backend**,
with granular changes in the managed state column. The original meeting rows are
a snapshot and are not rewritten for each change, so their displayed cells/counts
may be old. The app replays accepted updates to show current schedule/attendance.
Do not manually edit, sort or delete these rows. The original calendar stays
read-only to the app. The admin sync status reports confirmed Sheets persistence;
local demo mode and pending development sync are labeled separately.

**Back to household selection** changes only this browser selection, keeping group/admin
access and saved attendance. Choose another household or expand **New household or
visiting guest?** using its caret. Guest setup is collapsed by default and works
without JavaScript.
