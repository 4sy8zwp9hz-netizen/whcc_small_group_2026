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
- 44 automated tests passed on Python 3.12.14. Python compilation passed.
- Added an optional school-year calendar reader with two-row assignments, header
  mapping, merged event titles, off weeks, optional notes, and footer exclusion.
- Added configurable leader-confirmed off-date overrides and visible warnings
  for other duplicate dates. The original CSV/table mode remains the default.
- Inspected the supplied calendar read-only and prepared ignored .env.google and
  private/GOOGLE_SETUP.md files locally. No real sheet ID, rows, or private connection
  values are tracked. These ignored files must be recreated privately at home.
- Verified the private configuration loads with Flask's routes command; live reads
  still require a service-account key and Viewer access.
- Rechecked the calendar UI with fictional paired assignments at 375 and 1440 px,
  with no horizontal overflow.
- Browser inspection at 375x812 and 1440x1000. Upcoming and past pages checked;
  no horizontal overflow (document widths 360 and 1425, allowing scrollbars).
  Corrected a text-encoding issue found during the first phone inspection.
- Source and tracked-file allowlist reviewed for secrets/unrelated content.
  Only original project code, documentation, and fictional sample data are included.

## Assumptions and tradeoffs
- Default required assignments: discussion leader, host, food, childcare.
- Topic, location, notes, and status are optional; blank location is unconfirmed.
- Meetings become past at their start time (no end time provided).
- Next card intentionally repeats the meeting from the full upcoming list.
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
- No database, user accounts, RSVP, reminders, payments, or prayer requests.
- Actual Google connectivity and a physical phone test remain unverified.

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
1. Supply a personal service account and grant it Viewer access; set the key path
   in an ignored .env.google and verify authenticated live reads and failure recovery.
2. Recreate the private sheet configuration at home using the supplied sheet and
   local private notes. Do not publish these values through Git.
3. Confirm meeting locations separately; a host assignment is not an address.
4. Decide website access and acceptable displayed information before sharing real
   group data online. A private sheet does not make the website private.
5. Test on a physical phone on trusted Wi-Fi.
6. Once explicitly authorized, plan Render secrets, access enforcement, and deployment.
