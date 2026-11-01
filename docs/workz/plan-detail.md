# Native Office plan editor contract

Companion for Office task `2486eaad-ff5d-4219-b0a1-d53451010243`.
Call `erplite.workz.api.run` with `action="plan_detail"` and
`payload={"name":"<Planner Entry name>"}` (a JSON string is also accepted).
Frappe wraps the returned object in the normal RPC `message` envelope.

The returned object has the same explicit public fields as a `plans` row:
`name`, `user`, `title`, `project`, `activity`, `kind`, `plan_start`, `plan_end`,
`duration_hours`, `timezone`, `all_day`, `billable`, `modified`, `status`,
`leave_application`. It additionally contains boolean `notes_editable`.
Only when that flag is true is `notes` present (the stored text or null).
`modified` is the existing concurrency token; return it unchanged on save.
Dates use the existing calendar ISO instant projection, including UTC shadows
for DST folds and the legacy duration fallback when no end is stored.

`notes_editable` means the authenticated user is the plan employee (`user`)
or an administrator under existing policy (Administrator or System Manager).
It is separate from permission to edit shared work allocations. Managers and
approvers can read only their existing scope, receive no `notes` key, and must
omit notes on save. Personal title/leave-link redaction matches `plans`.
The action rechecks authenticated/enabled/mapped-user policy, Project read,
and `can_read_plan` on every call; it introduces no DocShare or grant handling.

`save_plan` preserves omitted notes and removes notes from its response for
nonowners/nonadmins, also returning `notes_editable`. The document validation
hook rejects private-note changes by other users, including direct document
writes and cancellation. Empty and null both mean no note; unchanged notes
are allowed. Allocation permissions and stale-token checks remain in force.

Validation for this change:
- Workz Python suite: 68 tests, including seven new focused tests covering
  scopes, revocation, notes, stale writes, DST projection and legacy duration.
- Workz calendar JavaScript suite: seven tests, including DST.
- Real Frappe/MariaDB: `frappe_plan_detail_smoke.py` passed on the existing
  localhost-only disposable `workz-synthetic-office.local` site, importing
  this checkout via PYTHONPATH. All synthetic fixtures were rolled back.
  Covers owner/System Manager, shared-reader redaction, unrelated denial,
  manager save redaction, note preservation, direct guard/cancellation,
  stale modified denial, lead/approver revocation and disabled-user denial.
- Production builds: Workz TypeScript/Vite and legacy Vue frontend.

The real-site check exercises the application boundary and document hooks,
not an Office browser flow or HTTP authentication. No deployment, production
records, production grants, HR changes, or Crew operations are part of this PR.
Parent review and merge precede the coordinated Office release.

Additional broad offline scan: 697 tests ran, 693 passed, four failed. Three
failures reproduce on untouched `origin/main` (`220ad36`): the DocShare fixture
allowlist, the pinned `new_doc` count, and the class-based ScopedFile hook
resolver. The fourth scans generated legacy frontend assets and rejects
Frappe's `/api/method/login`; it also reproduces on the base with the same
unchanged frontend build artifact. These unrelated static-harness limitations
are outside this dependency PR. Legacy build warnings concern stale Browserslist
data and chunk size; both builds exit successfully.
