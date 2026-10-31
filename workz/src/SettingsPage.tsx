import React from "react";
import { api, Row } from "./api";
import { Table } from "./ui";
export default function SettingsPage({
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
}: any) {
  return (
    <>
      <nav className="category-nav" aria-label="Settings categories">
        {[
          "People & access",
          ...(ctx.admin || ctx.managed_projects.length ? ["Rate history"] : []),
          "Calendar preferences",
        ].map((c) => (
          <button
            key={c}
            aria-pressed={category === c}
            onClick={() => setCategory(c)}
          >
            {c}
          </button>
        ))}
      </nav>
      <div>
        <section className="panel" hidden={category !== "People & access"}>
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
            {users.map((r: Row) => (
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
                            (v: Row) => ({ ...v, roles: [v.role] }),
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
            Projects. Access roles never grant global financial or approval
            scope.
          </p>
        </section>
        {(ctx.admin || ctx.managed_projects.length > 0) && (
          <section className="panel" hidden={category !== "Rate history"}>
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
              {history.map((r: Row) => (
                <tr key={r.name}>
                  <td>{userName(r.employee)}</td>
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
        <section className="panel" hidden={category !== "Calendar preferences"}>
          <h2>Calendar preferences</h2>
          <label>
            Default planning view
            <select
              defaultValue={JSON.parse(ctx.preferences).view || "week"}
              onChange={(e) => act("preferences", { view: e.target.value })}
            >
              {["day", "week", "month", "table"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <p>
            Dates and times are displayed in {tz}. The site stores time in{" "}
            {ctx.timezone}.
          </p>
        </section>
      </div>
    </>
  );
}
