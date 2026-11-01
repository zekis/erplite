# Workz / Virtual Office integration (contract 2)

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

Validation on disposable Frappe 15.122.0 with MariaDB 10.11 and Redis 7:
- Workz TypeScript/Vite production build; 59 synthetic Python tests; 7 Node calendar tests.
- `tests/workz/frappe_scope_security.py`: 233 real WSGI requests through Frappe's
  authentication, HTTP dispatch and database. Generic v1/v2 get/list/count,
  search/export, hostile read/write/share/everyone grants, private File reads
  and downloads, attachment relinking, assignment-reference forgery, scope
  revocation, mapped/unmapped/guest identities, valid scoped leads/approvers,
  legacy RPC cmd/call/controller paths and standalone realtime restrictions.
- `tests/workz/frappe_smoke.py`: eight concurrent accepts create one time entry;
  reject/correct/resubmit/approve, report/finance totals and import reconciliation.
- `tests/workz/frappe_dst_smoke.py`: real MariaDB preserves 1.5 hours across a
  repeated clock hour; later bookings work while submitted/approved weeks stay
  locked. Timezone is injected into Frappe's request-local settings cache; no
  global site timezone or production configuration is changed.
- Generic HTTP edits/deletes of Submitted, Approved and Processed history fail.

No production data, identity grants, deployment or merge was used. The parent
owns combined Office HTTP/Socket.IO checks and independent final review.

Companion PR: https://github.com/zekis/erplite/pull/76. Publication uses the
companion task's ERPLite-scoped managed helper. Both PRs remain draft until the
required disposable Frappe integration and security checks pass.

Scope denials raise PermissionError: returning False alone allows Frappe to
restore access through DocShare. Query guards also reject conflicting read
shares before Frappe can OR them around scope predicates. Existing shares do
not survive scope revocation as an alternate access path; generic lists fail
closed until an administrator removes a conflicting share. Scoped Workz
projections remain available. Ordinary staff cannot delegate Workz access using
share grants. Permitted scoped leads/approvers and administrators retain their
existing access.


The assignment API uses the canonical ToDo controller directly. Frappe's generic
assignment helper auto-shares the full Activity with its assignee, which violates
the projection-only staff policy. ToDo hooks still maintain assignment comments
and `_assign`; no duplicate record store is introduced.

Legacy RPC policy executes through `auth_hooks` after API-key authentication.
Frappe's `before_request` executes too early for API-key administrators. Both the
URL and form `cmd` are checked because cmd takes dispatch precedence.

Contract 2 is required on both sides; contract 1 is rejected. The tracked Workz
assets include the matching ready/route/dirty handshake version. Both File
controller overrides compose Office and Workz attachment policies explicitly,
so the last-installed override cannot erase the other app's veto.

All human Socket.IO handshakes/subscriptions are denied by this companion,
including administrators. Workz uses authenticated HTTP polling, so admin data
access and oversight remain available without a persistent unrevocable channel.
The Office companion must apply the same policy. Rollout must restart realtime
once to evict connections established before these hooks existed. This is a
required deployment step; no deployment or restart is performed by this task.
Keep both PRs draft until the parent verifies the exact pair and completes its
independent review.

Work-record attachments must be private at insertion and validation; attempts to
publish a confidential blob or change an existing attachment to public fail.
API/workspace/private-download responses use `private, no-store` with Cookie
and Authorization variation, so revoked access is not restored from a cached
private response. The real suite checks rejected public uploads leave no blob.

File visibility is checked in both controller overrides before core
`before_insert`/`validate`, as well as in document events. Eight real-framework
call-order assertions cover both app overrides and both protected parent types,
proving the core write/move method is never reached for a public attachment.
Existing public confidential blobs require rollout inventory/remediation;
Python guards cannot protect static blobs already served by the web server.

The legacy frontend production build must also run in the deployment checkout:
`npm ci --prefix frontend --legacy-peer-deps --include=dev` followed by
`npm run build --prefix frontend`. It generates the intentionally ignored
`erplite/www/erplite.html`; without it Frappe returns 404 before invoking the
redirect controller. This build passed in the scoped checkout. Real Frappe
requests now verify `/erplite` redirects to Office and the old scheduler route
preserves its planning date context.
