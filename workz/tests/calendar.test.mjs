import test from "node:test";
import assert from "node:assert/strict";
import { period, inDay, shift, zoned } from "../src/calendar.mjs";
test("monthly and weekly boundaries", () => {
  assert.equal(period("2030-02-15", "month").days.length, 28);
  assert.equal(period("2030-02-01", "week").days[0], "2030-01-28");
});
test("multi-day interval uses exclusive end", () => {
  assert.equal(
    inDay("2030-01-31T23:00:00", "2030-02-01T01:00:00", "2030-02-01"),
    true,
  );
  assert.equal(
    inDay("2030-01-31T23:00:00", "2030-02-01T00:00:00", "2030-02-01"),
    false,
  );
});
test("moves preserve duration and change calendar date", () => {
  const [a, b] = shift(
    "2030-01-31T09:00:00Z",
    "2030-01-31T11:30:00Z",
    "2030-01-31",
    "2030-02-01",
  );
  assert.equal(a, "2030-02-01T09:00:00.000Z");
  assert.equal(b, "2030-02-01T11:30:00.000Z");
});
test("site timestamps become explicit instants", () => {
  assert.equal(
    zoned("2030-01-01 09:00:00", "Australia/Sydney"),
    "2029-12-31T22:00:00.000Z",
  );
  assert.equal(
    zoned("2030-01-01T09:00:00+11:00", "UTC"),
    "2029-12-31T22:00:00.000Z",
  );
});

test("DST gaps rejected and repeated times require explicit offset", async () => {
  const { toInstant } = await import("../src/calendar.mjs");
  const previous = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    assert.throws(() => toInstant("2030-03-10T02:30"), /does not exist/);
    assert.throws(() => toInstant("2030-11-03T01:30"), /Repeated/);
    assert.equal(
      toInstant("2030-11-03T01:30", "-04:00"),
      "2030-11-03T05:30:00.000Z",
    );
    assert.equal(
      toInstant("2030-11-03T01:30", "-05:00"),
      "2030-11-03T06:30:00.000Z",
    );
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});
