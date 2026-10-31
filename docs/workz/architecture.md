# Workz consolidation into ERPLite

## Inspected boundaries

ERPLite main at ed86561 owns Project, Activity, Planner Entry, Timesheet Entry,
standard Frappe ToDo assignments, accounting and Xero integrations. Afterz develop
at d02c7b20ba10134b89d5173f974c215cdb39ba31 owns the matching Workz React navigation,
planning and timesheet UI and application APIs. Its timesheet employee field links
to User, not HR Employee. Afterz's role policy names Administrator and per-project
timesheet_approver; project_lead is distinct. Neither repository contains an HR
leave approval implementation. Crew is a site mentioned in integration tests, not
an independently verified database/schema inventory. The virtual-office deployment
target is not specified in either repository's accessible deployment documentation.

## Deliverable and policy

Keep one maintained application in ERPLite at /workz. Adapt the Afterz navigation,
logo and blue/slate visual language, retaining the upstream MIT notice. Retain
/erplite scheduler routes for compatibility during transition. New UI uses a single
ERPLite service; no runtime Afterz dependency, no routine Desk prerequisites.
Reuse Project/Activity and standard ToDo assignments (no second assignment table).
Extend Planner Entry for explicit availability/work/leave/holiday kinds. Persist
suggestion decisions separately from actual entries; stable plan ID is the
occurrence identity. Moving a plan never resets a decision. Cancelled plans cease
suggestions; accepted actuals are never rewritten or deleted by plan changes.

Scope: Administrator/System Manager administer identities and setup. Project leads
manage their own project configuration, allocation and finances; timesheet
approvers see/transition their project's time, not global time or pay data.
Employees see their own time and availability. No self-approval. Sensitive rate
history has no employee-readable DocType permissions. History is append-only with
effective dates; missing values remain missing, currencies aggregate separately.

Use database transactions, row locks in stable order, modified-version checks and
unique decision keys for retries/concurrency. No endpoint commits partial work.
New records enforce employee/activity/project eligibility. Existing historical
records remain readable after assignment cancellation or project archival.

## Phases and migration gates

1. Consolidate shell and persisted application service, document schema additions.
2. Implement setup, planning, suggestion/actual workflow, scoped reporting and rates.
3. Exercise synthetic application and migration tests, build UI, review permissions.
4. Inventory source/target installed apps, schema, identity mapping, timezone,
   currency, attachments and audit availability. Obtain source backup and restore
   it to isolated staging. Do not copy live secrets into repository fixtures.
5. Dry run deterministic manifest with explicit source IDs and reviewed mappings;
   reject unresolved references/conflicts. Reconcile counts and decimal hours by
   employee/project/month and original workflow status. Preserve provenance and
   source approval actors/timestamps; importing is never a new approval.
6. Test clean install and staged import, role-separated booking/approval/reporting,
   attachment access and rollback. Review concrete target names and cutover package.
7. Only after separate approval: backup both sides, freeze Crew writes, export
   final delta, import/reconcile, switch access, retain Crew read-only with archive
   access. Restore backup and route back if reconciliation/permissions fail.

No live deployment, migration, source deletion or Crew shutdown is authorized.
Missing inputs: virtual-office bench/site/database and installed app versions;
Crew site/database/export schema and attachment/audit inventory; identity mapping;
source/target timezone and currency settings; leave-policy integration; backup,
retention and acceptance owners. These block live cutover, not reversible code work.
