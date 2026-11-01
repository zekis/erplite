/// <reference types="vite/client" />
import React, { useState, useEffect, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, MemoryRouter, useLocation, Navigate, Link } from "react-router-dom";
import Sidebar from "./Sidebar";
import SettingsPage from "./SettingsPage";
import Editor, { Field } from "./Editor";
import TimeCalendar, { CalendarEvent, PaletteItem } from "./TimeCalendar";
import { api, Row } from "./api";
import {
  period,
  localDate,
  localInput,
  toInstant,
  offsetFor,
  zoned,
} from "./calendar.mjs";
import "./style.css";
import {
  Toolbar,
  TopActions,
  Table,
  Icon,
  IconButton,
  ViewSwitch,
  ScopeSelect,
} from "./ui";

const embedded = window.workzBoot?.office_contract === 1;
const routeParams = new URLSearchParams(location.search);
if (embedded) {
  // Reuse the shell's locally bundled font faces rather than downloading fonts.
  try {
    const faces = Array.from(window.parent.document.styleSheets).flatMap(sheet => {
      try { return Array.from(sheet.cssRules).filter(rule => rule.type === CSSRule.FONT_FACE_RULE).map(rule => rule.cssText.replace(/url\(["']?([^"')]+)["']?\)/g, (_, url) => `url("${new URL(url, sheet.href || window.parent.document.baseURI).href}")`)); }
      catch { return []; }
    });
    const style = document.createElement('style'); style.textContent = faces.join('\n'); document.head.append(style);
  } catch { /* same-origin shell unavailable: system fallback remains readable */ }
}
const opts = (rows: Row[], key = "name", label = "name") =>
  rows.map((r) => ({ value: r[key], label: r[label] || r[key] }));
const storageKey = "workz-ui:" + (window.workzBoot?.user || "user");
const saved = (() => {
  try {
    return JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    return {};
  }
})();
const today = localDate(new Date()),
  tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
const number = (value: any) =>
  Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
function Empty({ text = "No records in this period." }: { text?: string }) {
  return <p className="empty">{text}</p>;
}
function App() {
  const path = useLocation().pathname;
  const [ctx, setCtx] = useState<Row | null>(null),
    [date, setDate] = useState(routeParams.get("date") || saved.date || today),
    [view, setView] = useState(
      routeParams.get("view") || saved.view || (innerWidth < 768 ? "day" : "week"),
    ),
    [expanded, setExpanded] = useState(saved.expanded ?? innerWidth >= 1280);
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("People & access"),
    [selection, setSelection] = useState(""),
    [projectStatus, setProjectStatus] = useState("Active");

  const [data, setData] = useState<Row>({
    plans: [],
    entries: [],
    suggestions: [],
    report: { employees: [], totals: {} },
    finance: { currencies: {}, missing: [] },
  });
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [scopeWarning, setScopeWarning] = useState(""),
    [notice, setNotice] = useState(""),
    [editor, setEditor] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [employee, setEmployee] = useState(routeParams.get("employee") || saved.employee || ""),
    [project, setProject] = useState(routeParams.get("project") || saved.project || ""),
    [history, setHistory] = useState<Row[]>([]);
  useEffect(() => {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ date, view, expanded, employee, project }),
      );
    } catch {}
  }, [date, view, expanded, employee, project]);
  useEffect(() => {
    if (notice === "Saved. Totals refreshed.") {
      const timer = setTimeout(() => setNotice(""), 4000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  const reportPage = path === "/" || path.endsWith("/reports"),
    planning = path === "/planning",
    todos =
      path === "/projects" ||
      path === "/todos" ||
      path.endsWith("/assignments"),
    settings = path === "/settings";
  const rawRange = period(
    date,
    reportPage ? "month" : view === "table" ? "week" : view,
  );
  const range = reportPage
    ? {
        ...rawRange,
        start: zoned(rawRange.days[0] + " 00:00:00", ctx?.timezone || tz),
        end: zoned(
          localDate(new Date(rawRange.end)) + " 00:00:00",
          ctx?.timezone || tz,
        ),
      }
    : rawRange;
  const requestId = useRef(0);
  const preferencesReady = useRef(false);
  const load = useCallback(async () => {
    const current = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const c = await api("context");
      if (current !== requestId.current) return;
      setCtx(c);
      if (
        (employee && !c.users.some((u: Row) => u.name === employee)) ||
        (project && !c.projects.some((p: Row) => p.name === project))
      ) {
        setEmployee("");
        setProject("");
        setScopeWarning(
          "Saved scope is no longer available. Showing your authorised scope.",
        );
        return;
      }
      if (!preferencesReady.current) {
        preferencesReady.current = true;
        const preference = JSON.parse(c.preferences || "{}").view;
        if (
          !saved.view &&
          innerWidth >= 768 &&
          ["day", "week", "month", "table"].includes(preference)
        )
          setView(preference);
      }
      const [plans, entries, suggestions, report, finance] = await Promise.all(
        ["plans", "times", "suggestions", "report", "financials"].map((a) =>
          api(a, {
            ...range,
            employee: employee || undefined,
            project: project || undefined,
          }),
        ),
      );
      const convert = (row: Row) => {
        const r = { ...row };
        for (const k of [
          "plan_start",
          "plan_end",
          "check_in_time",
          "check_out_time",
        ])
          if (r[k]) r[k] = zoned(r[k], c.timezone);
        return r;
      };
      if (current !== requestId.current) return;
      setData({
        plans: plans.map(convert),
        entries: entries.map(convert),
        suggestions: suggestions.map(convert),
        report,
        finance,
      });
    } catch (e) {
      if (current === requestId.current) { setCtx(null); setEditor(null); setData({plans:[],entries:[],suggestions:[],report:{employees:[],totals:{}},finance:{currencies:{},missing:[]}}); setError((e as Error).message); }
    } finally {
      if (current === requestId.current) setLoading(false);
    }
  }, [range.start, range.end, employee, project]);
  const refresh = useRef(load);
  refresh.current = load;
  useEffect(() => {
    load();
  }, [load, path]);
  useEffect(() => {
    const poll = window.setInterval(() => { if (!document.hidden && !editor && !busy) refresh.current(); }, 30000);
    return () => clearInterval(poll);
  }, [editor, busy]);
  useEffect(() => {
    if (!embedded || !ctx) return;
    window.parent.postMessage({type:'office:workz-ready',version:1},location.origin);
    const params = new URLSearchParams({date, view, employee, project});
    window.parent.postMessage({type: 'office:workz-route', version: 1, path, query: params.toString()}, location.origin);
  }, [path, date, view, employee, project, !!ctx]);
  async function mutate(action: string, payload: Row) {
    setBusy(true);
    setNotice("");
    try {
      await api(action, payload);
      await refresh.current();
      setNotice("Saved. Totals refreshed.");
    } catch (error) {
      if ((error as any).status === 403) { setEditor(null); await refresh.current(); }
      throw error;
    } finally {
      setBusy(false);
    }
  }
  async function act(action: string, payload: Row) {
    try {
      await mutate(action, payload);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function open(
    title: string,
    action: string,
    fields: Field[],
    initial: Row = {},
    transform?: (v: Row) => Row,
  ) {
    setEditor({
      title,
      fields,
      initial,
      onSave: async (v: Row) => mutate(action, transform ? transform(v) : v),
    });
  }
  if (path === "/todos" || path.startsWith("/todos/"))
    return <Navigate to="/projects" replace />;
  if (!ctx)
    return (
      <main className="boot">
        <h1>Workz</h1>
        {loading ? (
          <p role="status">Loading your workspace…</p>
        ) : (
          <>
            <p role="alert">{error}</p>
            <button onClick={load}>Retry</button>
          </>
        )}
      </main>
    );
  const projects = ctx.projects as Row[],
    activities = ctx.activities as Row[],
    users = ctx.users as Row[];
  const managed = (name: string) =>
    ctx.admin || ctx.managed_projects.includes(name);
  const canApprove = (row: Row) =>
    row.employee !== ctx.user &&
    (ctx.admin || ctx.approval_projects.includes(row.project));
  const projectField: Field = {
    key: "project",
    label: "Project",
    options: opts(
      projects.filter((p) => p.status !== "Archived"),
      "name",
      "project_name",
    ),
  };
  const activityField: Field = {
    key: "activity",
    label: "Activity (must belong to chosen project)",
    options: opts(activities, "name", "activity_name"),
  };
  const userField: Field = {
    key: "employee",
    label: "Employee",
    options: opts(users, "name", "full_name"),
  };
  function planEditor(row: Row = {}, day = date) {
    const start = row.plan_start
        ? new Date(row.plan_start)
        : new Date(day + "T09:00:00"),
      end = row.plan_end ? new Date(row.plan_end) : new Date(day + "T17:00:00");
    open(
      row.name ? "Edit / move / resize plan" : "Plan time",
      "save_plan",
      [
        { key: "title", label: "Title" },
        {
          key: "kind",
          label: "Kind",
          options: ["Work", "Availability", "Leave", "Holiday"].map(
            (value) => ({ value, label: value }),
          ),
        },
        { ...userField, key: "user" },
        { ...projectField, required: false },
        { ...activityField, required: false },
        { key: "plan_start", label: `Start (${tz})`, type: "datetime-local" },
        {
          key: "plan_end",
          label: `End, exclusive (${tz})`,
          type: "datetime-local",
        },
        {
          key: "all_day",
          label: "All day (use midnight to midnight)",
          type: "checkbox",
        },
        { key: "billable", label: "Billable work", type: "checkbox" },
        {
          key: "start_offset",
          label: "UTC offset for start (optional)",
          required: false,
        },
        {
          key: "end_offset",
          label: "UTC offset for end (optional)",
          required: false,
        },
        { key: "notes", label: "Notes", required: false },
      ],
      {
        kind: "Work",
        user: employee || ctx!.user,
        project: project || undefined,
        billable: true,
        timezone: tz,
        ...row,
        start_offset: row.plan_start ? offsetFor(start) : "",
        end_offset: row.plan_end ? offsetFor(end) : "",
        plan_start: localInput(start),
        plan_end: localInput(end),
      },
      (v) => ({
        ...v,
        plan_start: toInstant(v.plan_start, v.start_offset),
        plan_end: toInstant(v.plan_end, v.end_offset),
      }),
    );
  }
  function timeEditor(row: Row = {}) {
    open(
      row.name
        ? "Edit draft"
        : `Book actual time · ${userName(employee || ctx!.user)}`,
      "save_time",
      [
        projectField,
        activityField,
        {
          key: "check_in_time",
          label: `Start (${tz})`,
          type: "datetime-local",
        },
        { key: "check_out_time", label: `End (${tz})`, type: "datetime-local" },
        {
          key: "start_offset",
          label: "UTC offset for start (optional)",
          required: false,
        },
        {
          key: "end_offset",
          label: "UTC offset for end (optional)",
          required: false,
        },
        { key: "description", label: "Description", required: false },
      ],
      {
        employee: employee || ctx!.user,
        project: project || undefined,
        ...row,
        start_offset: row.check_in_time
          ? offsetFor(new Date(row.check_in_time))
          : "",
        end_offset: row.check_out_time
          ? offsetFor(new Date(row.check_out_time))
          : "",
        check_in_time: localInput(
          row.check_in_time
            ? new Date(row.check_in_time)
            : new Date(date + "T09:00"),
        ),
        check_out_time: localInput(
          row.check_out_time
            ? new Date(row.check_out_time)
            : new Date(date + "T17:00"),
        ),
      },
      (v) => ({
        ...v,
        check_in_time: toInstant(v.check_in_time, v.start_offset),
        check_out_time: toInstant(v.check_out_time, v.end_offset),
      }),
    );
  }
  function projectEditor(row: Row = {}) {
    open(
      row.name ? "Edit project" : "Create project",
      "save_project",
      [
        { key: "project_name", label: "Project name" },
        {
          key: "status",
          label: "Status",
          options: ["Opportunity", "Estimate", "Open", "Archived"].map(
            (value) => ({ value, label: value }),
          ),
        },
        ...(ctx!.admin
          ? [
              {
                ...userField,
                key: "project_lead",
                label: "Project lead",
                required: false,
              },
              {
                ...userField,
                key: "timesheet_approver",
                label: "Timesheet approver",
                required: false,
              },
            ]
          : []),
      ],
      { status: "Open", project: project || undefined, ...row },
    );
  }
  function activityEditor(row: Row = {}) {
    open(
      row.name ? "Edit activity" : "Create activity",
      "save_activity",
      [
        projectField,
        { key: "activity_name", label: "Activity name" },
        {
          key: "status",
          label: "Status",
          options: ["Open", "Complete", "Closed", "Cancelled"].map((value) => ({
            value,
            label: value,
          })),
        },
      ],
      { status: "Open", project: project || undefined, ...row },
    );
  }
  const filteredPlans = data.plans.filter(
    (r: Row) =>
      (!employee || r.user === employee) && (!project || r.project === project),
  );
  const scopedTime = data.entries.filter(
    (r: Row) =>
      (!employee || r.employee === employee) &&
      (!project || r.project === project) &&
      (path.endsWith("/approvals") ? r.status === "Submitted" : true),
  );
  const approvalPage = path.endsWith("/approvals");
  const approvalSelection = scopedTime.some((r: Row) => r.name === selection)
    ? selection
    : scopedTime[0]?.name;
  const filteredTime = approvalPage
    ? scopedTime.filter((r: Row) => r.name === approvalSelection)
    : scopedTime;
  const title =
    path === "/"
      ? "Dashboard"
      : planning
        ? "Planning"
        : todos
          ? path.endsWith("/assignments")
            ? "Manage Assignments"
            : "Projects"
          : settings
            ? "Settings & people"
            : path.endsWith("/reports")
              ? "Monthly reports"
              : path.endsWith("/approvals")
                ? "Pending approvals"
                : "Timesheet";
  const selectedEmployee = employee || ctx.user;
  const projectName = (name: string) =>
    projects.find((p) => p.name === name)?.project_name ||
    "Unavailable project";
  const activityName = (name: string) =>
    activities.find((a) => a.name === name)?.activity_name ||
    "Unavailable activity";
  const userName = (name: string) =>
    users.find((u) => u.name === name)?.full_name || "Unavailable person";
  const visibleProjects = projects.filter(
    (p) =>
      (projectStatus === "All" ||
        (projectStatus === "Archived"
          ? p.status === "Archived"
          : p.status !== "Archived")) &&
      p.project_name.toLowerCase().includes(query.toLowerCase()),
  );
  const selectedProject = project || visibleProjects[0]?.name;
  const assignedActivities = activities.filter(
    (a) =>
      a.status === "Open" &&
      (!project || a.project === project) &&
      projects.some((p) => p.name === a.project && p.status !== "Archived") &&
      ctx.assignments.some(
        (assignment: Row) =>
          assignment.allocated_to === selectedEmployee &&
          assignment.reference_name === a.name,
      ),
  );
  const palette: PaletteItem[] = assignedActivities.map((a) => ({
    id: a.name,
    title: a.activity_name,
    subtitle: projectName(a.project),
    kind: "Work",
    row: planning
      ? {
          title: a.activity_name,
          kind: "Work",
          user: selectedEmployee,
          project: a.project,
          activity: a.name,
          billable: true,
          timezone: tz,
        }
      : {
          employee: selectedEmployee,
          project: a.project,
          activity: a.name,
          description: a.activity_name,
        },
  }));
  if (planning && (selectedEmployee === ctx.user || ctx.admin))
    for (const kind of ["Availability", "Leave", "Holiday"])
      palette.push({
        id: kind,
        title: kind,
        kind,
        subtitle: "Personal calendar block",
        row: {
          title: kind,
          kind,
          user: selectedEmployee,
          billable: false,
          timezone: tz,
        },
      });
  const calendarEvents: CalendarEvent[] = planning
    ? filteredPlans.map((r: Row) => ({
        id: r.name,
        title: r.title || activityName(r.activity) || r.kind,
        start: r.plan_start,
        end: r.plan_end,
        kind: r.kind,
        subtitle: `${userName(r.user)} · ${r.project ? projectName(r.project) : r.kind}`,
        allDay: !!r.all_day,
        row: r,
        editable:
          r.user === ctx.user ||
          ctx.admin ||
          (r.kind === "Work" && managed(r.project)),
      }))
    : filteredTime
        .filter((r: Row) => r.check_out_time)
        .map((r: Row) => ({
          id: r.name,
          title: activityName(r.activity) || r.description || "Actual time",
          start: r.check_in_time,
          end: r.check_out_time,
          kind: r.status,
          subtitle: `${r.status} · ${userName(r.employee)} · ${projectName(r.project)}`,
          row: r,
          editable:
            ["Draft", "Rejected"].includes(r.status) &&
            (r.employee === ctx.user ||
              ctx.admin ||
              ctx.approval_projects.includes(r.project)),
        }));
  function editCalendarEvent(event: CalendarEvent) {
    if (planning)
      planEditor({
        ...event.row,
        plan_start: event.start,
        plan_end: event.end,
      });
    else
      timeEditor({
        ...event.row,
        check_in_time: event.start,
        check_out_time: event.end,
      });
  }
  function changePeriod(direction: number) {
    const next = new Date(date + "T12:00");
    if (view === "month" || reportPage) {
      next.setDate(1);
      next.setMonth(next.getMonth() + direction);
    } else next.setDate(next.getDate() + direction * (view === "day" ? 1 : 7));
    setDate(localDate(next));
  }
  const periodControls = (
    <div className="calendar-navigation">
      <button onClick={() => changePeriod(-1)} aria-label="Previous period">
        <Icon name="previous" />
      </button>
      <details className="period-picker">
        <summary className="period-label">
          {new Date(range.days[0] + "T12:00").toLocaleDateString([], {
            month: "short",
            day: "numeric",
          })}{" "}
          –{" "}
          {new Date(
            range.days[range.days.length - 1] + "T12:00",
          ).toLocaleDateString([], {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </summary>
        <label>
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => {
              if (e.target.value) setDate(e.target.value);
            }}
          />
        </label>
      </details>
      <button onClick={() => setDate(today)}>Today</button>
      <button onClick={() => changePeriod(1)} aria-label="Next period">
        <Icon name="next" />
      </button>
    </div>
  );
  const calendarControls = (
    <div className="calendar-controls">
      <ViewSwitch
        label={planning ? "Planning view" : "Timesheet view"}
        value={view}
        onChange={setView}
      />
      {periodControls}
    </div>
  );
  const calendar = (
    <TimeCalendar
      onNavigateDate={setDate}
      summary={
        <>
          <span>
            New {planning ? "plans" : "entries"} for{" "}
            {userName(selectedEmployee)}
          </span>
          <span>
            {planning
              ? `${filteredPlans.length} allocations`
              : `${number(filteredTime.reduce((sum: number, r: Row) => sum + Number(r.period_hours || 0), 0))} actual hours`}{" "}
            ·{" "}
            {planning
              ? "Work / Availability / Leave / Holiday"
              : "Draft / Submitted / Approved / Processed"}
          </span>
        </>
      }
      detailActions={(event) =>
        !planning && (
          <div className="actions">
            {["Draft", "Rejected"].includes(event.kind) && event.editable && (
              <button
                disabled={busy}
                onClick={() =>
                  act("transition", { ...event.row, status: "Submitted" })
                }
              >
                {event.kind === "Rejected" ? "Resubmit" : "Submit"}
              </button>
            )}
            {event.kind === "Submitted" && canApprove(event.row) && (
              <>
                <button
                  disabled={busy}
                  onClick={() =>
                    act("transition", { ...event.row, status: "Approved" })
                  }
                >
                  Approve
                </button>
                <button
                  onClick={() =>
                    open(
                      "Return submitted entry",
                      "transition",
                      [{ key: "reason", label: "Reason" }],
                      { ...event.row, status: "Rejected" },
                    )
                  }
                >
                  Return
                </button>
              </>
            )}
          </div>
        )
      }
      railContent={
        path === "/timesheet" ? (
          <section>
            <h3>Suggestions ({data.suggestions.length})</h3>

            {data.suggestions.map((r: Row) => (
              <article className="suggestion" key={r.name}>
                <strong>{r.title}</strong>{" "}
                {new Date(r.plan_start).toLocaleString()}
                <button
                  disabled={busy}
                  onClick={() =>
                    act("decision", { ...r, decision: "Accepted" })
                  }
                >
                  Accept
                </button>
                <button
                  disabled={busy}
                  onClick={() => act("decision", { ...r, decision: "Ignored" })}
                >
                  Ignore
                </button>
              </article>
            ))}
            {!data.suggestions.length && (
              <Empty text="No undecided work suggestions in this period." />
            )}
          </section>
        ) : undefined
      }
      events={calendarEvents}
      palette={palette}
      days={range.days}
      view={view}
      mode={planning ? "Planning" : "Timesheet"}
      busy={busy}
      onCreate={(item, start, end) =>
        mutate(
          planning ? "save_plan" : "save_time",
          planning
            ? { ...item.row, plan_start: start, plan_end: end }
            : { ...item.row, check_in_time: start, check_out_time: end },
        )
      }
      onChange={(event, start, end) =>
        mutate(
          planning ? "save_plan" : "save_time",
          planning
            ? { ...event.row, plan_start: start, plan_end: end }
            : { ...event.row, check_in_time: start, check_out_time: end },
        )
      }
      onSelect={(start, end) =>
        planning
          ? planEditor({
              user: selectedEmployee,
              plan_start: start,
              plan_end: end,
            })
          : timeEditor({
              employee: selectedEmployee,
              check_in_time: start,
              check_out_time: end,
            })
      }
      onEdit={editCalendarEvent}
      onError={setError}
    />
  );
  return (
    <div className={`shell workz ${embedded ? "office-embedded" : ""}`}>
      {!embedded && <Sidebar expanded={expanded} onToggle={() => setExpanded(!expanded)} />}
      <main
        id="main"
        className={
          (planning || path === "/timesheet") && view !== "table"
            ? "calendar-page"
            : "list-page"
        }
      >
        {!embedded && <Toolbar title={title} loading={loading || busy} onRefresh={load} />}
        {scopeWarning && (
          <div role="alert" className="error">
            {scopeWarning}
            <button onClick={() => setScopeWarning("")}>
              Dismiss scope notice
            </button>
          </div>
        )}
        {error && (
          <div role="alert" className="error">
            {error} <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        {notice && (
          <p role="status" className="success">
            {notice}
          </p>
        )}

        <section className="toolbar" aria-label="Period and filters">
          {embedded && <IconButton icon="refresh" label="Refresh workspace" onClick={load} />}
          {(planning || path === "/timesheet") && calendarControls}
          {!settings &&
            !todos &&
            !(planning || path === "/timesheet") &&
            periodControls}
          {!settings && (
            <>
              <ScopeSelect
                label="Employee"
                value={employee}
                onChange={setEmployee}
                options={users.map((u) => ({
                  value: u.name,
                  label: u.full_name || u.name,
                }))}
                empty="All authorised employees"
              />
              <ScopeSelect
                label="Project"
                value={project}
                onChange={setProject}
                options={projects.map((p) => ({
                  value: p.name,
                  label: p.project_name,
                }))}
                empty="All authorised projects"
              />
            </>
          )}
          {!settings && (
            <button
              onClick={() => {
                setEmployee("");
                setProject("");
                setQuery("");
              }}
            >
              Clear ({Number(!!employee) + Number(!!project) + Number(!!query)})
            </button>
          )}
          {todos && (
            <>
              <label>
                Find project
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <label>
                Status
                <select
                  value={projectStatus}
                  onChange={(e) => setProjectStatus(e.target.value)}
                >
                  {["Active", "Archived", "All"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            </>
          )}
          <span
            className="timezone"
            title={`Calendar: ${tz}; storage: ${ctx.timezone}`}
            tabIndex={0}
          >
            {tz}
          </span>
        </section>
        <div
          className={`page-workspace ${reportPage ? "report-layout" : todos ? "project-layout" : settings ? "settings-layout" : path.endsWith("/approvals") ? "approval-layout" : ""}`}
        >
          {approvalPage && (
            <nav className="approval-queue" aria-label="Submission queue">
              <h2>Submitted ({scopedTime.length})</h2>
              {scopedTime.map((r: Row) => (
                <button
                  key={r.name}
                  aria-pressed={r.name === approvalSelection}
                  onClick={() => setSelection(r.name)}
                >
                  <strong>{userName(r.employee)}</strong>
                  <span>{projectName(r.project)}</span>
                  <span>
                    {new Date(r.check_in_time).toLocaleDateString()} ·{" "}
                    {number(r.period_hours)} h
                  </span>
                </button>
              ))}
              {!scopedTime.length && <Empty text="No pending submissions." />}
            </nav>
          )}
          {path === "/" && (
            <aside className="dashboard-actions">
              <Link to="/timesheet/approvals">
                Pending approvals ·{" "}
                {
                  data.entries.filter(
                    (r: Row) => r.status === "Submitted" && canApprove(r),
                  ).length
                }
              </Link>
              <Link to="/timesheet">
                Plan suggestions · {data.suggestions.length}
              </Link>
            </aside>
          )}
          {reportPage && (
            <>
              <section className="metrics">
                {Object.entries(data.report.totals).map(([key, value]) => (
                  <article key={key}>
                    <span>{key} hours</span>
                    <strong>{number(value)}</strong>
                  </article>
                ))}
              </section>
              <p className="help">
                {data.report.definition} Totals and drilldown share the selected
                employee/project filters.
              </p>
              <Table
                headers={[
                  "Employee",
                  "Planned h",
                  "Actual h",
                  "Submitted h",
                  "Approved h",
                ]}
              >
                {data.report.employees.map((r: Row) => (
                  <tr key={r.employee}>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setEmployee(r.employee)}
                        aria-label={`Show entries for ${userName(r.employee)}`}
                      >
                        {userName(r.employee)}
                      </button>
                    </td>
                    {["planned", "actual", "submitted", "approved"].map((k) => (
                      <td key={k}>{number(r[k])}</td>
                    ))}
                  </tr>
                ))}
              </Table>
              {!data.report.employees.length && <Empty />}
            </>
          )}
          {planning && (
            <>
              <TopActions>
                <button className="primary" onClick={() => planEditor()}>
                  <Icon name="add" /> Plan time
                </button>
              </TopActions>
              {view === "table" ? (
                <Table
                  headers={[
                    "Employee",
                    "Kind",
                    "Allocation",
                    "Start",
                    "End",
                    "Actions",
                  ]}
                >
                  {filteredPlans.map((r: Row) => (
                    <tr key={r.name}>
                      <td>{userName(r.user)}</td>
                      <td>{r.kind}</td>
                      <td>{r.title}</td>
                      <td>{new Date(r.plan_start).toLocaleString()}</td>
                      <td>{new Date(r.plan_end).toLocaleString()}</td>
                      <td>
                        <button onClick={() => planEditor(r)}>
                          Edit / resize
                        </button>
                        <button onClick={() => act("delete_plan", r)}>
                          Cancel
                        </button>
                      </td>
                    </tr>
                  ))}
                </Table>
              ) : (
                calendar
              )}
              {view === "table" && !filteredPlans.length && (
                <Empty text="No plans yet. Add work, availability, leave or holiday time." />
              )}
              {ctx.managed_projects.length > 0 && (
                <details className="panel contextual-panel">
                  <summary>Financial projections</summary>
                  <p>{data.finance.definition}</p>
                  {data.finance.missing.length > 0 && (
                    <p className="error">
                      Rate missing: totals are incomplete (
                      {data.finance.missing.length} rate/day gaps).
                    </p>
                  )}
                  <Table
                    headers={[
                      "Currency",
                      "Planned pay cost",
                      "Planned revenue",
                      "Gross margin",
                      "Margin %",
                    ]}
                  >
                    {Object.entries(data.finance.currencies).map(
                      ([currency, v]) => {
                        const r = v as Row;
                        return (
                          <tr key={currency}>
                            <td>{currency}</td>
                            <td>{number(r.cost)}</td>
                            <td>{number(r.revenue)}</td>
                            <td>
                              {r.margin === null
                                ? "Incomplete"
                                : number(r.margin)}
                            </td>
                            <td>
                              {r.margin_percent === null
                                ? "—"
                                : number(r.margin_percent)}
                            </td>
                          </tr>
                        );
                      },
                    )}
                  </Table>
                  <details>
                    <summary>Allocation projections by project</summary>
                    <h3>Project totals for selected period</h3>
                    <Table
                      headers={[
                        "Project",
                        "Currency",
                        "Cost",
                        "Revenue",
                        "Gross margin",
                      ]}
                    >
                      {data.finance.projects?.map((r: Row) => (
                        <tr key={r.project + r.currency}>
                          <td>
                            {projects.find((p) => p.name === r.project)
                              ?.project_name || r.project}
                          </td>
                          <td>{r.currency}</td>
                          <td>{number(r.cost)}</td>
                          <td>{number(r.revenue)}</td>
                          <td>
                            {r.margin === null
                              ? "Incomplete"
                              : number(r.margin)}
                          </td>
                        </tr>
                      ))}
                    </Table>
                    <Table
                      headers={[
                        "Project",
                        "Plan",
                        "Currency",
                        "Cost",
                        "Revenue",
                        "Completeness",
                      ]}
                    >
                      {data.finance.allocations?.flatMap((r: Row) =>
                        Object.entries(r.currencies).map(([c, v]) => (
                          <tr key={r.plan + c}>
                            <td>{projectName(r.project)}</td>
                            <td>{r.plan}</td>
                            <td>{c}</td>
                            <td>{number((v as Row).cost)}</td>
                            <td>{number((v as Row).revenue)}</td>
                            <td>
                              {r.missing.length ? "Rate missing" : "Complete"}
                            </td>
                          </tr>
                        )),
                      )}
                    </Table>
                  </details>
                </details>
              )}
              <details className="panel contextual-panel">
                <summary>HR leave requests</summary>
                <button
                  onClick={async () => {
                    try {
                      const l = await api("leave_options");
                      if (!l.available) {
                        setNotice(
                          l.message ||
                            "An HR Employee mapping is required before HR leave requests.",
                        );
                        return;
                      }
                      open(
                        "Request HR leave",
                        "leave_request",
                        [
                          {
                            key: "leave_type",
                            label: "Leave type",
                            options: l.types.map((value: string) => ({
                              value,
                              label: value,
                            })),
                          },
                          {
                            key: "from_date",
                            label: "From date",
                            type: "date",
                          },
                          {
                            key: "to_date",
                            label: "Through date",
                            type: "date",
                          },
                          {
                            key: "half_day",
                            label: "Half day",
                            type: "checkbox",
                          },
                          {
                            key: "half_day_date",
                            label: "Half-day date",
                            type: "date",
                            required: false,
                          },
                          { key: "description", label: "Reason" },
                        ],
                        { from_date: date, to_date: date },
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Request through existing leave policy
                </button>
              </details>
            </>
          )}
          {todos && (
            <>
              <TopActions>
                {ctx.admin && (
                  <button className="primary" onClick={() => projectEditor()}>
                    Create project
                  </button>
                )}
                {ctx.managed_projects.length > 0 && (
                  <>
                    <button onClick={() => activityEditor()}>
                      Create activity
                    </button>
                    <button
                      onClick={() =>
                        open(
                          "Assign employee to activity",
                          "assignment",
                          [
                            userField,
                            activityField,
                            {
                              key: "assigned",
                              label: "Assigned (uncheck to remove)",
                              type: "checkbox",
                            },
                          ],
                          { assigned: true },
                        )
                      }
                    >
                      Manage assignment
                    </button>
                  </>
                )}
              </TopActions>
              <section className="master-pane">
                <h2>Projects ({visibleProjects.length})</h2>
                {visibleProjects.map((r) => (
                  <button
                    className="project-choice"
                    key={r.name}
                    aria-pressed={selectedProject === r.name}
                    onClick={() => setProject(r.name)}
                  >
                    <strong>{r.project_name}</strong>
                    <span>
                      {r.status} ·{" "}
                      {activities.filter((a) => a.project === r.name).length}{" "}
                      activities
                    </span>
                  </button>
                ))}
                {!visibleProjects.length && (
                  <Empty text="No matching projects." />
                )}
              </section>
              <section className="detail-pane">
                <h2>
                  {selectedProject
                    ? projectName(selectedProject)
                    : "Select a project"}
                </h2>
                {projects
                  .filter((p) => p.name === selectedProject)
                  .map((r) => (
                    <div className="project-overview" key={r.name}>
                      <span>{r.status}</span>
                      <span>Lead: {userName(r.project_lead)}</span>
                      <span>Approver: {userName(r.timesheet_approver)}</span>
                      {managed(r.name) && (
                        <button onClick={() => projectEditor(r)}>
                          Edit / archive
                        </button>
                      )}
                    </div>
                  ))}
                <h3>Activities · Current canonical assignments</h3>
                <Table
                  headers={[
                    "Activity",
                    "Project",
                    "Status",
                    "Employees",
                    "Actions",
                  ]}
                >
                  {activities
                    .filter(
                      (r) =>
                        r.project === selectedProject &&
                        (!employee ||
                          ctx.assignments.some(
                            (a: Row) =>
                              a.reference_name === r.name &&
                              a.allocated_to === employee,
                          )),
                    )
                    .map((r) => (
                      <tr key={r.name}>
                        <td>{r.activity_name}</td>
                        <td>
                          {
                            projects.find((p) => p.name === r.project)
                              ?.project_name
                          }
                        </td>
                        <td>{r.status}</td>
                        <td>
                          {ctx.assignments
                            .filter((a: Row) => a.reference_name === r.name)
                            .map((a: Row) => userName(a.allocated_to))
                            .join(", ") || "Unassigned"}
                        </td>
                        <td>
                          {managed(r.project) && (
                            <button onClick={() => activityEditor(r)}>
                              Edit
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                </Table>
                <p className="help">
                  Current activity assignments only; closed/cancelled
                  assignments and project-level source history are not exposed
                  by this API. Removing an assignment preserves historic
                  timesheets.
                </p>
              </section>
            </>
          )}
          {!planning && !todos && !settings && (
            <>
              <TopActions>
                <button className="primary" onClick={() => timeEditor()}>
                  <Icon name="add" /> New entry
                </button>
              </TopActions>
              {path === "/timesheet" && <>{view !== "table" && calendar}</>}
              {(path !== "/timesheet" || view === "table") && (
                <section className="entry-detail">
                  <Table
                    headers={[
                      ...(new Set(filteredTime.map((r: Row) => r.employee))
                        .size > 1
                        ? ["Employee"]
                        : []),
                      "Project / activity",
                      "Start – end",
                      "Hours in period",
                      "Status",
                      "Actions",
                    ]}
                  >
                    {filteredTime.map((r: Row) => (
                      <tr key={r.name}>
                        {new Set(
                          filteredTime.map((entry: Row) => entry.employee),
                        ).size > 1 && <td>{userName(r.employee)}</td>}
                        <td>
                          {projectName(r.project)}
                          <br />
                          {activityName(r.activity)}
                        </td>
                        <td>
                          {new Date(r.check_in_time).toLocaleString()}
                          <small>
                            –{" "}
                            {r.check_out_time
                              ? new Date(r.check_out_time).toLocaleString()
                              : "In progress"}
                          </small>
                        </td>
                        <td>{number(r.period_hours)}</td>
                        <td>
                          {r.status}
                          {r.approved_by && (
                            <small>Last decision by {r.approved_by}</small>
                          )}
                          {r.approval_notes && (
                            <details>
                              <summary>Decision notes</summary>
                              <p>{r.approval_notes}</p>
                            </details>
                          )}
                          <button
                            onClick={async () => {
                              try {
                                const audit = await api("audit_history", {
                                  name: r.name,
                                });
                                setNotice(
                                  audit
                                    .map(
                                      (a: Row) =>
                                        `${a.recorded_at}: ${a.actor} · ${a.old_status || "new"} → ${a.new_status || a.action}`,
                                    )
                                    .join(" | ") ||
                                    "No application audit records. Imported source history remains in the migration archive.",
                                );
                              } catch (e) {
                                setError((e as Error).message);
                              }
                            }}
                          >
                            Audit
                          </button>
                        </td>
                        <td>
                          {["Draft", "Rejected"].includes(r.status) && (
                            <>
                              <button onClick={() => timeEditor(r)}>
                                Edit
                              </button>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  act("transition", {
                                    ...r,
                                    status: "Submitted",
                                  })
                                }
                              >
                                {r.status === "Rejected"
                                  ? "Resubmit"
                                  : "Submit"}
                              </button>
                              {r.status === "Draft" && (
                                <button
                                  disabled={busy}
                                  onClick={() => act("delete_time", r)}
                                >
                                  Delete
                                </button>
                              )}
                            </>
                          )}
                          {r.status === "Submitted" && canApprove(r) && (
                            <>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  act("transition", {
                                    ...r,
                                    status: "Approved",
                                  })
                                }
                              >
                                Approve
                              </button>
                              <button
                                onClick={() =>
                                  open(
                                    "Return submitted entry",
                                    "transition",
                                    [{ key: "reason", label: "Reason" }],
                                    { ...r, status: "Rejected" },
                                  )
                                }
                              >
                                Return
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </Table>
                  {!filteredTime.length && <Empty />}
                </section>
              )}
            </>
          )}
          {settings && (
            <SettingsPage
              {...{
                ctx,
                users,
                category,
                setCategory,
                open,
                setError,
                userField,
                projectField,
                today,
                date,
                tz,
                opts,
                history,
                setHistory,
                setEditor,
                act,
                userName,
                projectName,
              }}
            />
          )}
        </div>
        {editor && (
          <Editor
            key={editor.title}
            {...editor}
            onClose={() => setEditor(null)}
          />
        )}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  embedded ? <MemoryRouter initialEntries={[location.pathname.replace(/^\/workz/, '') || '/']}><App /></MemoryRouter> :
  <BrowserRouter basename={import.meta.env.DEV ? "/" : "/workz"}>
    <App />
  </BrowserRouter>,
);
