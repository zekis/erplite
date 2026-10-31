// Interaction parity with Afterz d02c7b2: palette -> time slot, move, top/bottom resize.
// MIT attribution retained in docs/workz/AFTERZ-LICENSE.txt.
import React, { useEffect, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  pointerWithin,
  rectIntersection,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  inDay,
  localDate,
  shift,
  slotInstant,
  moveInterval,
  resizeInterval,
  timeSegments,
} from "./calendar.mjs";

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  kind: string;
  subtitle?: string;
  editable: boolean;
  allDay?: boolean;
  row: any;
}
export interface PaletteItem {
  id: string;
  title: string;
  subtitle?: string;
  kind: string;
  row: any;
}
interface Props {
  events: CalendarEvent[];
  palette: PaletteItem[];
  days: string[];
  view: string;
  mode: "Planning" | "Timesheet";
  busy: boolean;
  onCreate: (item: PaletteItem, start: string, end: string) => Promise<void>;
  onChange: (event: CalendarEvent, start: string, end: string) => Promise<void>;
  onSelect: (start: string, end: string) => void;
  onEdit: (event: CalendarEvent) => void;
  onError: (message: string) => void;
}
const clock = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
const timeLabel = (minute: number) =>
  `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;

function PaletteCard({
  item,
  disabled,
  onClick,
}: {
  item: PaletteItem;
  disabled: boolean;
  onClick: () => void;
}) {
  const drag = useDraggable({
    id: "palette:" + item.id,
    data: { item },
    disabled,
  });
  return (
    <button
      ref={drag.setNodeRef}
      {...drag.attributes}
      {...drag.listeners}
      disabled={disabled}
      className={`activity-card ${item.kind.toLowerCase()}`}
      aria-label={`Schedule ${item.title}`}
      onClick={onClick}
      style={{ opacity: drag.isDragging ? 0.35 : 1 }}
    >
      <strong>{item.title}</strong>
      <small>{item.subtitle || item.kind}</small>
    </button>
  );
}

function Slot({
  day,
  minute,
  mode,
  disabled,
  children,
  onClick,
}: {
  day: string;
  minute: number | null;
  mode: string;
  disabled: boolean;
  children?: React.ReactNode;
  onClick: () => void;
}) {
  const drop = useDroppable({
    id: `slot:${day}:${minute ?? "day"}`,
    data: { day, minute },
    disabled,
  });
  return (
    <div
      ref={drop.setNodeRef}
      className={`${minute === null ? "month-cell" : "time-slot"} ${drop.isOver ? "drop-target" : ""}`}
      data-slot={`${day} ${minute === null ? "day" : timeLabel(minute)}`}
    >
      <button
        className="slot-create"
        disabled={disabled}
        onClick={onClick}
        aria-label={`${mode === "Planning" ? "Plan" : "Book"} at ${day} ${minute === null ? "09:00" : timeLabel(minute)}`}
      >
        {minute === null ? day : ""}
      </button>
      {children}
    </div>
  );
}

function Entry({
  event,
  instanceId,
  anchorStart,
  disabled,
  style,
  handles = true,
  onEdit,
  onChange,
  onError,
}: {
  event: CalendarEvent;
  instanceId: string;
  anchorStart?: string;
  disabled: boolean;
  style?: React.CSSProperties;
  handles?: boolean | { start: boolean; end: boolean };
  onEdit: () => void;
  onChange: (start: string, end: string) => Promise<void>;
  onError: (message: string) => void;
}) {
  const editable = event.editable && !disabled;
  const drag = useDraggable({
    id: "event:" + instanceId,
    data: { event, sourceDay: instanceId.slice(0, 10), anchorStart },
    disabled: !editable,
  });
  const resize = useRef<{ edge: string; y: number } | null>(null);
  const [preview, setPreview] = useState<[string, string] | null>(null);
  const [resizing, setResizing] = useState(false);
  const cancelled = useRef(false);
  useEffect(() => {
    if (!resizing) return;
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        cancelled.current = true;
        resize.current = null;
        setPreview(null);
        setResizing(false);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [resizing]);
  const save = async (start: string, end: string) => {
    try {
      await onChange(start, end);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setPreview(null);
    }
  };
  const handle = (edge: "start" | "end") => (
    <button
      type="button"
      className={`resize-handle ${edge}`}
      aria-label={`Resize ${edge} of ${event.title}`}
      title={`Drag to resize; arrow keys change by 15 minutes`}
      onPointerDown={(e) => {
        e.stopPropagation();
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        cancelled.current = false;
        resize.current = { edge, y: e.clientY };
        setResizing(true);
      }}
      onPointerMove={(e) => {
        if (!resize.current) return;
        const minutes = Math.round((e.clientY - resize.current.y) / 15) * 15;
        try {
          setPreview(
            resizeInterval(event.start, event.end, edge, minutes) as [
              string,
              string,
            ],
          );
        } catch {}
      }}
      onPointerUp={(e) => {
        e.stopPropagation();
        const current = resize.current;
        resize.current = null;
        setResizing(false);
        if (!current || cancelled.current) return;
        const minutes = Math.round((e.clientY - current.y) / 15) * 15;
        if (!minutes) {
          setPreview(null);
          return;
        }
        try {
          const [a, b] = resizeInterval(event.start, event.end, edge, minutes);
          void save(a, b);
        } catch (error) {
          setPreview(null);
          onError((error as Error).message);
        }
      }}
      onPointerCancel={() => {
        resize.current = null;
        setResizing(false);
        setPreview(null);
      }}
      onKeyDown={(e) => {
        if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
        e.preventDefault();
        try {
          const [a, b] = resizeInterval(
            event.start,
            event.end,
            edge,
            e.key === "ArrowDown" ? 15 : -15,
          );
          void save(a, b);
        } catch (error) {
          onError((error as Error).message);
        }
      }}
    >
      {edge === "end" ? "═" : "─"}
    </button>
  );
  const [start, end] = preview || [event.start, event.end];
  const visualStyle = { ...style, opacity: drag.isDragging ? 0.35 : 1 };
  if (preview && style?.height !== undefined) {
    const deltaStart = (+new Date(start) - +new Date(event.start)) / 60000;
    const deltaEnd = (+new Date(end) - +new Date(event.end)) / 60000;
    visualStyle.top = Number(style.top) + deltaStart;
    visualStyle.height = Math.max(
      24,
      Number(style.height) + deltaEnd - deltaStart,
    );
  }
  return (
    <article
      ref={drag.setNodeRef}
      className={`time-entry ${event.kind.toLowerCase()} ${!event.editable ? "locked" : ""}`}
      style={visualStyle}
      data-entry={event.id}
      title={`${event.title}: ${new Date(start).toString()} – ${new Date(end).toString()}`}
    >
      {editable && (
        <button
          className="move-handle"
          {...drag.attributes}
          {...drag.listeners}
          aria-label={`Move ${event.title}`}
          title="Drag to another time"
        >
          ⠿
        </button>
      )}
      <button className="event-title" onClick={onEdit} disabled={!editable}>
        {event.title}
      </button>
      <small>
        {clock(start)}–{clock(end)} · {event.subtitle || event.kind}
      </small>
      {!event.editable && <small>Locked · {event.kind}</small>}
      {editable && handles && (
        <>
          {(handles === true || handles.start) && handle("start")}
          {(handles === true || handles.end) && handle("end")}
        </>
      )}
      {preview && (
        <output className="resize-preview">
          {clock(start)}–{clock(end)}
        </output>
      )}
    </article>
  );
}

export default function TimeCalendar(props: Props) {
  const {
    events,
    palette,
    days,
    view,
    mode,
    busy,
    onCreate,
    onChange,
    onSelect,
    onEdit,
    onError,
  } = props;
  const [fullDay, setFullDay] = useState(false),
    [search, setSearch] = useState(""),
    [active, setActive] = useState("");
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );
  const startHour = fullDay ? 0 : 6,
    endHour = fullDay ? 24 : 18;
  const minutes = Array.from(
    { length: (endHour - startHour) * 4 },
    (_, i) => startHour * 60 + i * 15,
  );
  const select = (day: string, minute: number) => {
    try {
      const a = slotInstant(day, minute);
      onSelect(a, new Date(+new Date(a) + 3600000).toISOString());
    } catch (e) {
      onError((e as Error).message);
    }
  };
  async function dropped({ active, over }: DragEndEvent) {
    setActive("");
    if (!over || busy) return;
    const target = over.data.current;
    if (!target?.day) return;
    try {
      const data = active.data.current;
      if (data?.item) {
        const start = slotInstant(target.day, target.minute ?? 540);
        await onCreate(
          data.item,
          start,
          new Date(+new Date(start) + 3600000).toISOString(),
        );
      } else if (data?.event) {
        const e = data.event as CalendarEvent;
        if (!e.editable) return;
        let a: string, b: string;
        if (e.allDay) {
          [a, b] = shift(e.start, e.end, data.sourceDay, target.day);
        } else if (target.minute == null) {
          const [moved] = shift(e.start, e.end, data.sourceDay, target.day);
          [a, b] = moveInterval(
            e.start,
            e.end,
            localDate(new Date(moved)),
            null,
          );
        } else {
          // Move the visible segment, retaining an overnight entry's hidden
          // portion rather than moving its original start into this slot.
          const delta =
            +new Date(slotInstant(target.day, target.minute)) -
            +new Date(data.anchorStart || e.start);
          a = new Date(+new Date(e.start) + delta).toISOString();
          b = new Date(+new Date(e.end) + delta).toISOString();
        }
        if (a !== e.start || b !== e.end) await onChange(e, a, b);
      }
    } catch (e) {
      onError((e as Error).message);
    }
  }
  const entry = (
    event: CalendarEvent,
    style?: React.CSSProperties,
    handles?: boolean | { start: boolean; end: boolean },
    key = event.id,
    anchorStart?: string,
  ) => (
    <Entry
      key={key}
      event={event}
      instanceId={key}
      anchorStart={anchorStart}
      disabled={busy}
      style={style}
      handles={handles}
      onEdit={() => onEdit(event)}
      onChange={(a, b) => onChange(event, a, b)}
      onError={onError}
    />
  );
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={(args) =>
        pointerWithin(args).length
          ? pointerWithin(args)
          : rectIntersection(args)
      }
      onDragStart={({ active }) =>
        setActive(
          active.data.current?.item?.title ||
            active.data.current?.event?.title ||
            "",
        )
      }
      onDragEnd={dropped}
      onDragCancel={() => setActive("")}
    >
      <div className="scheduling-workspace">
        <aside className="activity-palette" aria-label="Activities to schedule">
          <h2>Drag onto the calendar</h2>
          <p>
            Activities and calendar blocks. Click for the same form without
            dragging.
          </p>
          <label>
            Find activity
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Project or activity"
            />
          </label>
          {palette
            .filter((p) =>
              (p.title + " " + p.subtitle)
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((item) => (
              <PaletteCard
                key={item.id}
                item={item}
                disabled={busy}
                onClick={() => {
                  try {
                    const a = slotInstant(days[0], 540);
                    onEdit({
                      id: "",
                      title: item.title,
                      start: a,
                      end: new Date(+new Date(a) + 3600000).toISOString(),
                      kind: item.kind,
                      editable: true,
                      row: item.row,
                    });
                  } catch (e) {
                    onError((e as Error).message);
                  }
                }}
              />
            ))}
          {!palette.some((p) => p.row.activity) && (
            <p className="help">
              No assigned activities for this employee. Set up the project and
              activity assignments in Projects.
            </p>
          )}
        </aside>
        <section
          className="calendar-workspace"
          aria-label={`${mode} interactive calendar`}
        >
          <div className="calendar-options">
            <strong>
              {mode === "Planning"
                ? "Plan work and availability"
                : "Book actual time"}
            </strong>
            {view !== "month" && (
              <label>
                <input
                  type="checkbox"
                  checked={fullDay}
                  onChange={(e) => setFullDay(e.target.checked)}
                />
                Full day (00:00–24:00)
              </label>
            )}
          </div>
          <p className="help">
            Drag an activity to book one hour. Move with the grip; resize either
            edge in 15-minute steps. Click a time to use a form. Escape cancels
            a drag. Submitted and approved time stays locked.
          </p>
          {view === "month" ? (
            <div
              className="month-time-grid"
              role="region"
              aria-label="month calendar"
            >
              {Array.from(
                { length: (new Date(days[0] + "T12:00").getDay() + 6) % 7 },
                (_, i) => (
                  <div key={"pad" + i} />
                ),
              )}
              {days.map((day) => (
                <Slot
                  key={day}
                  day={day}
                  minute={null}
                  mode={mode}
                  disabled={busy}
                  onClick={() => select(day, 540)}
                >
                  {events
                    .filter((e) => inDay(e.start, e.end, day))
                    .map((e) => entry(e, undefined, false, day + e.id))}
                </Slot>
              ))}
            </div>
          ) : (
            <div
              className="time-grid-scroll"
              role="region"
              aria-label={`${view} calendar`}
            >
              <div
                className="time-grid"
                style={{
                  gridTemplateColumns: `58px repeat(${days.length}, minmax(125px, 1fr))`,
                }}
              >
                <div className="time-heading">Time</div>
                {days.map((day) => (
                  <div className="time-heading" key={day}>
                    {new Date(day + "T12:00").toLocaleDateString([], {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                ))}
                <div className="all-day-label">All day</div>
                {days.map((day) => (
                  <div className="all-day-cell" key={day}>
                    {events
                      .filter((e) => e.allDay && inDay(e.start, e.end, day))
                      .map((e) => entry(e, undefined, false, day + e.id))}
                  </div>
                ))}
                <div
                  className="time-ruler"
                  style={{ height: (endHour - startHour) * 60 }}
                >
                  {minutes
                    .filter((m) => m % 60 === 0)
                    .map((m) => (
                      <span key={m} style={{ top: m - startHour * 60 }}>
                        {timeLabel(m)}
                      </span>
                    ))}
                </div>
                {days.map((day) => (
                  <div
                    className="time-day-column"
                    key={day}
                    data-day={day}
                    style={{ height: (endHour - startHour) * 60 }}
                  >
                    {minutes.map((minute) => (
                      <Slot
                        key={minute}
                        day={day}
                        minute={minute}
                        mode={mode}
                        disabled={busy}
                        onClick={() => select(day, minute)}
                      />
                    ))}
                    {timeSegments(events, day, startHour, endHour).map(
                      (s: any) =>
                        entry(
                          s.event,
                          {
                            position: "absolute",
                            top: s.top,
                            height: s.height,
                            left: `${(s.lane * 100) / s.lanes}%`,
                            width: `${100 / s.lanes}%`,
                          },
                          { start: s.startHandle, end: s.endHandle },
                          day + s.event.id,
                          s.anchorStart,
                        ),
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
      <DragOverlay>
        {active ? <div className="calendar-drag-preview">{active}</div> : null}
      </DragOverlay>
    </DndContext>
  );
}
