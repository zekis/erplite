# Workz workspace repair — 31 October 2026

Scope: all eight Workz routes; preserve #72 currency handling, #73 calendar intervals and #74 Processed locks/import idempotency. No backend, production or business data changes.

- Shared 100dvh shell, 212px/60px navigation, 56px title/actions toolbar and compact contextual controls. Controls remain above an independently scrolling workspace. Scoped styles, 4/8/12/16/24px spacing, 14px body, 34px controls, visible focus, locally bundled MDI SVGs.
- Planning/Timesheet: left searchable activity/suggestion rail, flexible calendar, conditional details drawer. One representation at a time. Fit 06–18 to available height; full day scrolls internally; surface out-of-hours counts. Geometry must respond to resize and rail changes, including pointer resize precision.
- Month: labelled Monday–Sunday, bounded equal rows, compact entries and accessible overflow agenda. Details expose all events including locked history; only editable entries offer editing.
- Dashboard/Reports: compact totals, summary and entry drilldown columns. Projects/Assignments: searchable project selection with scoped activity details. Approvals: selectable queue and detail. Settings: category navigation and one focused panel.
- Persist navigation and authorised scope locally per user. Revalidate saved scopes with fresh context. No layout-triggered writes. Short floating success status; persistent dismissible errors. Mobile reflows, uses day initially and collapsible navigation/rails; zoom remains enabled.
- Reuse existing mutation paths, permissions, concurrency handling, rejected correction and canonical assignments. Friendly labels only from authorised context, explicit unavailable fallback.

## Verification contract

Record actual outcomes in UI-ACCEPTANCE.md. Test every route at 1920×1080, 1440×900, 1366×768, 1024×768, 768×1024 and 390×844. Assert document geometry at laptop sizes for day/week/month, six-row and crowded months. Preserve existing offline/backend/calendar/browser checks. Use synthetic fixtures only for before/after evidence and preview. PR targets main and explicitly depends on #74 until integrated.
