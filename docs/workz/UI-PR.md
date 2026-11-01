# Prepared PR: Repair Workz shell, calendars and route layouts

Target: `main`; head: `feature/fix-workz-layouts-an-3vc`.

Workz calendars previously began below stacked headings/filter cards and repeated the entire entry table underneath. This change introduces a compact shared shell and toolbar, responsive left activity/suggestion rail, conditional details drawer, bounded day/week/month workspace and an explicit table alternative. It also reorganises Projects/Assignments as master/detail, Reports as summary/drilldown columns, Approvals as a selection queue, and Settings into categories. Navigation is direct and persistent; authorised friendly labels replace primary hash IDs. Local MDI SVGs replace react-icons/md.

Calendar resize gestures now use the rendered time scale. Existing backend mutation/permission/locking/concurrency paths remain unchanged. View switching is local and does not issue preference writes; routine Settings preference changes still use the existing endpoint. Production bundles and cache versions are included.

**Dependency:** this branch starts at #74 (`0fff323`), not main (`94fe9b8`), to retain Processed-history protection and child-table import idempotency. The PR comparison against main will include that dependency until #74 lands. Refresh the task branch after integration; do not drop these fixes. Currency and calendar interaction compatibility remain covered by existing suites.

Validation and fictional screenshots: [acceptance record](UI-ACCEPTANCE.md), [specification](UI-SPEC.md). Build, 697 offline tests, 47 backend tests and 7 calendar tests and 22 browser tests passed. Browser suite retains real synthetic service workflows and adds route/breakpoint geometry, month overflow, scope and lock regressions.

Review limits are listed explicitly in the acceptance record: current-only assignment API, native 200% zoom/manual accessibility/cross-browser verification, individual rather than weekly-grouped approval queue, modal rather than docked inspector. No production deployment, migration, live mutation, merge or auto-merge.

Publication note: this file is a prepared description, not an existing PR. Kandev's credential broker currently rejects authentication with HTTP 403.
