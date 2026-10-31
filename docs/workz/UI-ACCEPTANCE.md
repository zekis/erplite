# Workz UI acceptance record

31 October 2026. Fictional data only; no live site access, production deployment, migrations or permission changes.

## Route and viewport matrix

Each cell below passed browser assertions for the shared toolbar/workspace and document horizontal containment. Desktop columns additionally assert document vertical containment. Small screens deliberately allow vertical document scrolling. Table contents have labelled, keyboard-focusable contained scrollers.

| Route | 1920×1080 | 1440×900 | 1366×768 | 1024×768 | 768×1024 | 390×844 |
|---|---|---|---|---|---|---|
| Dashboard | Pass | Pass | Pass | Pass | Pass | Pass |
| Projects | Pass | Pass | Pass | Pass | Pass | Pass |
| Planning | Pass | Pass | Pass | Pass | Pass | Pass |
| Timesheet | Pass | Pass | Pass | Pass | Pass | Pass |
| Manage Assignments | Pass | Pass | Pass | Pass | Pass | Pass |
| Pending Approvals | Pass | Pass | Pass | Pass | Pass | Pass |
| Reports | Pass | Pass | Pass | Pass | Pass | Pass |
| Settings | Pass | Pass | Pass | Pass | Pass | Pass |

`workz/e2e/layout.spec.js` checks `documentElement.scrollHeight/clientHeight` and `scrollWidth/clientWidth` with a 2px tolerance. Both calendar routes separately test day/week/month at 1366×768 and 1440×900; workspace starts at or above 120px and ends inside the viewport. The ordinary 1366×768 workspace boundary is 115px. Screenshot evidence complements these assertions.

## Checks

- Production TypeScript/Vite build, including generated assets and cache hashes.
- 697 offline tests passed. The first run found a stale `login` URL exception in `test_api_url_methods.py`; no source calls that URL. Removed the obsolete exception as that regression explicitly requires.
- 47 Workz backend tests passed; backend files unchanged.
- 7 calendar tests passed, including DST gaps/folds, elapsed duration and overlap/multi-day segmentation.
- 22 browser tests passed (final full run: 1.1 minutes). Existing three end-to-end workflows retained and adapted for explicit Settings categories/calendar-vs-table navigation; additional layout/role/accessibility regressions in `layout.spec.js`.
- Real synthetic service workflows cover setup, plan creation, drag create/move, both resize edges after responsive/rail changes, Escape cancellation, overlap rollback, persistence, multi-day/all-day and grabbed overnight segments, Accept/Ignore, rejection correction/resubmission, approval and report reconciliation.
- Layout fixtures cover long names, dense overlapping records, all statuses including Processed, four/five/six-row months, overflow agendas, out-of-hours reveal, stale-save rollback, search and persisted authorised scope, unavailable scope warning, inspector focus containment and Escape, arrow-key view changes, employee/lead/approver/admin Settings capabilities.
- Browser fixture handlers reject unexpected writes. Screenshots contain only fictional labels. Baseline screenshots show the original empty synthetic installation; after screenshots use the documented dense fixture (they are not a same-dataset visual diff).

## Evidence

[Baseline Dashboard](ui-evidence/before-dashboard.png) · [Projects](ui-evidence/before-projects.png) · [Planning](ui-evidence/before-planning.png) · [Timesheet](ui-evidence/before-timesheet.png) · [Assignments](ui-evidence/before-assignments.png) · [Approvals](ui-evidence/before-approvals.png) · [Reports](ui-evidence/before-reports.png) · [Settings](ui-evidence/before-settings.png)

[After Dashboard](ui-evidence/after-dashboard-1366.png) · [Projects](ui-evidence/after-projects-1366.png) · [Planning](ui-evidence/after-planning-1366.png) · [Timesheet](ui-evidence/after-timesheet-1366.png) · [Assignments](ui-evidence/after-assignments-1366.png) · [Approvals](ui-evidence/after-approvals-1366.png) · [Reports](ui-evidence/after-reports-1366.png) · [Settings](ui-evidence/after-settings-1366.png)

The same directory contains day/week/month captures for both calendars at both laptop sizes, plus representative 768px and 390px Planning/Timesheet/Settings captures.

## Limits requiring explicit review

- The existing context API exposes current activity assignments only. Closed/cancelled ToDo records and project-level assignment history cannot be presented accurately without an additional authorised backend read interface. The UI states that limitation and does not create a second store.
- Native browser 200% zoom was not manually verified. Automated 683×384 CSS-viewport reflow exercises the equivalent available space of a 1366×768 laptop at 200%; this is not a claim of native zoom testing. No zoom restriction is installed.
- Tests run in Chromium, not Safari/Firefox or a physical touch device. Screen-reader speech output and a full accessibility audit remain manual review work.
- The inspector is a conditional right-side modal drawer at every width, rather than a permanently docked desktop column. Month overflow uses the same focus-trapped drawer. Week/month can still be deliberately chosen on mobile; day is the initial mobile default.
- Approvals retain explicit individual decisions in a labelled employee/project/date queue; there is no new bulk decision operation. The queue does not yet aggregate submissions into collapsible weekly groups.
- Dashboard keeps the report summary/drilldown with compact actionable links; it does not introduce financial trend charts or new backend metrics. Financial detail remains in Planning's optional panel.
- Stored view/scope/nav preferences are local to the signed-in browser. A deliberate saved week/month choice survives mobile reload; automatic mobile day selection applies when there is no saved choice. Calendar rails use responsive initial state and can be toggled, but their open state is not persisted.

## Preview and reproduce

```sh
npm ci --prefix workz --include=dev
npm run build --prefix workz
python3 tests/workz/server.py
```

Open **http://127.0.0.1:8765/workz**. This is the loopback-only fictional test adapter, not a Frappe production site. Start with the default synthetic Administrator; all records disappear when the server stops. Do not expose this server publicly.

Stop that server before Playwright, which starts its own fresh instance:

```sh
npm run test:offline
npm run test:workz
cd workz
npx playwright install chromium
# Install Chromium OS prerequisites if your machine needs them.
npx playwright test
```

In the Kandev runtime, missing Chromium libraries were extracted under `/tmp/browser-libs` without system changes. Tests used `LD_LIBRARY_PATH=/tmp/browser-libs/root/usr/lib/x86_64-linux-gnu:/tmp/browser-libs/root/lib/x86_64-linux-gnu`.

## Integration/publication

Task branch: `feature/fix-workz-layouts-an-3vc`. Integration target: `main`.

Verified main remains `94fe9b84bd660a8644a5ef8f6d6ed8af00f31c25`; task parent and `fix/crew-history-import` are `0fff3236bd6e0677ca83fdbb3d9a22ef2407d2cd`. This branch includes and depends on #74's Processed-history protection and import child-metadata idempotency. No backend edits remove those fixes. Refresh against main if #74 lands before review; retain its changes.

Publication is blocked: the configured Kandev Git credential helper returns `broker returned HTTP 403: Forbidden` for both credential retrieval and `git push --dry-run origin HEAD:feature/fix-workz-layouts-an-3vc`. PR creation cannot authenticate. No PR link or completed workflow signal is claimed.
