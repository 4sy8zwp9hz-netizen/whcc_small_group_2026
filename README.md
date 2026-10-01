# WHCC small group schedule

A mobile-friendly, read-only Flask schedule for a West Houston Christian Church
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
- A highlighted next gathering excludes canceled meetings.
- Upcoming and past lists are chronological. The next gathering is also included
  in the complete upcoming list, intentionally.
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
GOOGLE_SHEET_RANGE='Schedule'!A1:J500
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
Logs report the exception class. Real connectivity has not been verified without
the user's real sheet and service account.

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
- Mount the Google service-account key as a secret file; point
  GOOGLE_APPLICATION_CREDENTIALS to its absolute server path.
- One worker maintains one shared process cache; multiple workers/instances have
  independent caches. Plan a shared cache only if scaling requires it.
- Flask's development server is for local testing only. No service was purchased,
  created, or deployed for this proof of concept.

References: [Render Flask guide](https://render.com/docs/deploy-flask),
[Flask Gunicorn guidance](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/),
[Google Sheets scopes](https://developers.google.com/workspace/sheets/api/scopes).

## Continue with Codex
Read AGENTS.md, README.md, and PROJECT_STATUS.md first. Run the validation commands,
then resolve the next recorded task within the agreed scope. Do not deploy publicly
or introduce real group information until website access has been decided.
