# WHCC small group schedule

A mobile-friendly Flask schedule with quick household attendance for a West Houston Christian Church
small group. Leaders continue editing Google Sheets. The app starts immediately
with fictional CSV data and needs no Google credentials in demo mode.

## Windows setup
Install Python 3.12 or newer and Git. In PowerShell, from your personal projects folder:
```powershell
git clone https://github.com/4sy8zwp9hz-netizen/whcc_small_group_2026.git whcc-small-group-schedule
cd whcc-small-group-schedule
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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
- Cache is in memory per process. Restarting loses the last-good snapshot.
  There is intentionally no disk cache of private data.


## Quick household attendance
Enter a household name and its members once (comma-separated names, up to 20).
Choose **All going** or **Not going** to save. On later visits, this browser
remembers the household. Everyone starts checked for each unanswered gathering;
nothing is counted until someone submits or changes a checkbox. Uncheck anyone
who cannot come and the change saves immediately. Without JavaScript, use
**Save selection**. The attendance summary expands to show who is coming.

Responses are per gathering. Repeated taps update the same response. **Clear
response** removes that gathering's answer while keeping the remembered household.
Canceled, past, ambiguous, or stale schedules reject attendance changes.

A signed, HttpOnly, SameSite=Lax cookie remembers a random household identifier
for up to a year. Names and responses stay in the server's SQLite database, not
the cookie or Google Sheet. The default database is private/attendance.sqlite3;
a locally generated signing secret persists in private/session.key. Both are
ignored by Git. Back up these files privately together to preserve local attendance.
Cloning source code does not transfer attendance or remembered households.

This is a prototype without verified identities or cross-device household recovery.
Another browser, cleared cookies, or **Forget this household on this browser**
creates a new identity and may produce a duplicate household. Forgetting preserves
existing responses but loses the ability to edit them from that browser. There is
no roster-editing UI yet. Website access, recovery, and leader correction tools must
be decided before broader use with real household information.

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

## Google Sheets: server-side, read-only
1. In your personal Google Cloud project, enable the Google Sheets API.
2. Create a dedicated service account. It does not need broad project roles.
3. Create/download its JSON key to a secure location outside this repository.
   Do not paste the key into chat, commit it, or put it in static/.
4. Share the target spreadsheet directly with the service account's client_email
   as **Viewer**. Keep the spreadsheet unpublished and otherwise private.
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

The adapter performs a values GET using only
https://www.googleapis.com/auth/spreadsheets.readonly and a 15-second read timeout.
Credentials and tokens stay server-side. No Drive write access, published CSV URL,
or browser Google authentication is used.

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

## Future Render deployment (not deployed)
Before deployment, decide who may access the website and how that access is enforced.
**A private Google Sheet does not make the website private.**
This prototype has no website authentication: anyone with network access can read it.
Decide which addresses, names, notes, and assignments are appropriate to display.
An access gateway is one possible future choice; no account system is implemented.

For a future Linux Render web service:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT app:app`
- Configure a supported Python 3.12+ runtime and environment values.
- Set COOKIE_SECURE=true and a persistent random SECRET_KEY in server secrets.
- Attendance needs durable storage: set RSVP_DATABASE to a persistent disk path
  for a single instance, or migrate to a managed database before scaling. Default
  ephemeral storage can lose attendance during redeploys. No disk was purchased.
- Mount the Google service-account key as a secret file; point
  GOOGLE_APPLICATION_CREDENTIALS to its absolute server path.
- One worker maintains one shared process cache; multiple workers/instances have
  independent caches. Plan a shared cache only if scaling requires it.
- Flask's development server is for local testing only. No service was purchased,
  created, or deployed for this proof of concept.

References: [Render Flask guide](https://render.com/docs/deploy-flask),
[Flask Gunicorn guidance](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/),
[Google Sheets scopes](https://developers.google.com/workspace/sheets/api/scopes),
[Render persistent disks](https://render.com/docs/disks),
[Flask cookie security](https://flask.palletsprojects.com/en/stable/web-security/).

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
