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
- 27 automated tests passed on Python 3.12.14. Python compilation passed.
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
- Google formatted values must match configured Python date/time formats.
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
1. Obtain the real sheet's headers, date/time display formats, tab name, and
   assignment conventions. Configure mapping without committing private data.
2. Supply a personal service account and grant it Viewer access; verify live reads
   and failure recovery using non-sensitive test rows first.
3. Decide website access and acceptable displayed information before sharing real
   group data online. A private sheet does not make the website private.
4. Test on a physical phone on trusted Wi-Fi.
5. Once explicitly authorized, plan Render secrets, access enforcement, and deployment.
