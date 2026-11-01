# Unified Office companion foundation

This change narrows Workz context before any unified-shell cutover. Enabled
Frappe users must have System Manager, Projects Manager or Projects User roles.
A role alone supplies no project oversight: active Activity assignments expose
only those activities and their necessary project context. Configured project
leads and timesheet approvers retain their existing project scopes. Assignment
revocation is reflected on the next context request; no response cache is added.

No live identity mapping or grants are changed. The synthetic staff A/staff B,
lead and approver fixtures cover sibling activity confidentiality, revocation,
unknown/disabled/Guest identities and existing workflow invariants.

This is **not** the complete unified interface. Project/Activity generic reads,
legacy API scope, document/file/realtime/export auditing and the embedded app
contract remain prerequisites. In particular, the Activity controller's legacy
get_project_activities/get_activity_summary still use elevated get_all reads;
this patch does not claim that context scoping secures those independent routes.

No sidebar or shell changes, redirects or default entry changes are made here.
Office and Workz foundations can ship independently: neither enables embedding.
Workz build: npm ci --prefix workz --include=dev; npm run build --prefix workz.
Office assets are packaged by the separate tm-office Frappe app. A future unified
shell must check a matching server contract and fail closed on missing versions.

Parent task: 69475672-5c8c-4f9e-b4a8-983af50f966b.
Companion task: 26057359-4bcc-4984-9a05-554529d4d029.

Validation: 49 Workz Python tests, 7 Node calendar tests, 697 offline regression
tests and Workz production TypeScript/Vite build passed. Synthetic tests are not
substitutes for HTTP/Socket.IO permission checks on a disposable Frappe site.
Legacy ERPLite Vue production build was not run for this Python-only increment.
