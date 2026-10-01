# Project status

Updated: 2026-10-01

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
- Git exclusions, .env.example, Windows/Wi-Fi instructions, future Render command.
- 74 automated tests passed on Python 3.12.14. Python compilation passed.
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
- Production still needs website access decisions, durable storage, HTTPS cookie
  settings, and a stable signing secret. No public app deployment was performed.

## Assumptions and tradeoffs
- Default required assignments: discussion leader, host, food, childcare.
- Topic, location, notes, and status are optional; blank location is unconfirmed.
- Meetings become past at their start time (no end time provided).
- This week is featured above navigation, including off weeks or already-started
  gatherings. Otherwise the next gathering is featured; it is not duplicated.
- Sample dates are fixed in September-November 2026.
- Refreshes happen on page requests; cache does not survive process restarts.
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
- SQLite stores attendance separately; the Google Sheet remains read-only.
- No user accounts, reminders, payments, or prayer requests.
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
7. Once explicitly authorized, plan Render secrets, durable attendance storage,
   access enforcement, and deployment.
