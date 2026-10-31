import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  mdiMagnify,
  mdiMenu,
  mdiRefresh,
  mdiPlus,
  mdiChevronLeft,
  mdiChevronRight,
  mdiClose,
  mdiViewDashboard,
  mdiFolderOutline,
  mdiCalendarMonth,
  mdiClockOutline,
  mdiAccountMultiple,
  mdiCheckDecagram,
  mdiChartBoxOutline,
  mdiCog,
  mdiDrag,
  mdiLock,
  mdiCalendarToday,
  mdiCalendarWeek,
  mdiTable,
} from "@mdi/js";
export const icons = {
  search: mdiMagnify,
  menu: mdiMenu,
  refresh: mdiRefresh,
  add: mdiPlus,
  previous: mdiChevronLeft,
  next: mdiChevronRight,
  close: mdiClose,
  dashboard: mdiViewDashboard,
  projects: mdiFolderOutline,
  planning: mdiCalendarMonth,
  timesheet: mdiClockOutline,
  assignments: mdiAccountMultiple,
  approvals: mdiCheckDecagram,
  reports: mdiChartBoxOutline,
  settings: mdiCog,
  grip: mdiDrag,
  lock: mdiLock,
  day: mdiCalendarToday,
  week: mdiCalendarWeek,
  month: mdiCalendarMonth,
  table: mdiTable,
};
export function Icon({ name }: { name: keyof typeof icons }) {
  return (
    <svg className="mdi" viewBox="0 0 24 24" aria-hidden="true">
      <path d={icons[name]} />
    </svg>
  );
}
export function IconButton({
  icon,
  label,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: keyof typeof icons;
  label: string;
}) {
  return (
    <button {...props} aria-label={label} title={label} className="icon-button">
      <Icon name={icon} />
      <span className="tooltip">{label}</span>
    </button>
  );
}
export function Toolbar({
  title,
  loading,
  onRefresh,
}: {
  title: string;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <header className="top-toolbar">
      <h1>{title}</h1>
      <div id="page-actions" />
      <span role="status">{loading ? "Loading…" : ""}</span>
      <IconButton
        icon="refresh"
        label="Refresh"
        onClick={onRefresh}
        disabled={loading}
      />
    </header>
  );
}
export function TopActions({ children }: { children: React.ReactNode }) {
  const target = document.getElementById("page-actions");
  return target ? (
    createPortal(children, target)
  ) : (
    <div className="actions">{children}</div>
  );
}
export function Drawer({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.querySelector<HTMLElement>("button")?.focus();
    return () => previous?.focus();
  }, []);
  return (
    <div
      className="overlay drawer-overlay"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        if (e.key === "Tab") {
          const nodes = Array.from(
            ref.current!.querySelectorAll<HTMLElement>(
              'button:not(:disabled),a,input,select,[tabindex="0"]',
            ),
          );
          const first = nodes[0],
            last = nodes[nodes.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      <section
        ref={ref}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <IconButton icon="close" label="Close details" onClick={onClose} />
        </header>
        {children}
      </section>
    </div>
  );
}
export function Table({
  headers,
  children,
}: {
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <div
      className="table-wrap"
      role="region"
      aria-label={headers.join(", ")}
      tabIndex={0}
    >
      <table>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {React.Children.map(children, (row) => {
            if (!React.isValidElement<{ children: React.ReactNode }>(row))
              return row;
            return React.cloneElement(
              row,
              {},
              React.Children.toArray(row.props.children).map((cell, i) =>
                React.isValidElement<{ className?: string }>(cell) &&
                /(?: h$|hours|cost|revenue|margin|rate$)/i.test(
                  headers[i] || "",
                )
                  ? React.cloneElement(cell, { className: "numeric" })
                  : cell,
              ),
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ViewSwitch({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  const values = ["day", "week", "month", "table"];
  return (
    <div
      role="group"
      aria-label={label}
      onKeyDown={(e) => {
        const index = values.indexOf(value);
        const next =
          e.key === "ArrowRight"
            ? (index + 1) % 4
            : e.key === "ArrowLeft"
              ? (index + 3) % 4
              : e.key === "Home"
                ? 0
                : e.key === "End"
                  ? 3
                  : -1;
        if (next >= 0) {
          e.preventDefault();
          onChange(values[next]);
          (e.currentTarget.children[next] as HTMLElement).focus();
        }
      }}
    >
      {values.map((v) => (
        <button
          key={v}
          tabIndex={value === v ? 0 : -1}
          aria-pressed={value === v}
          onClick={() => onChange(v)}
        >
          <Icon name={v as "day"} />
          {v}
        </button>
      ))}
    </div>
  );
}
export function ScopeSelect({
  label,
  value,
  onChange,
  options,
  empty,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  empty: string;
}) {
  const [query, setQuery] = React.useState("");
  const ref = useRef<HTMLDetailsElement>(null);
  return (
    <div className="scope-control">
      <label>
        {label}
        <select
          aria-label={label}
          value={value}
          title={options.find((o) => o.value === value)?.label || empty}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">{empty}</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <details
        ref={ref}
        className="scope-search"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            ref.current!.open = false;
            ref.current?.querySelector("summary")?.focus();
          }
        }}
      >
        <summary
          aria-label={`Search ${label.toLowerCase()}`}
          title={`Search ${label.toLowerCase()}`}
        >
          <Icon name="search" />
        </summary>
        <div>
          <label>
            Find {label.toLowerCase()}
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          {options
            .filter((o) => o.label.toLowerCase().includes(query.toLowerCase()))
            .map((o) => (
              <button
                key={o.value}
                onClick={() => {
                  onChange(o.value);
                  ref.current!.open = false;
                  ref.current?.querySelector("summary")?.focus();
                }}
              >
                {o.label}
              </button>
            ))}
          {!options.some((o) =>
            o.label.toLowerCase().includes(query.toLowerCase()),
          ) && <p>No matching {label.toLowerCase()}.</p>}
        </div>
      </details>
    </div>
  );
}
