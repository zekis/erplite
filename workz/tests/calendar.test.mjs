import test from "node:test";
import assert from "node:assert/strict";
import {
  period,
  inDay,
  shift,
  zoned,
  slotInstant,
  moveInterval,
  resizeInterval,
  timeSegments,
} from "../src/calendar.mjs";
test("monthly and weekly boundaries", () => {
  assert.equal(period("2030-02-15", "month").days.length, 28);
  assert.equal(period("2030-02-01", "week").days[0], "2030-01-28");
});

test("time grid moves preserve elapsed duration across DST and reject ambiguous slots", () => {
  const previous = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    assert.equal(period("2030-03-10", "day").days.length, 1);
    assert.equal(
      new Date(period("2030-03-10", "day").end) -
        new Date(period("2030-03-10", "day").start),
      23 * 3600000,
    );
    assert.throws(() => slotInstant("2030-03-10", 150), /does not exist/);
    assert.throws(() => slotInstant("2030-11-03", 90), /Repeated/);
    const [a, b] = moveInterval(
      "2030-03-09T14:00Z",
      "2030-03-09T16:30Z",
      "2030-03-10",
      540,
    );
    assert.equal(a, "2030-03-10T13:00:00.000Z");
    assert.equal(+new Date(b) - +new Date(a), 2.5 * 3600000);
    assert.deepEqual(resizeInterval(a, b, "start", 15), [
      "2030-03-10T13:15:00.000Z",
      b,
    ]);
    assert.throws(() => resizeInterval(a, b, "end", -150), /at least 15/);
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

test("calendar splits overnight intervals with exclusive midnight and separates overlapping blocks", () => {
  const previous = process.env.TZ;
  process.env.TZ = "UTC";
  try {
    const events = [
      { id: "a", start: "2030-02-04T23:00Z", end: "2030-02-05T02:00Z" },
      { id: "b", start: "2030-02-05T01:00Z", end: "2030-02-05T03:00Z" },
    ];
    const [a] = timeSegments(events, "2030-02-04", 0, 24);
    assert.equal(a.top, 1380);
    assert.equal(a.height, 60);
    assert.equal(a.endHandle, false);
    const [b, c] = timeSegments(events, "2030-02-05", 0, 24);
    assert.equal(b.startHandle, false);
    assert.equal(b.lanes, 2);
    assert.notEqual(b.lane, c.lane);
    assert.equal(
      timeSegments(
        [{ start: "2030-02-04T23:00Z", end: "2030-02-05T00:00Z" }],
        "2030-02-05",
        0,
        24,
      ).length,
      0,
    );
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
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
