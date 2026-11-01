import { test, expect } from "@playwright/test";
const routes = {
  dashboard: "",
  projects: "/projects",
  planning: "/planning",
  timesheet: "/timesheet",
  assignments: "/timesheet/assignments",
  approvals: "/timesheet/approvals",
  reports: "/timesheet/reports",
  settings: "/settings",
};
const viewports = [
  [1920, 1080],
  [1440, 900],
  [1366, 768],
  [1024, 768],
  [768, 1024],
  [390, 844],
];
const person = {
  name: "fictional.person",
  full_name: "Alex Example",
  enabled: 1,
};
const project = {
  name: "project-hash-01",
  project_name: "Fictional coastal infrastructure and accessibility programme",
  status: "Open",
  project_lead: person.name,
  timesheet_approver: "reviewer",
};
const activity = {
  name: "activity-hash-01",
  activity_name:
    "Review design documentation and coordinate accessible delivery",
  project: project.name,
  status: "Open",
};
const entries = Array.from({ length: 18 }, (_, i) => ({
  name: "entry-" + i,
  employee: person.name,
  project: project.name,
  activity: activity.name,
  check_in_time: `2030-09-02T${String(6 + Math.floor(i / 2)).padStart(2, "0")}:00:00Z`,
  check_out_time: `2030-09-02T${String(7 + Math.floor(i / 2)).padStart(2, "0")}:00:00Z`,
  status: ["Draft", "Rejected", "Submitted", "Approved", "Processed"][i % 5],
  period_hours: 1,
  description: "Fictional fixture only",
}));
async function fixture(page, role = "admin") {
  await page.clock.install({ time: new Date("2030-09-02T12:00:00Z") });
  await page.route("**/api/method/erplite.workz.api.run", async (route) => {
    const { action } = route.request().postDataJSON();
    const admin = role === "admin";
    const context = {
      user: person.name,
      admin,
      timezone: "Australia/Perth",
      preferences: "{}",
      projects: [project],
      activities: [activity],
      users: [person, { name: "reviewer", full_name: "Sam Reviewer" }],
      assignments: [
        { reference_name: activity.name, allocated_to: person.name },
      ],
      managed_projects: admin || role === "lead" ? [project.name] : [],
      approval_projects: admin || role === "approver" ? [project.name] : [],
      currencies: [{ name: "AUD" }],
    };
    const data = {
      context,
      times: entries,
      plans: entries.map((e) => ({
        ...e,
        user: e.employee,
        plan_start: e.check_in_time,
        plan_end: e.check_out_time,
        title: activity.activity_name,
        kind: "Work",
      })),
      suggestions: [],
      report: {
        totals: { actual: 18, submitted: 4, approved: 7, planned: 18 },
        employees: [
          {
            employee: person.name,
            actual: 18,
            submitted: 4,
            approved: 7,
            planned: 18,
          },
        ],
        definition: "Fictional totals; plans are separate from actual time.",
      },
      financials: {
        currencies: {},
        missing: [],
        projects: [],
        allocations: [],
        definition: "No configured rates.",
      },
    };
    if (!(action in data))
      throw Error("Layout test must not mutate: " + action);
    await route.fulfill({ json: { message: data[action] } });
  });
}
async function geometry(page) {
  return page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
    clientWidth: document.documentElement.clientWidth,
    clientHeight: document.documentElement.clientHeight,
    calendar: document
      .querySelector(".calendar-workspace")
      ?.getBoundingClientRect()
      .toJSON(),
  }));
}
for (const [width, height] of viewports)
  test(`all routes at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await fixture(page);
    for (const [name, path] of Object.entries(routes)) {
      await page.goto("/workz" + path);
      await expect(page.locator(".top-toolbar")).toBeVisible();
      await expect(page.locator(".page-workspace")).toBeVisible();
      const g = await geometry(page);
      expect(g.width, name).toBeLessThanOrEqual(g.clientWidth + 2);
      if (width >= 1280)
        expect(g.height, name).toBeLessThanOrEqual(g.clientHeight + 2);
      if (
        width === 1366 ||
        (["planning", "timesheet", "settings"].includes(name) &&
          [390, 768].includes(width))
      )
        await page.screenshot({
          path: `../docs/workz/ui-evidence/after-${name}-${width}.png`,
          fullPage: true,
        });
    }
  });
for (const [width, height] of [
  [1366, 768],
  [1440, 900],
])
  for (const route of ["planning", "timesheet"])
    test(`${route} calendar geometry and overflow ${width}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height });
      await fixture(page);
      await page.goto("/workz/" + route);
      for (const mode of ["day", "week", "month"]) {
        await page.getByRole("button", { name: mode, exact: true }).click();
        await expect(
          page.getByRole("region", { name: mode + " calendar", exact: true }),
        ).toBeVisible();
        const g = await geometry(page);
        expect(g.width).toBeLessThanOrEqual(g.clientWidth + 2);
        expect(g.height).toBeLessThanOrEqual(g.clientHeight + 2);
        expect(g.calendar.y).toBeLessThanOrEqual(120);
        expect(g.calendar.bottom).toBeLessThanOrEqual(height);
        expect(
          await page.locator(".page-workspace > .entry-detail").count(),
        ).toBe(0);
        await page.screenshot({
          path: `../docs/workz/ui-evidence/after-${route}-${mode}-${width}.png`,
        });
        if (mode === "month") {
          expect(await page.locator(".weekday").count()).toBe(7);
          const more = page.getByRole("button", { name: /\+\d+ more/ }).first();
          await expect(more).toBeVisible();
          await more.click();
          await expect(page.getByRole("dialog")).toBeVisible();
          expect(await page.locator(".agenda-item").count()).toBe(18);
          await page.keyboard.press("Escape");
          await expect(page.getByRole("dialog")).toHaveCount(0);
        }
      }
      await page.getByRole("button", { name: "week", exact: true }).click();
      await page.getByRole("button", { name: /^Activities/ }).click();
      await page.getByRole("button", { name: "Collapse sidebar" }).click();
      await page.setViewportSize({ width: 1024, height: 768 });
      expect((await geometry(page)).width).toBeLessThanOrEqual(1026);
      await page.locator(".event-title").first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.keyboard.press("Escape");
      await page.reload();
      await expect(
        page.getByRole("button", { name: "Expand sidebar" }),
      ).toBeVisible();
    });
for (const role of ["employee", "lead", "approver", "admin"])
  test(`settings capabilities for ${role}`, async ({ page }) => {
    await fixture(page, role);
    await page.goto("/workz/settings");
    await expect(
      page.getByRole("button", { name: "Create employee", exact: true }),
    ).toHaveCount(role === "admin" ? 1 : 0);
    await expect(
      page.getByRole("button", { name: "Rate history", exact: true }),
    ).toHaveCount(["admin", "lead"].includes(role) ? 1 : 0);
  });

test("Processed details lock, keyboard trap and unavailable saved scope", async ({
  page,
}) => {
  await fixture(page);
  await page.goto("/workz/timesheet");
  await page.getByRole("button", { name: "day", exact: true }).click();
  await page.locator(".time-entry.processed .event-title").first().click();
  await expect(page.getByRole("dialog")).toContainText("Locked history");
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Edit", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Tab");
  expect(
    await page
      .getByRole("dialog")
      .evaluate((e) => e.contains(document.activeElement)),
  ).toBeTruthy();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.evaluate(() =>
    localStorage.setItem(
      "workz-ui:Administrator",
      JSON.stringify({ employee: "removed-user", project: "removed-project" }),
    ),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Saved scope is no longer available",
  );
});
test("small CSS viewport equivalent to 200 percent laptop zoom keeps actions reachable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 683, height: 384 });
  await fixture(page);
  await page.goto("/workz/timesheet");
  expect((await geometry(page)).width).toBeLessThanOrEqual(685);
  await page.getByRole("button", { name: "New entry", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
});

test("four, five and six week months remain bounded", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await fixture(page);
  await page.goto("/workz/planning");
  await page.getByRole("button", { name: "month", exact: true }).click();
  for (const [date, rows] of [
    ["2027-02-01", 4],
    ["2030-04-01", 5],
    ["2030-09-01", 6],
  ]) {
    await page.locator(".period-picker summary").click();
    await page.getByLabel("Date", { exact: true }).fill(date);
    await page.locator(".period-picker summary").click();
    await expect
      .poll(() =>
        page
          .locator(".month-time-grid")
          .evaluate(
            (e) => getComputedStyle(e).gridTemplateRows.split(" ").length,
          ),
      )
      .toBe(rows + 1);
    expect((await geometry(page)).height).toBeLessThanOrEqual(770);
  }
});
test("out-of-hours reveal and stale save leave persisted interval intact", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await fixture(page);
  await page.route("**/api/method/erplite.workz.api.run", async (route) => {
    const { action } = route.request().postDataJSON();
    if (action === "plans")
      return route.fulfill({
        json: {
          message: [
            {
              name: "early",
              user: person.name,
              project: project.name,
              title: "Early fictional availability",
              kind: "Availability",
              plan_start: "2030-09-02T04:00:00Z",
              plan_end: "2030-09-02T05:00:00Z",
            },
          ],
        },
      });
    if (action === "save_plan")
      return route.fulfill({
        status: 409,
        json: {
          message: "Record changed. Refresh and retry.",
          exc: "Conflict",
        },
      });
    return route.fallback();
  });
  await page.goto("/workz/planning");
  await page.getByRole("button", { name: /outside working hours/ }).click();
  await expect(
    page.getByRole("checkbox", { name: "Full day (00:00–24:00)", exact: true }),
  ).toBeChecked();
  const early = page
    .locator(".time-entry")
    .filter({ hasText: "Early fictional availability" });
  await early
    .getByRole("button", { name: "Resize end of Early fictional availability" })
    .press("ArrowDown");
  await expect(page.getByRole("alert")).toContainText("Record changed");
  await expect(early).toContainText("04:00–05:00");
  expect((await geometry(page)).height).toBeLessThanOrEqual(770);
});

test("searchable employee scope prefills the named entry form and view switch has arrow keys", async ({
  page,
}) => {
  await fixture(page);
  await page.goto("/workz/timesheet");
  await page.getByLabel("Search employee", { exact: true }).click();
  await page.getByLabel("Find employee", { exact: true }).fill("Sam");
  await page.getByRole("button", { name: "Sam Reviewer", exact: true }).click();
  await page.getByRole("button", { name: "New entry", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Book actual time · Sam Reviewer",
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "week", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("button", { name: "month", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByLabel("Employee", { exact: true })).toHaveValue(
    "reviewer",
  );
  await expect(
    page.getByRole("button", { name: "month", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});
