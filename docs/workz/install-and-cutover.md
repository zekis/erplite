# Install, rehearsal and cutover runbook

This is a **review package**, not authorization to deploy or shut down Crew.
Use an isolated bench and synthetic data first. There are no live hostnames,
database credentials or assumed employee-ID mappings in this package.

## Build and install

Supported integration baseline: Frappe 15, MariaDB/InnoDB, Python 3.10+ and Node
18+. Workz is served by the ERPLite app at `/workz`, same origin as Frappe auth
and CSRF. It has no runtime dependency on Afterz. Existing `/erplite` scheduler
routes remain available during migration. Keep the existing Xero app/settings
unchanged; financial planning is not invoice creation.

From this repository:

```sh
npm install
npm run build
npm run test:offline
npm run test:workz
cd workz
npx playwright install --with-deps chromium
npx playwright test
```

`npm install` installs both frontends. The old frontend npm lock had drifted
from its manifest; it is reconciled for reproducible installation. Workz uses
Rollup's WebAssembly build because native Rollup crashed on the task runner.
Committed Workz assets are built from `workz/src`; rebuild after source changes.
The old Vue scheduler remains a compatibility surface, not a second maintained
Workz workflow.

On a **verified isolated** Frappe bench, install this ERPLite branch as an app,
then run the normal `bench --site <isolated-site> install-app erplite` (fresh
site) or `bench --site <isolated-site> migrate` (existing staging site), and
`bench build --app erplite`. Use a site administrator to open `/workz`.
Do not substitute a production site into these commands.

Additive schema changes:

- Planner Entry: kind, activity, timezone, all_day, billable, leave_application,
  workz_start_utc, workz_end_utc.
- Timesheet Entry: workz_start_utc, workz_end_utc. UTC companion fields preserve
  elapsed time through repeated daylight-saving clock times while retaining the
  existing site-local timestamps for integrations. New writes populate both;
  historical records are not silently backfilled. Ambiguous historical local
  timestamps require an explicit reviewed offset before editing/importing.
- Workz Decision: unique per-user/per-plan occurrence decisions and acceptance link.
- Workz Rate: immutable effective-dated pay/project-sell records with currency.
- Workz Audit: append-only actor/employee/time/action/status history.
- Workz Import Map: unique source identity, target identity, source digest, batch
  and original record/archive including supplied historical audit information.

No automatic source import or historical time rewrite runs during migration.
Legacy plans without an Activity cannot be accepted until explicitly corrected;
no guessed Activity backfill. Submitted weeks block new bookings and booking-time edits. Schema fields are additive and old timesheets stay
in their existing DocType. Do not uninstall an app or remove tables as rollback.

## First-run application configuration (no Desk)

1. Settings → Create employee: create supported Frappe User accounts, optionally
   send the standard welcome invitation (requires existing outgoing email setup).
   Edit access enables/disables accounts and assigns supported Projects roles.
   The app deliberately cannot assign System Manager or edit its own admin account.
2. Todos → Create project: select project lead and timesheet approver. Only a site
   administrator/System Manager changes these assignments. Add activities, then
   assign employees. Manage Assignments routes to this same canonical ToDo flow.
3. Settings → Add currency, Add rate version: pay rate is administrator-only;
   sell rate is project-lead scoped. Currency creation does not configure exchange
   conversion. Missing rates stay missing; no pay/sell rates are guessed.
4. Planning → Plan time: work/availability/leave/holiday, table/week/month views.
   Title opens an accessible edit/move/resize form; drag moves a block. All-day
   blocks use midnight-to-midnight exclusive end in their declared timezone.
5. Employee → Timesheet: Accept/Ignore suggestions, or book actual time manually.
   Submit completed drafts; a different authorized approver approves or returns
   them with a reason. Reports and Dashboard share the same totals service.

Leave/holiday calendar blocks are **intentions**, not HR approvals. If HRMS Leave
Application and a mapped Employee are already installed, the in-app request form
uses that document's existing permissions, balance validation and workflow. This
package does not install HRMS or invent a leave approval policy. Verify the target's
actual leave implementation and employee mapping before promising HR integration.
SMTP, identity-provider setup, initial administrator bootstrap and schema migration
remain infrastructure operations. Core Workz booking needs no HRMS Employee row.

## Migration manifest and preflight

`synthetic-manifest.json` is fabricated test data. Run without Frappe:

```sh
python3 -m erplite.workz.migration docs/workz/synthetic-manifest.json
```

Version 1 manifest fields: `source_site`, `batch_id`, IANA `timezone`, `identity_map`,
and `records`. Each record has `doctype`, `source_id`, `fields`, optional
`audit_history`, and optional `attachments` (`path`, `sha256`). Attachment paths
are relative to the manifest directory and may not escape it. Original records
are archived verbatim in Workz Import Map; original audit actors/times are not
represented as newly executed approval actions.

Supported record types: User, Project, Activity, ToDo, Planner Entry, Timesheet
Entry, Workz Rate. Required relationships are translated through explicit
`<DocType>:<source-id>` mappings. An `identity_map` entry names a reviewed existing
destination record. Matching email does not silently merge identities. Only
Projects User is automatically given to newly imported users; original source
roles remain archived for separate authorization review.

Unknown source types, missing references, duplicate IDs, mismatched declared
hours, missing approval provenance, active timers, missing/changed attachments
and changed previously imported records are exceptions, not silently repaired.
Rates are never inferred. Inventory currencies and other linked source-specific
DocTypes before export; the importer refuses missing mandatory destination data.
The source must be exported from a verified schema inventory. An Afterz git
checkout is not proof of Crew's installed schema or customizations.

On isolated staging only, preflight with:

```sh
bench --site <isolated-site> execute erplite.workz.migration.import_manifest \
  --kwargs '{"path":"/absolute/path/to/reviewed-manifest.json","apply":false}'
```

Review every exception and source→destination mapping. Then apply to that same
isolated staging site with `apply:true`. Identical imported records are skipped;
a changed record is a conflict requiring review, never an overwrite. The import
checks target hours/status/counts by employee/project/month before success.
Cross-month durations are split at midnight in source timezone using decimal
hours. A record spanning months counts once in each affected monthly bucket.

The import runs one transaction; errors trigger a full rollback, including
Frappe's attachment rollback callbacks. Batch map records identify imported rows.
Keep a database **and private/public files** backup before import. Rehearse full
backup restoration rather than deleting imported rows that may now have new links.
This package intentionally provides no destructive one-click rollback or shutdown.

## Final cutover gates (not executed)

Verify the virtual-office bench/site/database/app versions and Crew's actual
source site/database/apps/custom fields/integrations, user identity mappings,
timezones, currencies, historical approval/submission/audit sources and attachment
inventory. Run the same workflow under distinct employee/lead/approver/admin
accounts on the target Frappe runtime, including concurrent acceptance and moves.
Check direct REST access as well as UI actions. Test invitation delivery and any
installed HR leave workflow separately using synthetic identities.

After the owner reviews targets, staging evidence and backups: freeze source
writes, take final backup/export, review and import the final delta, reconcile
counts/hours/statuses/attachments, switch access, and retain Crew read-only with
archive access. Keep rollback routing and backups until acceptance. Never retire
Crew merely because a PR was merged. No deployment, live import or shutdown was
performed as part of this development task.

## Validation and reproducibility

See [validation.md](validation.md) for the executed checks and screenshots.
The real database scripts refuse sites without a `workz-synthetic` name prefix.
With this checkout and Frappe installed in a disposable bench virtualenv:

```sh
SITE=workz-synthetic.localhost SITES_PATH=/absolute/bench/sites \
  FRAPPE_BENCH_ROOT=/absolute/bench \
  /absolute/bench/env/bin/python tests/workz/frappe_smoke.py
SITE=workz-synthetic.localhost SITES_PATH=/absolute/bench/sites \
  FRAPPE_BENCH_ROOT=/absolute/bench \
  /absolute/bench/env/bin/python tests/workz/frappe_dst_smoke.py
```

The DST test temporarily changes only that synthetic site's timezone and restores
it. The integration script creates uniquely named synthetic records and commits
independent transactions to test genuine database contention. Use a disposable
site; it intentionally does not erase its audit evidence. Database/Redis setup and
Frappe installation are prerequisites, not mocked by these scripts.
