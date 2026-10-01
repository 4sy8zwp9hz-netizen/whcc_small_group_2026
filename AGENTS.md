# WHCC small group schedule

## Scope
Personal proof of concept for West Houston Christian Church, led by the owner,
his wife Diana, and another member. This is original code in a separate repository.
Never copy company code, configurations, credentials, private data, or chat archives.
Google Sheets remains the schedule source of truth; its adapter is read-only.
Household attendance, explicitly requested by the owner, is stored separately in SQLite.

Use Flask, server-rendered Jinja templates, and plain responsive CSS. No frontend
build system. No accounts, reminders, payments, prayer requests, or public
deployment without a new explicit request. Decide website access before using real
group information online. A private sheet does not make the website private.

## Conventions
- Python 3.12+; straightforward modules, explicit names, standard library when practical.
- All meeting times use America/Chicago. Require dates and times; do not invent them.
- Normalize both adapters through the same parser and last-good cache.
- Keep configuration in environment variables, never hardcode real sheet IDs or people.
- Attendance uses a signed browser cookie, CSRF checks, validated household members,
  and transactional updates. Cookies remember a household; they do not authenticate it.
- Keep attendance databases and session secrets under ignored private/ paths.
- Keep template autoescaping enabled and show safe errors rather than raw exceptions.
- Required assignments are configurable; optional blanks are not errors.
- Never commit .env, credential files, local caches, virtual environments, or private data.
- Check README.md and PROJECT_STATUS.md before changes and update status after work.
- Use codex/ prefix for future feature branches. Do not overwrite remote work.
- Before creating/pushing a repo, verify authenticated identity and intended personal owner.

## Validation (PowerShell, repository root)
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app.py schedule tests
git diff --check
git status --short
git diff --cached --stat
git diff --cached
```
Inspect / and /past at 375 px and desktop width after layout changes. Check long
content for horizontal overflow; keep controls keyboard-accessible.
Tests cover chronology, next gathering, cancellation, blanks, cache TTL, stale/error
states, mapping, DST, escaping, and the read-only Google adapter contract. Attendance
tests cover cookies, individual selections, duplicate responses, CSRF, persistence,
and rejected writes for stale/canceled/past/ambiguous meetings. Exercise real browser
submissions as well: server-only tests cannot validate JavaScript form behavior.
Real Google connectivity requires separately supplied credentials and sheet access.

## Calendar layout
The optional calendar adapter lives in schedule/calendar.py. Keep its rules generic:
year/time/headers/off-date overrides belong in environment configuration. Use only
fictional data in tests/fixtures. Never commit the real sheet ID or copied rows.
The school-year rollover and start time must be explicit. Keep source dates intact;
only apply leader-confirmed off-date overrides. Do not edit the Google Sheet unless
asked. Any local .env.google and private/ notes are ignored and do not transfer by
clone. Live Google API reads were verified on the original workstation. A fresh
clone still needs the user's server-side credentials and private configuration.
