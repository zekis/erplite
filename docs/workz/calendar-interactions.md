# Workz calendar interaction restoration

The Projects menu replaces Todos; existing `/workz/todos` links remain valid.
Planning and Timesheet share a day/week time grid, month overview and table view.

- Drag an assigned activity from the palette to create a one-hour allocation or draft actual entry.
- Move an editable block with its grip. Resize either edge in 15-minute increments.
- Click an activity, time slot or editable block for the equivalent form; resize handles also support arrow keys.
- Escape cancels a move or resize. Server conflicts and stale versions leave the saved entry unchanged.
- Submitted/approved actual entries have no move or resize handles. Rejected entries retain their status while being corrected.
- Planning intentions remain separate from actual time and HR leave approval. Suggestions still require explicit acceptance.
- Calendar slots reject missing or repeated DST clock times; the form supports explicit offsets. Moves preserve elapsed duration.
- The default visible hours are 06:00–18:00; Full day exposes overnight hours. Multi-day blocks are clipped at exclusive day boundaries.

Activity cards use the selected employee's active assignments. With All authorized employees selected, new entries use the signed-in employee. Choose an employee to plan/book on their behalf within existing server permissions.

Reference: Afterz develop d02c7b20ba10134b89d5173f974c215cdb39ba31. MIT attribution is retained in AFTERZ-LICENSE.txt.

Validation: TypeScript/Vite production build, seven calendar unit tests (including DST), 44 backend tests, and three Playwright workflows. Browser coverage exercises palette creation, pointer moves, both resize edges, persistence, cancellation, conflict rollback, view changes, approval locks and legacy navigation. All browser data is synthetic and loopback-only.

This UI-only release is based on Currency compatibility PR #72. It requires no database migration or live source-data import and does not change Crew.
