# Workz / Virtual Office integration (contract 1)

Workz remains the sole work-record API and calendar/editor implementation. The
Office shell mounts the existing modules at /workz paths with office=1. The
server checks permitted module routes and the installed Office contract before
emitting an embedded boot. Embedded React uses memory routing, has no sidebar or
app header, and reports route/dirty/readiness messages to the same-origin shell.
Existing /workz bookmarks preserve supported period and filter parameters when
redirected to /virtual-office; /erplite becomes the unified entry when both apps
are installed. Unsupported utility routes retain their existing entry points.

The Office shell's locally bundled font faces are reused. No CDN or second data
store is introduced. Existing calendar interactions, concurrency, history locks,
DST logic, imported IDs and report calculations are retained.

Enabled Frappe identities require configured Projects User/Manager or System
Manager roles. Dedicated agent readers cannot enter the human work surface.
Ordinary staff context includes only active assigned activities and necessary
project context. Leads/approvers retain existing explicit project scopes.
Generic Project/Activity reads are scoped to configured leaders/approvers (staff
use the safe context projection); assignment reads are restricted separately.
Legacy elevated project/scheduler RPCs are admin-only, including v1/v2 method
paths. This is a compatibility restriction: non-admin integrations using legacy
RPCs must migrate to scoped Workz APIs. No live user role is changed.

Office has separate Frappe packaging and a Vue build; Workz assets are committed
under erplite/public/workz. Review/install this companion before Office migration
and asset packaging. Missing contract versions fail closed. ERPLite main's
existing automatic deployment is not triggered by this task; nothing is merged.

Parent PR: https://github.com/zekis/tm-office/pull/7
Companion task: 26057359-4bcc-4984-9a05-554529d4d029.
Parent task: 69475672-5c8c-4f9e-b4a8-983af50f966b.

Validation: Workz TypeScript/Vite production build, 54 synthetic Python tests,
7 Node calendar tests and 697 offline regressions pass. No actual Frappe HTTP,
Socket.IO, File download/export or exact-commit cross-app deployment test ran:
this runtime has no disposable Frappe site. Those are required release gates,
particularly Frappe DocShare fallback and generic endpoint behavior. Office's
main/deployed appearance cannot be compared because the deployed site returns
HTTP 403. No live business data is copied into this change.

Publishing remains blocked by the configured helper/managed gh repository scope
mismatch. Preserve the commit in a credential-free bundle until Kandev grants
this attached repository its own credential scope; never reuse Office's token.
