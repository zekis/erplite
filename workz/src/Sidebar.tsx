// Adapted from zekis/afterz; MIT notice in docs/workz/AFTERZ-LICENSE.txt.
import React from "react";
import { NavLink } from "react-router-dom";
import { Icon, IconButton, icons } from "./ui";
const routes: [string, string, keyof typeof icons][] = [
  ["/", "Dashboard", "dashboard"],
  ["/projects", "Projects", "projects"],
  ["/planning", "Planning", "planning"],
  ["/timesheet", "View Timesheet", "timesheet"],
  ["/timesheet/assignments", "Manage Assignments", "assignments"],
  ["/timesheet/approvals", "Pending Approvals", "approvals"],
  ["/timesheet/reports", "Reports", "reports"],
  ["/settings", "Settings", "settings"],
];
export default function Sidebar({
  expanded,
  onToggle,
}: {
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <aside
      aria-label="Main navigation"
      className={`sidebar ${expanded ? "expanded" : "collapsed"}`}
    >
      <div className="brand">
        {expanded && (
          <>
            <img src="/assets/erplite/tm-logo.svg" alt="Tierney Morris" />
            <strong>Workz</strong>
          </>
        )}
        <IconButton
          icon="menu"
          label={expanded ? "Collapse sidebar" : "Expand sidebar"}
          onClick={onToggle}
        />
      </div>
      <nav>
        {routes.map(([path, label, icon]) => (
          <NavLink key={path} to={path} end title={label} aria-label={label}>
            <Icon name={icon} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <footer title={window.workzBoot?.user}>
        {expanded ? window.workzBoot?.user : <Icon name="assignments" />}
      </footer>
    </aside>
  );
}
