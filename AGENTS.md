# WHCC small group schedule

## Scope
Personal proof of concept for West Houston Christian Church, led by the owner,
his wife Diana, and another member. This is original code in a separate repository.
Never copy company code, configurations, credentials, private data, or chat archives.
The owner authorized admin schedule editing, a new App Backend tab, and attendance
updates in that tab. The original calendar adapter remains read-only. Merge its
changes into the effective schedule without overwriting app edits; require explicit
admin resolution for conflicts. Development SQLite holds local edits and pending sync. Production SQLite is ephemeral;
confirmed App Backend persistence is required before acknowledging writes.

Use Flask, server-rendered Jinja templates, and plain responsive CSS. No frontend
build system. A shared-password admin area is authorized. No member accounts, reminders, payments,
prayer requests, or public
deployment without a new explicit request. Decide website access before using real
group information online. A private sheet does not make the website private.

## Conventions
- Python 3.12+; straightforward modules, explicit names, standard library when practical.
- All meeting times use America/Chicago. Require dates and times; do not invent them.
- Normalize both adapters through the same parser and last-good cache.
- Keep configuration in environment variables, never hardcode real sheet IDs or people.
- Attendance uses a signed browser cookie, CSRF checks, validated household members,
  and transactional updates. Cookies remember a household; they do not authenticate it.
- Keep databases, password hashes, and session secrets under ignored private/ paths.
- Write only the configured backend tab; never edit the original calendar. Write
  literal cell values, never interpret submitted text as spreadsheet formulas.
- Use one Gunicorn worker and Cloud Run service min 0 / max 1. Replacement overlap
  is possible: append optimistic updates, replay only matching predecessor digests,
  never rewrite accepted history. Stop older full-tab writers before migration.
- Preserve revisions, source baselines and stable meeting IDs. Queue local writes
  only in development; production restores Sheets state and rolls back failed writes.
- Admin edits require authentication, expiry, CSRF, validation, and a current revision.
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
Admin/backend tests cover auth, conflict resolution, stale forms, durable pending
writes, lost acknowledgments, restoration, and scoped Google writes.
Real Google connectivity requires separately supplied credentials and sheet access.

## Calendar layout
The optional calendar adapter lives in schedule/calendar.py. Keep its rules generic:
year/time/headers/off-date overrides belong in environment configuration. Use only
fictional data in tests/fixtures. Never commit the real sheet ID or copied rows.
The school-year rollover and start time must be explicit. Keep source dates intact;
only apply leader-confirmed off-date overrides. The requested backend tab may be updated; the original calendar must remain intact. Any local .env.google and private/ notes are ignored and do not transfer by
clone. Live Google API reads were verified on the original workstation. A fresh
clone still needs the user's server-side credentials and private configuration.

## Cloud Run readiness
No deployment/cloud resource creation is authorized by readiness work. Runtime uses
ADC with the assigned service account; do not upload a JSON private key. Keep the
stable SECRET_KEY and separate group/admin hashes in Secret Manager. /health stays
public, minimal, and free of Google calls. Protect every private member/admin route
with the group gate and admin routes independently. ProxyFix trusts only the final
scheme header when explicitly configured behind Cloud Run. No additional workers,
databases, or background infrastructure without deliberate architecture review.
Read the Cloud Run README checklist before any future deployment. Test lost local
storage with the same cookie, strict failed writes, stale overlapping writers,
credential mocks and group/CSRF gates. Never run pre-log app versions on a backend
that contains update events. Container/source-upload ignore files are allowlists;
review them when adding runtime files. Install requirements-dev.txt for validation.
