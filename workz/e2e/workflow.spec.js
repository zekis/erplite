import { test, expect } from "@playwright/test";
test("fresh setup, plan, ghost, accept, submit, scoped approve and reconciliation without Desk", async ({
  page,
  context,
}) => {
  await page.clock.install({ time: new Date("2030-01-07T12:00:00Z") });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  async function role(user) {
    await context.addCookies([
      { name: "synthetic_user", value: user, url: "http://127.0.0.1:8765" },
    ]);
    await page.goto("/workz");
    await expect(
      page.getByRole("heading", { name: "Dashboard", exact: true }),
    ).toBeVisible();
  }
  async function save() {
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByText("Saved. Totals refreshed.")).toBeVisible();
  }
  await role("Administrator");
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await page
    .getByLabel("Project name", { exact: true })
    .fill("Synthetic project");
  await page.getByLabel("Project lead", { exact: true }).selectOption("lead");
  await page
    .getByLabel("Timesheet approver", { exact: true })
    .selectOption("approver");
  await save();
  await page
    .getByRole("button", { name: "Create activity", exact: true })
    .click();
  await page
    .getByLabel("Project", { exact: true })
    .last()
    .selectOption({ label: "Synthetic project" });
  await page.getByLabel("Activity name").fill("Synthetic activity");
  await save();
  await page
    .getByRole("button", { name: "Manage assignment", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Employee", { exact: true })
    .selectOption("alice");
  await page
    .getByLabel("Activity (must belong to chosen project)")
    .selectOption({ label: "Synthetic activity" });
  await save();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page
    .getByRole("button", { name: "Create employee", exact: true })
    .click();
  await page
    .getByLabel("Email", { exact: true })
    .fill("newperson@example.invalid");
  await page
    .getByLabel("Full name", { exact: true })
    .fill("New synthetic person");
  await save();
  await expect(
    page.getByText("newperson@example.invalid", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Rate history", exact: true }).click();
  await page.getByRole("button", { name: "Add currency", exact: true }).click();
  await page.getByLabel("Three-letter code").fill("AUD");
  await page.getByLabel("Symbol", { exact: true }).fill("$");
  await save();
  for (const [kind, amount] of [
    ["Pay", "40"],
    ["Sell", "100"],
  ]) {
    await page
      .getByRole("button", { name: "Add rate version", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByLabel("Employee", { exact: true })
      .selectOption("alice");
    await page.getByLabel("Rate kind", { exact: true }).selectOption(kind);
    if (kind === "Sell")
      await page
        .getByRole("dialog")
        .getByLabel("Project", { exact: true })
        .selectOption({ label: "Synthetic project" });
    await page.getByLabel("Effective from", { exact: true }).fill("2030-01-01");
    await page.getByLabel("Hourly rate", { exact: true }).fill(amount);
    await page.getByLabel("Currency", { exact: true }).selectOption("AUD");
    await save();
  }
  await role("lead");
  await page.getByRole("link", { name: "Planning", exact: true }).click();
  await page.getByRole("button", { name: "Plan time", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Synthetic allocation");
  await page
    .getByRole("dialog")
    .getByLabel("Employee", { exact: true })
    .selectOption("alice");
  await page
    .getByRole("dialog")
    .getByLabel("Project", { exact: true })
    .selectOption({ label: "Synthetic project" });
  await page
    .getByLabel("Activity (must belong to chosen project)")
    .selectOption({ label: "Synthetic activity" });
  await save();
  await page.getByRole("button", { name: "table", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Synthetic allocation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "month", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "month calendar" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "week", exact: true }).click();
  await page.screenshot({
    path: "artifacts/workz-planning.png",
    fullPage: true,
  });
  await role("alice");
  await page.getByRole("link", { name: "View Timesheet", exact: true }).click();
  await expect(
    page.getByText("Synthetic allocation", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Accept", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "table", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Submit", exact: true }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Submitted", exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve", exact: true }),
  ).toHaveCount(0);
  await role("stranger");
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "alice", exact: true }),
  ).toHaveCount(0);
  await role("approver");
  await page
    .getByRole("link", { name: "Pending Approvals", exact: true })
    .click();
  await page.getByRole("button", { name: "Return", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Reason", { exact: true })
    .fill("Please correct description");
  await save();
  await role("alice");
  await page.getByRole("link", { name: "View Timesheet", exact: true }).click();
  await page.getByText("Decision notes", { exact: true }).click();
  await expect(
    page.getByText("Please correct description", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Description", { exact: true })
    .fill("Corrected after rejection");
  await save();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Resubmit", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByLabel("Description", { exact: true }),
  ).toHaveValue("Corrected after rejection");
  page.once("dialog", (dialog) => dialog.accept());
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Resubmit", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Edit", exact: true }),
  ).toHaveCount(0);
  await role("approver");
  await page
    .getByRole("link", { name: "Pending Approvals", exact: true })
    .click();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Approve", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(
    page.getByRole("cell", {
      name: "Approved Last decision by approver Audit",
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "artifacts/workz-reports.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
  expect(page.url()).not.toContain("/app/");
});

test("calendar drag, rejected overlap rollback, keyboard resize, ignored suggestion and mobile navigation", async ({
  page,
  context,
}) => {
  await page.clock.install({ time: new Date("2030-01-14T12:00:00Z") });
  await context.addCookies([
    { name: "synthetic_user", value: "alice", url: "http://127.0.0.1:8765" },
  ]);
  await page.goto("/workz/planning");
  async function add(title, day) {
    await page.getByRole("button", { name: "Plan time", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Title", { exact: true }).fill(title);
    await dialog
      .getByLabel("Project", { exact: true })
      .selectOption({ label: "Synthetic project" });
    await dialog
      .getByLabel("Activity (must belong to chosen project)")
      .selectOption({ label: "Synthetic activity" });
    await dialog.getByLabel(/^Start/).fill(day + "T09:00");
    await dialog.getByLabel(/^End, exclusive/).fill(day + "T11:00");
    await dialog.getByRole("button", { name: "Save", exact: true }).click();
    await expect(dialog).toBeHidden();
  }
  await add("Move me", "2030-01-14");
  await add("Conflict target", "2030-01-16");
  const moved = page
    .locator("article.time-entry")
    .filter({ hasText: "Move me" });
  const tuesday = page.locator('[data-day="2030-01-15"]');
  async function drag(source, target) {
    await source.scrollIntoViewIfNeeded();
    await target.scrollIntoViewIfNeeded();
    const a = await source.boundingBox(),
      b = await target.boundingBox();
    await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
    await page.mouse.down();
    await page.mouse.move(a.x + a.width / 2 + 8, a.y + a.height / 2, {
      steps: 3,
    });
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 20 });
    await page.mouse.up();
  }
  await drag(
    moved.getByRole("button", { name: "Move Move me", exact: true }),
    page.locator('[data-slot="2030-01-15 09:00"]'),
  );
  await expect(
    tuesday.locator("article.time-entry").filter({ hasText: "Move me" }),
  ).toHaveCount(1);
  await drag(
    moved.getByRole("button", { name: "Move Move me", exact: true }),
    page.locator('[data-slot="2030-01-16 09:00"]'),
  );
  await expect(page.getByRole("alert")).toContainText("Conflicts");
  await expect(
    tuesday.locator("article.time-entry").filter({ hasText: "Move me" }),
  ).toHaveCount(1);
  await moved
    .getByRole("button", { name: "Resize end of Move me", exact: true })
    .press("ArrowDown");
  await expect(moved).toContainText("11:15");
  await page.getByRole("link", { name: "View Timesheet", exact: true }).click();
  const suggestion = page.locator(".suggestion").filter({ hasText: "Move me" });
  await suggestion.getByRole("button", { name: "Ignore", exact: true }).click();
  await expect(suggestion).toHaveCount(0);
  await page.reload();
  await expect(
    page.locator(".suggestion").filter({ hasText: "Move me" }),
  ).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Settings & people", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create employee", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Rate history", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({ path: "artifacts/workz-mobile.png", fullPage: true });
});
