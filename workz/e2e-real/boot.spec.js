import { test, expect } from "@playwright/test";
test("real Frappe session, CSRF, consolidated page and scoped API", async ({
  page,
}) => {
  const base = process.env.WORKZ_SYNTHETIC_URL;
  if (base !== "http://127.0.0.1:8766")
    throw Error("Use the disposable local synthetic server only");
  const login = await page.request.post(base + "/api/method/login", {
    form: { usr: "Administrator", pwd: process.env.WORKZ_SYNTHETIC_PASSWORD },
  });
  expect(login.ok(), await login.text()).toBeTruthy();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const response = await page.goto(base + "/workz");
  expect(response.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Refresh", exact: true }),
  ).toBeEnabled();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Settings & people", exact: true }),
  ).toBeVisible();
  const result = await page.evaluate(async () => {
    const response = await fetch("/api/method/erplite.workz.api.run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.workzBoot.csrf_token,
      },
      body: JSON.stringify({ action: "context", payload: {} }),
    });
    return { status: response.status, data: await response.json() };
  });
  expect(result.status).toBe(200);
  expect(result.data.message.user).toBe("Administrator");
  expect(errors).toEqual([]);
  await page.screenshot({
    path: "artifacts/workz-real-frappe.png",
    fullPage: true,
  });
});
