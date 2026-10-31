export const localDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const localInput = (d) =>
  `${localDate(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
export function period(date, view) {
  const start = new Date(`${date}T00:00:00`);
  if (view === "month") start.setDate(1);
  else start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  const end = new Date(start);
  if (view === "month") end.setMonth(end.getMonth() + 1);
  else end.setDate(end.getDate() + 7);
  const days = [];
  for (let d = new Date(start); d < end; d.setDate(d.getDate() + 1))
    days.push(localDate(d));
  return { start: start.toISOString(), end: end.toISOString(), days };
}
export function shift(start, end, sourceDay, targetDay) {
  // Calendar days, not multiples of 24h: retain wall-clock times across DST.
  const source = new Date(sourceDay + "T12:00:00"),
    target = new Date(targetDay + "T12:00:00");
  const delta = Math.round(
    (Date.UTC(target.getFullYear(), target.getMonth(), target.getDate()) -
      Date.UTC(source.getFullYear(), source.getMonth(), source.getDate())) /
      86400000,
  );
  const a = new Date(start),
    b = new Date(end);
  a.setDate(a.getDate() + delta);
  b.setDate(b.getDate() + delta);
  return [a.toISOString(), b.toISOString()];
}
export function inDay(start, end, day) {
  const a = new Date(day + "T00:00:00"),
    b = new Date(a);
  b.setDate(b.getDate() + 1);
  return new Date(start) < b && new Date(end) > a;
}
// Server values are site-local naive timestamps. Resolve using explicit site zone.
export function zoned(value, zone) {
  if (!value) return "";
  if (/Z$|[+-]\d\d:\d\d$/.test(value)) return new Date(value).toISOString();
  const raw = value.replace(" ", "T").slice(0, 19),
    target = Date.parse(raw + "Z");
  let guess = target;
  for (let i = 0; i < 3; i++) {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: zone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
      })
        .formatToParts(new Date(guess))
        .map((p) => [p.type, p.value]),
    );
    const wall = Date.parse(
      `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}Z`,
    );
    guess += target - wall;
  }
  return new Date(guess).toISOString();
}

export function offsetFor(date) {
  const minutes = -date.getTimezoneOffset();
  return `${minutes < 0 ? "-" : "+"}${String(Math.floor(Math.abs(minutes) / 60)).padStart(2, "0")}:${String(Math.abs(minutes) % 60).padStart(2, "0")}`;
}
export function toInstant(value, offset = "") {
  if (offset && !/^[+-](0\d|1[0-4]):[0-5]\d$/.test(offset))
    throw Error("Use a UTC offset such as +11:00 or -05:00");
  const date = new Date(value + offset);
  if (!Number.isFinite(date.getTime()) || localInput(date) !== value)
    throw Error(
      "This clock time/offset does not exist in the displayed timezone",
    );
  if (!offset)
    for (let minutes = -180; minutes <= 180; minutes += 30) {
      if (
        minutes &&
        localInput(new Date(date.getTime() + minutes * 60000)) === value
      )
        throw Error(
          "Repeated DST clock time: specify the UTC offset to choose its occurrence",
        );
    }
  return date.toISOString();
}
