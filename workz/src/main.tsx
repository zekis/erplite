/// <reference types="vite/client" />
import React, { useState, useEffect, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import { api, Row } from "./api";
import {
  period,
  localDate,
  localInput,
  toInstant,
  offsetFor,
  shift,
  inDay,
  zoned,
} from "./calendar.mjs";
import "./style.css";

type Field = {
  key: string;
  label: string;
  type?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
};
const opts = (rows: Row[], key = "name", label = "name") =>
  rows.map((r) => ({ value: r[key], label: r[label] || r[key] }));
const today = localDate(new Date()),
  tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
const number = (value: any) =>
  Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
function Table({
  headers,
  children,
}: {
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
function Empty({ text = "No records in this period." }: { text?: string }) {
  return <p className="empty">{text}</p>;
}
function Editor({
  title,
  fields,
  initial,
  onSave,
  onClose,
}: {
  title: string;
  fields: Field[];
  initial: Row;
  onSave: (v: Row) => Promise<void>;
  onClose: () => void;
}) {
  const [values, setValues] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const dialog = document.querySelector(".dialog")!;
    const controls = () =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>("input,select,button"),
      ).filter((e) => !e.hasAttribute("disabled"));
    controls()[0]?.focus();
    function trap(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const list = controls(),
        first = list[0],
        last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="overlay"
      onKeyDown={(e) => {
        if (e.key === "Escape" && !busy) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-title"
        className="dialog"
      >
        <h2 id="edit-title">{title}</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await onSave(values);
              onClose();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {fields.map((f) => (
            <label key={f.key}>
              {f.label}
              {f.type === "checkbox" ? (
                <input
                  type="checkbox"
                  checked={!!values[f.key]}
                  onChange={(e) =>
                    setValues({ ...values, [f.key]: e.target.checked })
                  }
                />
              ) : f.options ? (
                <select
                  aria-label={f.label}
                  required={f.required !== false}
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      [f.key]: e.target.value,
                      ...(["plan_start", "check_in_time"].includes(f.key)
                        ? { start_offset: "" }
                        : ["plan_end", "check_out_time"].includes(f.key)
                          ? { end_offset: "" }
                          : {}),
                    })
                  }
                >
                  <option value="">Choose…</option>
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  autoFocus={fields[0] === f}
                  required={f.required !== false}
                  type={f.type || "text"}
                  step={f.type === "number" ? "0.000001" : undefined}
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      [f.key]: e.target.value,
                      ...(["plan_start", "check_in_time"].includes(f.key)
                        ? { start_offset: "" }
                        : ["plan_end", "check_out_time"].includes(f.key)
                          ? { end_offset: "" }
                          : {}),
                    })
                  }
                />
              )}
            </label>
          ))}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <footer>
            <button type="button" disabled={busy} onClick={onClose}>
              Cancel
            </button>
            <button className="primary" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
function App() {
  const path = useLocation().pathname;
  const [ctx, setCtx] = useState<Row | null>(null),
    [date, setDate] = useState(today),
    [view, setView] = useState("week"),
    [expanded, setExpanded] = useState(true);
  const [data, setData] = useState<Row>({
    plans: [],
    entries: [],
    suggestions: [],
    report: { employees: [], totals: {} },
    finance: { currencies: {}, missing: [] },
  });
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [editor, setEditor] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [employee, setEmployee] = useState(""),
    [project, setProject] = useState(""),
    [history, setHistory] = useState<Row[]>([]);
  const reportPage = path === "/" || path.endsWith("/reports"),
    planning = path === "/planning",
    todos = path === "/todos" || path.endsWith("/assignments"),
    settings = path === "/settings";
  const rawRange = period(
    date,
    reportPage ? "month" : view === "month" ? "month" : "week",
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
      if (!preferencesReady.current) {
        preferencesReady.current = true;
        const preference = JSON.parse(c.preferences || "{}").view;
        if (["table", "week", "month"].includes(preference))
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
      if (current === requestId.current) setError((e as Error).message);
    } finally {
      if (current === requestId.current) setLoading(false);
    }
  }, [range.start, range.end, employee, project]);
  const refresh = useRef(load);
  refresh.current = load;
  useEffect(() => {
    load();
  }, [load, path]);
  async function mutate(action: string, payload: Row) {
    setBusy(true);
    setNotice("");
    try {
      await api(action, payload);
      await refresh.current();
      setNotice("Saved. Totals refreshed.");
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
        user: ctx!.user,
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
      row.name ? "Edit draft" : "Book actual time",
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
        employee: ctx!.user,
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
      { status: "Open", ...row },
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
      { status: "Open", ...row },
    );
  }
  const filteredPlans = data.plans.filter(
    (r: Row) =>
      (!employee || r.user === employee) && (!project || r.project === project),
  );
  const filteredTime = data.entries.filter(
    (r: Row) =>
      (!employee || r.employee === employee) &&
      (!project || r.project === project) &&
      (path.endsWith("/approvals") ? r.status === "Submitted" : true),
  );
  const title =
    path === "/"
      ? "Dashboard"
      : planning
        ? "Planning"
        : todos
          ? "Todos & assignments"
          : settings
            ? "Settings & people"
            : path.endsWith("/reports")
              ? "Monthly reports"
              : path.endsWith("/approvals")
                ? "Pending approvals"
                : "Timesheet";
  function planCard(r: Row, day: string) {
    return (
      <article
        key={r.name}
        className={`plan ${r.kind?.toLowerCase()}`}
        draggable={!busy && (r.user === ctx!.user || managed(r.project))}
        onDragStart={(e) => {
          e.dataTransfer.setData(
            "application/workz",
            JSON.stringify({ name: r.name, day }),
          );
          e.dataTransfer.effectAllowed = "move";
        }}
      >
        <button className="text-button" onClick={() => planEditor(r)}>
          {r.title}
        </button>
        <small>
          {r.kind} · {r.user}
        </small>
        <small>
          {new Date(r.plan_start).toLocaleString()} —{" "}
          {new Date(r.plan_end).toLocaleString()}
        </small>
        {["Leave", "Holiday"].includes(r.kind) && (
          <small>Calendar intention · not HR approval</small>
        )}
        {(r.user === ctx!.user || managed(r.project)) && (
          <button
            className="text-button"
            disabled={busy}
            onClick={() => act("delete_plan", r)}
          >
            Cancel plan
          </button>
        )}
      </article>
    );
  }
  return (
    <div className="shell">
      <Sidebar expanded={expanded} onToggle={() => setExpanded(!expanded)} />
      <main id="main">
        <header>
          <div>
            <p className="eyebrow">ERPLite workspace</p>
            <h1>{title}</h1>
          </div>
          <button onClick={load} disabled={loading}>
            Refresh
          </button>
        </header>
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
        {loading && <p role="status">Refreshing persisted records…</p>}
        <section className="toolbar" aria-label="Period and filters">
          <label>
            {reportPage ? "Month" : "Date"}
            <input
              type={reportPage ? "month" : "date"}
              value={reportPage ? date.slice(0, 7) : date}
              onChange={(e) =>
                setDate(reportPage ? e.target.value + "-01" : e.target.value)
              }
            />
          </label>
          {!settings && (
            <>
              <label>
                Employee
                <select
                  value={employee}
                  onChange={(e) => setEmployee(e.target.value)}
                >
                  <option value="">All authorized employees</option>
                  {users.map((u) => (
                    <option key={u.name} value={u.name}>
                      {u.full_name || u.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Project
                <select
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                >
                  <option value="">All authorized projects</option>
                  {projects.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.project_name}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <small>
            Calendar: {tz} · Storage: {ctx.timezone}
          </small>
        </section>
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
                "Drilldown",
              ]}
            >
              {data.report.employees.map((r: Row) => (
                <tr key={r.employee}>
                  <td>{r.employee}</td>
                  {["planned", "actual", "submitted", "approved"].map((k) => (
                    <td key={k}>{number(r[k])}</td>
                  ))}
                  <td>
                    <button onClick={() => setEmployee(r.employee)}>
                      Show entries
                    </button>
                  </td>
                </tr>
              ))}
            </Table>
            {!data.report.employees.length && <Empty />}
          </>
        )}
        {planning && (
          <>
            <div className="actions">
              <button className="primary" onClick={() => planEditor()}>
                Plan time
              </button>
              <div role="group" aria-label="Planning view">
                {["table", "week", "month"].map((v) => (
                  <button
                    key={v}
                    aria-pressed={view === v}
                    onClick={() => {
                      setView(v);
                      act("preferences", { view: v });
                    }}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
            <p className="help">
              Drag an allocation to move it. Select its title to edit or resize
              with a keyboard or touch. Escape cancels a drag. Leave and
              holidays block allocations, but do not grant HR approval.
            </p>
            <div className="legend">
              {["Work", "Availability", "Leave", "Holiday"].map((k) => (
                <span key={k} className={`plan ${k.toLowerCase()}`}>
                  {k}
                </span>
              ))}
            </div>
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
                    <td>{r.user}</td>
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
              <div
                className={`calendar ${view}`}
                role="region"
                aria-label={`${view} calendar`}
              >
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                  (day) => (
                    <div className="weekday" key={day}>
                      {day}
                    </div>
                  ),
                )}
                {view === "month" &&
                  Array.from(
                    {
                      length:
                        (new Date(range.days[0] + "T12:00:00").getDay() + 6) %
                        7,
                    },
                    (_, i) => (
                      <div
                        className="day padding-day"
                        aria-hidden="true"
                        key={"pad" + i}
                      />
                    ),
                  )}
                {range.days.map((day: string) => (
                  <section
                    key={day}
                    className="day"
                    onDragOver={(e) => {
                      if (e.dataTransfer.types.includes("application/workz")) {
                        e.preventDefault();
                        e.currentTarget.classList.add("drop-target");
                      }
                    }}
                    onDragLeave={(e) =>
                      e.currentTarget.classList.remove("drop-target")
                    }
                    onDrop={async (e) => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("drop-target");
                      try {
                        const item = JSON.parse(
                            e.dataTransfer.getData("application/workz"),
                          ),
                          row = data.plans.find(
                            (r: Row) => r.name === item.name,
                          );
                        if (!row) throw Error("Invalid drop");
                        const [start, end] = shift(
                          row.plan_start,
                          row.plan_end,
                          item.day,
                          day,
                        );
                        await mutate("save_plan", {
                          ...row,
                          plan_start: start,
                          plan_end: end,
                        });
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    <button
                      className="day-label"
                      onClick={() => planEditor({}, day)}
                      aria-label={`Create plan ${day}`}
                    >
                      {day}
                    </button>
                    {filteredPlans
                      .filter((r: Row) => inDay(r.plan_start, r.plan_end, day))
                      .map((r: Row) => planCard(r, day))}
                  </section>
                ))}
              </div>
            )}
            {!filteredPlans.length && (
              <Empty text="No plans yet. Add work, availability, leave or holiday time." />
            )}
            {ctx.managed_projects.length > 0 && (
              <section className="panel">
                <h2>Financial projections</h2>
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
                          {r.margin === null ? "Incomplete" : number(r.margin)}
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
                          <td>{r.project}</td>
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
              </section>
            )}
            <section className="panel">
              <h2>HR leave requests</h2>
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
                        { key: "from_date", label: "From date", type: "date" },
                        { key: "to_date", label: "Through date", type: "date" },
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
            </section>
          </>
        )}
        {todos && (
          <>
            <div className="actions">
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
            </div>
            <h2>Projects</h2>
            <Table
              headers={[
                "Project",
                "Status",
                "Lead",
                "Timesheet approver",
                "Actions",
              ]}
            >
              {projects.map((r) => (
                <tr key={r.name}>
                  <td>{r.project_name}</td>
                  <td>{r.status}</td>
                  <td>{r.project_lead}</td>
                  <td>{r.timesheet_approver}</td>
                  <td>
                    {managed(r.name) && (
                      <button onClick={() => projectEditor(r)}>
                        Edit / archive
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
            {!projects.length && (
              <Empty text="No projects yet. An administrator can create a project and choose a lead and approver." />
            )}
            <h2>Activities & canonical assignments</h2>
            <Table
              headers={[
                "Activity",
                "Project",
                "Status",
                "Employees",
                "Actions",
              ]}
            >
              {activities.map((r) => (
                <tr key={r.name}>
                  <td>{r.activity_name}</td>
                  <td>
                    {projects.find((p) => p.name === r.project)?.project_name}
                  </td>
                  <td>{r.status}</td>
                  <td>
                    {ctx.assignments
                      .filter((a: Row) => a.reference_name === r.name)
                      .map((a: Row) => a.allocated_to)
                      .join(", ") || "Unassigned"}
                  </td>
                  <td>
                    {managed(r.project) && (
                      <button onClick={() => activityEditor(r)}>Edit</button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
            <p className="help">
              Removing assignments or archiving projects preserves historic
              timesheets. Booking requires an active assignment.
            </p>
          </>
        )}
        {!planning && !todos && !settings && (
          <>
            <div className="actions">
              <h2>Actual entries</h2>
              <button className="primary" onClick={() => timeEditor()}>
                Book actual time
              </button>
            </div>
            {path === "/timesheet" && (
              <section>
                <h2>Suggestions from your plan</h2>
                <p className="help">
                  Suggestions do not count as worked hours. Accept once to
                  create an editable draft. Moving or cancelling a plan never
                  changes accepted time or resets Ignore.
                </p>
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
                      onClick={() =>
                        act("decision", { ...r, decision: "Ignored" })
                      }
                    >
                      Ignore
                    </button>
                  </article>
                ))}
                {!data.suggestions.length && (
                  <Empty text="No undecided work suggestions in this period." />
                )}
              </section>
            )}
            <Table
              headers={[
                "Employee",
                "Project / activity",
                "Start",
                "Hours in period",
                "Status",
                "Actions",
              ]}
            >
              {filteredTime.map((r: Row) => (
                <tr key={r.name}>
                  <td>{r.employee}</td>
                  <td>
                    {r.project}
                    <br />
                    {r.activity}
                  </td>
                  <td>{new Date(r.check_in_time).toLocaleString()}</td>
                  <td>{number(r.period_hours)}</td>
                  <td>
                    {r.status}
                    {r.approved_by && <small>By {r.approved_by}</small>}
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
                    {r.status === "Draft" && (
                      <>
                        <button onClick={() => timeEditor(r)}>Edit</button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            act("transition", { ...r, status: "Submitted" })
                          }
                        >
                          Submit
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => act("delete_time", r)}
                        >
                          Delete
                        </button>
                      </>
                    )}
                    {r.status === "Submitted" && canApprove(r) && (
                      <>
                        <button
                          disabled={busy}
                          onClick={() =>
                            act("transition", { ...r, status: "Approved" })
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
                              { ...r, status: "Draft" },
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
          </>
        )}
        {settings && (
          <>
            <section className="panel">
              <h2>People & access</h2>
              {ctx.admin && (
                <button
                  className="primary"
                  onClick={() =>
                    open(
                      "Create employee account",
                      "save_user",
                      [
                        { key: "email", label: "Email", type: "email" },
                        { key: "full_name", label: "Full name" },
                        { key: "enabled", label: "Enabled", type: "checkbox" },
                        {
                          key: "invite",
                          label: "Send Frappe welcome invitation",
                          type: "checkbox",
                        },
                      ],
                      {
                        enabled: true,
                        invite: false,
                        roles: ["Projects User"],
                      },
                    )
                  }
                >
                  Create employee
                </button>
              )}
              <Table headers={["Employee", "Enabled", "Actions"]}>
                {users.map((r) => (
                  <tr key={r.name}>
                    <td>
                      {r.full_name || r.name}
                      <small>{r.name}</small>
                    </td>
                    <td>{r.enabled ? "Yes" : "No"}</td>
                    <td>
                      {ctx.admin && (
                        <button
                          onClick={async () => {
                            try {
                              const u = await api("user_detail", {
                                name: r.name,
                              });
                              open(
                                "Employee access",
                                "save_user",
                                [
                                  { key: "full_name", label: "Full name" },
                                  {
                                    key: "enabled",
                                    label: "Enabled",
                                    type: "checkbox",
                                  },
                                  {
                                    key: "role",
                                    label: "Project role",
                                    options: [
                                      {
                                        value: "Projects User",
                                        label: "Projects User",
                                      },
                                      {
                                        value: "Projects Manager",
                                        label: "Projects Manager",
                                      },
                                    ],
                                  },
                                ],
                                {
                                  ...u,
                                  role: u.roles.includes("Projects Manager")
                                    ? "Projects Manager"
                                    : "Projects User",
                                },
                                (v) => ({ ...v, roles: [v.role] }),
                              );
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Edit access
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
              <p className="help">
                Project leads and timesheet approvers are set on the project in
                Todos. Access roles never grant global financial or approval
                scope.
              </p>
            </section>
            {(ctx.admin || ctx.managed_projects.length > 0) && (
              <section className="panel">
                <h2>Rate history</h2>
                {ctx.admin && (
                  <button
                    onClick={() =>
                      open("Add currency", "save_currency", [
                        { key: "code", label: "Three-letter code" },
                        { key: "symbol", label: "Symbol" },
                      ])
                    }
                  >
                    Add currency
                  </button>
                )}
                <p>
                  Versions apply from their effective date in {ctx.timezone}.
                  Existing versions are immutable. Zero is an intentional rate;
                  blank means missing. Pay rates are administrator-managed.
                </p>
                <button
                  onClick={() =>
                    open(
                      "Add effective rate",
                      "save_rate",
                      [
                        userField,
                        {
                          key: "kind",
                          label: "Rate kind",
                          options: (ctx.admin ? ["Pay", "Sell"] : ["Sell"]).map(
                            (value) => ({ value, label: value }),
                          ),
                        },
                        { ...projectField, required: false },
                        {
                          key: "effective_from",
                          label: "Effective from",
                          type: "date",
                        },
                        { key: "amount", label: "Hourly rate", type: "number" },
                        {
                          key: "currency",
                          label: "Currency",
                          options: opts(ctx.currencies),
                        },
                      ],
                      {
                        kind: ctx.admin ? "Pay" : "Sell",
                        effective_from: today,
                      },
                    )
                  }
                >
                  Add rate version
                </button>
                <button
                  onClick={() =>
                    setEditor({
                      title: "View rate history",
                      fields: [
                        userField,
                        { ...projectField, required: !ctx.admin },
                      ],
                      initial: {},
                      onSave: async (v: Row) =>
                        setHistory(await api("rate_history", v)),
                    })
                  }
                >
                  View employee rates
                </button>
                <Table
                  headers={[
                    "Employee",
                    "Kind",
                    "Project",
                    "Effective from",
                    "Hourly rate",
                    "Currency",
                  ]}
                >
                  {history.map((r) => (
                    <tr key={r.name}>
                      <td>{r.employee}</td>
                      <td>{r.kind}</td>
                      <td>{r.project || "All assigned projects"}</td>
                      <td>{r.effective_from}</td>
                      <td>{r.amount}</td>
                      <td>{r.currency}</td>
                    </tr>
                  ))}
                </Table>
              </section>
            )}
            <section className="panel">
              <h2>Calendar preferences</h2>
              <label>
                Default planning view
                <select
                  defaultValue={JSON.parse(ctx.preferences).view || "week"}
                  onChange={(e) => act("preferences", { view: e.target.value })}
                >
                  {["table", "week", "month"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              <p>
                Dates and times are displayed in {tz}. The site stores time in{" "}
                {ctx.timezone}.
              </p>
            </section>
          </>
        )}
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
  <BrowserRouter basename={import.meta.env.DEV ? "/" : "/workz"}>
    <App />
  </BrowserRouter>,
);
