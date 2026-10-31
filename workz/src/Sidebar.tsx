// Adapted from zekis/afterz d02c7b2; MIT notice in docs/workz/AFTERZ-LICENSE.txt.
import React, { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  MdDashboard,
  MdChecklist,
  MdCalendarToday,
  MdSchedule,
  MdSettings,
  MdChevronLeft,
  MdChevronRight,
  MdAccountCircle,
  MdExpandMore,
  MdExpandLess,
  MdAssignment,
  MdApproval,
} from "react-icons/md";

interface SidebarProps {
  expanded: boolean;
  onToggle: () => void;
}

interface NavItem {
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  badge?: number;
  subItems?: SubNavItem[];
}

interface SubNavItem {
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const Sidebar: React.FC<SidebarProps> = ({ expanded, onToggle }) => {
  const currentUser = {
    name: window.workzBoot?.user,
    full_name: "",
    email: window.workzBoot?.user,
  };
  const location = useLocation();
  const [timesheetExpanded, setTimesheetExpanded] = useState(true);

  const navItems: NavItem[] = [
    { path: "/", icon: MdDashboard, label: "Dashboard" },
    { path: "/projects", icon: MdChecklist, label: "Projects" },
    { path: "/planning", icon: MdCalendarToday, label: "Planning" },
    {
      path: "/timesheet",
      icon: MdSchedule,
      label: "Timesheet",
      subItems: [
        {
          path: "/timesheet/assignments",
          icon: MdAssignment,
          label: "Manage Assignments",
        },
        {
          path: "/timesheet/approvals",
          icon: MdApproval,
          label: "Pending Approvals",
        },
        { path: "/timesheet/reports", icon: MdDashboard, label: "Reports" },
      ],
    },
    { path: "/settings", icon: MdSettings, label: "Settings" },
  ];

  return (
    <aside
      aria-label="Main navigation"
      className={`sidebar ${expanded ? "expanded" : "collapsed"}`}
    >
      {/* Header with toggle */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between">
        {expanded && (
          <div className="flex items-center space-x-2">
            <img
              src="/assets/erplite/tm-logo.svg"
              alt="Tierney Morris"
              className="h-7 w-auto"
            />
            <span className="font-semibold text-slate-900">Workz</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-1 hover:bg-slate-100 rounded-md transition-colors"
          title={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {expanded ? (
            <MdChevronLeft className="w-5 h-5 text-slate-600" />
          ) : (
            <MdChevronRight className="w-5 h-5 text-slate-600" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.path}>
              {item.subItems ? (
                // Timesheet with submenu
                <div>
                  <button
                    type="button"
                    aria-label="Timesheet navigation"
                    aria-expanded={timesheetExpanded}
                    className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors cursor-pointer ${
                      location.pathname.startsWith("/timesheet")
                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                    onClick={() => {
                      if (item.path === "/timesheet") {
                        setTimesheetExpanded(!timesheetExpanded);
                      }
                    }}
                  >
                    <item.icon className="w-5 h-5 flex-shrink-0" />
                    {expanded && (
                      <>
                        <span className="font-medium flex-1">{item.label}</span>
                        {timesheetExpanded ? (
                          <MdExpandLess className="w-4 h-4" />
                        ) : (
                          <MdExpandMore className="w-4 h-4" />
                        )}
                      </>
                    )}
                  </button>

                  {/* Submenu */}
                  {expanded && timesheetExpanded && (
                    <ul className="ml-8 mt-1 space-y-1">
                      <li>
                        <NavLink
                          to="/timesheet"
                          className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors text-sm ${
                            location.pathname === "/timesheet"
                              ? "bg-blue-50 text-blue-700"
                              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                          }`}
                        >
                          <MdSchedule className="w-4 h-4 flex-shrink-0" />
                          <span>View Timesheet</span>
                        </NavLink>
                      </li>
                      {item.subItems.map((subItem) => (
                        <li key={subItem.path}>
                          <NavLink
                            to={subItem.path}
                            className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors text-sm ${
                              location.pathname === subItem.path
                                ? "bg-blue-50 text-blue-700"
                                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                            }`}
                          >
                            <subItem.icon className="w-4 h-4 flex-shrink-0" />
                            <span>{subItem.label}</span>
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                // Regular nav item
                <NavLink
                  to={item.path}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors group ${
                    location.pathname === item.path
                      ? "bg-blue-50 text-blue-700 border border-blue-200"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                  title={!expanded ? item.label : undefined}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" />
                  {expanded && (
                    <>
                      <span className="font-medium">{item.label}</span>
                      {item.badge && (
                        <span className="ml-auto bg-red-500 text-white text-xs rounded-full px-2 py-0.5 min-w-[20px] text-center">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              )}
            </li>
          ))}
        </ul>
      </nav>

      {/* User section at bottom */}
      <div className="p-4 border-t border-slate-200">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-slate-200 rounded-full flex items-center justify-center flex-shrink-0">
            <MdAccountCircle className="w-6 h-6 text-slate-600" />
          </div>
          {expanded && currentUser && (
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-900 truncate">
                {currentUser.full_name || currentUser.name}
              </div>
              <div className="text-xs text-slate-500 truncate">
                {currentUser.email}
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
