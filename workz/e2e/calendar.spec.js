import { test, expect } from "@playwright/test";

test("palette creation, pointer move/resize, persistence, cancellation and approval locks in both calendars", async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 1600, height: 1600 });
  await page.clock.install({ time: new Date("2030-02-04T12:00:00Z") });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  async function actor(user) {
    await context.addCookies([
      { name: "synthetic_user", value: user, url: "http://127.0.0.1:8765" },
    ]);
  }
  async function call(action, payload = {}) {
    const response = await context.request.post(
      "http://127.0.0.1:8765/api/method/erplite.workz.api.run",
      { data: { action, payload } },
    );
    const result = await response.json();
    expect(response.ok(), JSON.stringify(result)).toBeTruthy();
    return result.message;
  }
  await actor("Administrator");
  const project = await call("save_project", {
    project_name: "Calendar regression project",
    status: "Open",
    project_lead: "lead",
    timesheet_approver: "approver",
  });
  const activity = await call("save_activity", {
    project: project.name,
    activity_name: "Calendar regression activity",
    status: "Open",
  });
  await call("assignment", {
    employee: "alice",
    activity: activity.name,
    assigned: true,
  });
  await actor("alice");
  const title = "Calendar regression activity";
  async function drag(source, target, release = true) {
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
    if (release) await page.mouse.up();
  }
  async function resize(handle, dy) {
    await handle.scrollIntoViewIfNeeded();
    const box = await handle.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 + dy, {
      steps: 8,
    });
    await page.mouse.up();
  }
  for (const mode of ["planning", "timesheet"]) {
    await page.goto("/workz/" + mode);
    const palette = page.getByRole("button", {
      name: "Schedule " + title,
      exact: true,
    });
    const slot = (day) => page.locator(`[data-slot="2030-02-${day} 09:00"]`);
    await drag(palette, slot("04"));
    const entry = page.locator("article.time-entry").filter({ hasText: title });
    await expect(entry).toHaveCount(1);
    await expect(entry).toContainText("09:00–10:00");
    await drag(
      entry.getByRole("button", { name: "Move " + title, exact: true }),
      page.locator('[data-slot="2030-02-05 10:00"]'),
    );
    await expect(
      page.locator('[data-day="2030-02-05"]').locator("article.time-entry"),
    ).toHaveCount(1);
    await expect(entry).toContainText("10:00–11:00");
    await resize(
      entry.getByRole("button", {
        name: "Resize end of " + title,
        exact: true,
      }),
      30,
    );
    await expect(entry).toContainText("10:00–11:30");
    await resize(
      entry.getByRole("button", {
        name: "Resize start of " + title,
        exact: true,
      }),
      15,
    );
    await expect(entry).toContainText("10:15–11:30");
    await page.reload();
    await expect(entry).toContainText("10:15–11:30");
    await drag(
      entry.getByRole("button", { name: "Move " + title, exact: true }),
      slot("06"),
      false,
    );
    await page.keyboard.press("Escape");
    await page.mouse.up();
    await expect(
      page.locator('[data-day="2030-02-05"]').locator("article.time-entry"),
    ).toHaveCount(1);
    // A second activity dropped onto an occupied time must roll back, not create a phantom block.
    await drag(palette, page.locator('[data-slot="2030-02-05 10:30"]'));
    await expect(page.getByRole("alert")).toContainText("Conflicts");
    await expect(entry).toHaveCount(1);
    await page.getByRole("button", { name: "Dismiss", exact: true }).click();
    await page.getByRole("button", { name: "day", exact: true }).click();
    await expect(page.locator(".time-day-column")).toHaveCount(1);
    await page.getByRole("button", { name: "week", exact: true }).click();
    await expect(page.locator(".time-day-column")).toHaveCount(7);
    await page.getByRole("button", { name: "month", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "month calendar", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "week", exact: true }).click();
    await expect(page.locator(".time-day-column")).toHaveCount(7);
    if (mode === "timesheet") {
      const rows = await call("times", {
        start: "2030-02-04T00:00:00Z",
        end: "2030-02-11T00:00:00Z",
      });
      const row = rows.find((r) => r.activity === activity.name);
      await call("transition", { ...row, status: "Submitted" });
      await page.reload();
      await expect(entry).toContainText("Locked · Submitted");
      await expect(
        entry.getByRole("button", { name: "Move " + title, exact: true }),
      ).toHaveCount(0);
      await expect(entry.locator(".resize-handle")).toHaveCount(0);
      await actor("approver");
      await call("transition", {
        ...(
          await call("times", {
            start: "2030-02-04T00:00:00Z",
            end: "2030-02-11T00:00:00Z",
          })
        ).find((r) => r.name === row.name),
        status: "Approved",
      });
      await actor("alice");
      await page.reload();
      await expect(entry).toContainText("Locked · Approved");
    }
    await page.screenshot({
      path: `artifacts/workz-${mode}-drag-drop.png`,
      fullPage: true,
    });
  }
  await page.goto("/workz/todos");
  await expect(
    page.getByRole("heading", { name: "Projects & assignments", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Todos", exact: true }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
