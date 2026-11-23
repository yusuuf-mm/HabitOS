import { useEffect, useMemo, useState } from "react";
import { Flag, Lock } from "lucide-react";
import { localISODate } from "@/lib/localDate";
import {
  resolveObjective,
  type ObjectiveStyle,
} from "@/lib/objectivePalette";
import { ObjectiveShape } from "@/components/ObjectiveShape";
import type { WeekDayData, SelectedBlock, SessionBlock, RangeEntry } from "@/types/dashboard";

interface WeekCalendarProps {
  weekStart: Date;
  days: WeekDayData[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  onOpenBlock: (block: SelectedBlock) => void;
}

const AXIS_START = 300; // 05:00
const AXIS_MINUTES = 1140; // 05:00 - 24:00
const AXIS_LABELS = [5, 8, 12, 18, 24];
const HOUR_PX = 72;
const QUARTER_PX = HOUR_PX / 4; // 18px per 15-minute block

function toMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function topPx(time: string): number {
  return ((toMinutes(time) - AXIS_START) / 15) * QUARTER_PX;
}

function heightPx(startTime: string, endTime: string): number {
  const start = Math.max(toMinutes(startTime), AXIS_START);
  const end = Math.min(toMinutes(endTime), 1440);
  return Math.max(((end - start) / 15) * QUARTER_PX, QUARTER_PX);
}

function dayName(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString("en-US", { weekday: "long" });
}

function fullDate(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

function shortDate(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

interface TimedInterval {
  key: string;
  start: number;
  end: number;
}

/** Assign side-by-side columns to intervals that overlap in the same day. */
export function layoutOverlaps(
  intervals: readonly TimedInterval[],
): Map<string, { column: number; columns: number }> {
  const result = new Map<string, { column: number; columns: number }>();
  const sorted = [...intervals].sort((a, b) => a.start - b.start || a.end - b.end);
  const clusters: TimedInterval[][] = [];
  let current: TimedInterval[] = [];
  let clusterEnd = -Infinity;

  for (const interval of sorted) {
    if (current.length > 0 && interval.start >= clusterEnd) {
      clusters.push(current);
      current = [];
      clusterEnd = -Infinity;
    }
    current.push(interval);
    clusterEnd = Math.max(clusterEnd, interval.end);
  }
  if (current.length > 0) clusters.push(current);

  for (const cluster of clusters) {
    const columnEnds: number[] = [];
    const assigned: { interval: TimedInterval; column: number }[] = [];
    for (const interval of cluster) {
      let column = columnEnds.findIndex((end) => end <= interval.start);
      if (column === -1) {
        column = columnEnds.length;
        columnEnds.push(interval.end);
      } else {
        columnEnds[column] = interval.end;
      }
      assigned.push({ interval, column });
    }
    for (const { interval, column } of assigned) {
      result.set(interval.key, { column, columns: columnEnds.length });
    }
  }
  return result;
}

function useCompactCalendar(): boolean {
  const [compact, setCompact] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 639px)").matches
      : false,
  );

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(max-width: 639px)");
    const onChange = () => setCompact(query.matches);
    query.addEventListener?.("change", onChange);
    return () => query.removeEventListener?.("change", onChange);
  }, []);

  return compact;
}

function ObjectiveCaption({
  objective,
  id,
}: {
  objective: ObjectiveStyle;
  id: string;
}) {
  return (
    <span id={id} className="sr-only">
      Main objective: {objective.label}
    </span>
  );
}

function sessionObjective(session: SessionBlock): ObjectiveStyle {
  return resolveObjective(session.objectiveName);
}

function SessionButton({
  session,
  day,
  dayIndex,
  index,
  objective,
  position,
  nowrap,
  onOpenBlock,
  onKeyDown,
}: {
  session: SessionBlock;
  day: WeekDayData;
  dayIndex: number;
  index: number;
  objective: ObjectiveStyle;
  position?: { column: number; columns: number };
  nowrap: boolean;
  onOpenBlock: (block: SelectedBlock) => void;
  onKeyDown: (e: React.KeyboardEvent, dayIndex: number, blockIndex: number, kind: "session") => void;
}) {
  const released = Boolean(session.releasedAt);
  const stateClass = released
    ? "border-dashed border-zinc-400 commitment-hatch opacity-60 dark:border-zinc-500"
    : session.completed
    ? "border-2"
    : "border";
  const describedBy = `objective-session-${dayIndex}-${session.id}`;
  const shortBlock = nowrap && toMinutes(session.endTime) - toMinutes(session.startTime) <= 15;

  return (
    <button
      key={`session-${session.id}`}
      id={`session-${dayIndex}-${session.id}`}
      type="button"
      data-objective={objective.key}
      title={`${session.title} — ${objective.label}${session.objectiveName ? "" : " (no objective recorded)"}`}
      aria-describedby={describedBy}
      aria-label={`${dayName(day.date)} ${session.startTime} to ${session.endTime}, ${session.title}, planned session${released ? ", released" : session.completed ? ", completed" : ""}`}
      onClick={() => onOpenBlock({ type: "session", day, session })}
      onKeyDown={(e) => onKeyDown(e, dayIndex, index, "session")}
      className={`absolute overflow-hidden rounded px-1 py-0.5 text-left ${stateClass}`}
      style={{
        top: `${topPx(session.startTime)}px`,
        height: `${heightPx(session.startTime, session.endTime)}px`,
        backgroundColor: released ? undefined : objective.tint,
        color: released ? undefined : objective.ink,
        borderColor: released ? undefined : objective.ink,
        left: position
          ? `calc(${position.column * (100 / position.columns)}% + 2px)`
          : "2px",
        width: position
          ? `calc(${100 / position.columns}% - 4px)`
          : "calc(100% - 4px)",
      }}
    >
      <ObjectiveCaption objective={objective} id={describedBy} />
      <span className="flex items-start gap-1 text-[10px] font-medium leading-tight">
        <ObjectiveShape
          shape={objective.shape}
          color="currentColor"
          size={11}
          className="mt-[1px] shrink-0"
        />
        <span className={shortBlock ? "truncate" : "line-clamp-2"}>{session.title}</span>
      </span>
      {!shortBlock && (
        <span className="flex items-center gap-1 text-[9px] leading-tight opacity-75">
          <span aria-hidden="true" className="font-mono">
            {objective.short}
          </span>
          <span>
            {session.startTime}–{session.endTime}
            {released ? " · Released" : session.completed ? " · Done" : ""}
          </span>
        </span>
      )}
    </button>
  );
}

function CommitmentButton({
  commitment,
  day,
  dayIndex,
  index,
  position,
  onOpenBlock,
  onKeyDown,
}: {
  commitment: RangeEntry;
  day: WeekDayData;
  dayIndex: number;
  index: number;
  position?: { column: number; columns: number };
  onOpenBlock: (block: SelectedBlock) => void;
  onKeyDown: (e: React.KeyboardEvent, dayIndex: number, blockIndex: number, kind: "commitment") => void;
}) {
  const timed = Boolean(commitment.startTime && commitment.endTime);
  return (
    <button
      id={`commitment-${dayIndex}-${commitment.itemId}`}
      type="button"
      aria-label={`${dayName(day.date)} ${commitment.startTime ?? ""} to ${commitment.endTime ?? ""}, ${commitment.title}, fixed commitment`}
      onClick={() => onOpenBlock({ type: "commitment", day, item: commitment })}
      onKeyDown={(e) => onKeyDown(e, dayIndex, index, "commitment")}
      className="absolute overflow-hidden rounded border border-dashed border-zinc-400 commitment-hatch px-1 py-0.5 text-left text-zinc-700 dark:border-zinc-500 dark:text-zinc-200"
      style={{
        top: timed ? `${topPx(commitment.startTime ?? "00:00")}px` : `${48 + index * 26}px`,
        height: timed
          ? `${heightPx(commitment.startTime ?? "00:00", commitment.endTime ?? "00:00")}px`
          : "24px",
        left: position
          ? `calc(${position.column * (100 / position.columns)}% + 2px)`
          : "2px",
        width: position
          ? `calc(${100 / position.columns}% - 4px)`
          : "calc(100% - 4px)",
      }}
    >
      <span className="flex items-start gap-1 text-[10px] font-medium leading-tight">
        <Lock className="mt-[1px] h-3 w-3 shrink-0" />
        <span className="line-clamp-2">{commitment.title}</span>
      </span>
      {timed && (
        <span className="block text-[9px] leading-tight opacity-75">
          Fixed {commitment.startTime}–{commitment.endTime}
        </span>
      )}
    </button>
  );
}

export function WeekCalendar({
  weekStart,
  days,
  selectedDate,
  onSelectDate,
  onOpenBlock,
}: WeekCalendarProps) {
  const [showLegend, setShowLegend] = useState(false);
  const compact = useCompactCalendar();
  const todayStr = localISODate(new Date());
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nowTop = ((nowMinutes - AXIS_START) / AXIS_MINUTES) * 100;

  const objectivesInWeek = useMemo(() => {
    const names = new Set<string>();
    for (const day of days) {
      for (const session of day.sessions) {
        if (session.objectiveName) names.add(session.objectiveName);
      }
    }
    return [...names].sort().map((name) => resolveObjective(name));
  }, [days]);

  const summaryLine = useMemo(() => {
    const totalSessions = days.reduce((n, d) => n + d.sessions.length, 0);
    const totalCommitments = days.reduce((n, d) => n + d.commitments.length, 0);
    const totalDeadlines = days.reduce((n, d) => n + d.deadlines.length, 0);
    let busiest: WeekDayData | null = null;
    let busiestMinutes = -1;
    for (const d of days) {
      const mins = d.sessions.reduce((n, s) => n + s.duration, 0);
      if (mins > busiestMinutes) {
        busiestMinutes = mins;
        busiest = d;
      }
    }
    const allDeadlines = days
      .flatMap((d) => d.deadlines.map((dl) => ({ date: d.date, title: dl.title })))
      .sort((a, b) => a.date.localeCompare(b.date));
    const next = allDeadlines[0];
    const parts = [
      `${totalSessions} session${totalSessions === 1 ? "" : "s"}`,
      `${totalCommitments} commitment${totalCommitments === 1 ? "" : "s"}`,
      `${totalDeadlines} deadline${totalDeadlines === 1 ? "" : "s"}`,
    ];
    if (busiest && busiestMinutes > 0) {
      parts.push(`busiest day ${dayName(busiest.date)} (${busiestMinutes} min)`);
    }
    if (next) parts.push(`next deadline ${fullDate(next.date)} — ${next.title}`);
    return parts.join(" · ");
  }, [days]);

  const blockId = (
    kind: "session" | "commitment" | "deadline",
    dayIndex: number,
    target: { id?: string; itemId?: string },
  ) => `${kind}-${dayIndex}-${target.id ?? target.itemId}`;

  const handleBlockKeyDown = (
    e: React.KeyboardEvent,
    dayIndex: number,
    blockIndex: number,
    kind: "session" | "commitment" | "deadline",
  ) => {
    const listFor = (index: number) =>
      kind === "session"
        ? days[index].sessions
        : kind === "commitment"
        ? days[index].commitments
        : days[index].deadlines;

    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const target = listFor(dayIndex)[blockIndex + (e.key === "ArrowDown" ? 1 : -1)];
      if (target) document.getElementById(blockId(kind, dayIndex, target))?.focus();
      return;
    }
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const nextDay = dayIndex + (e.key === "ArrowRight" ? 1 : -1);
    if (nextDay < 0 || nextDay >= days.length) return;
    const list = listFor(nextDay);
    const target = list[Math.min(blockIndex, list.length - 1)];
    if (target) document.getElementById(blockId(kind, nextDay, target))?.focus();
  };

  const handleSessionKeys = (
    e: React.KeyboardEvent,
    dayIndex: number,
    blockIndex: number,
    kind: "session",
  ) => handleBlockKeyDown(e, dayIndex, blockIndex, kind);
  const handleCommitmentKeys = (
    e: React.KeyboardEvent,
    dayIndex: number,
    blockIndex: number,
    kind: "commitment",
  ) => handleBlockKeyDown(e, dayIndex, blockIndex, kind);

  const selectedDay =
    days.find((day) => day.date === selectedDate) ?? days[0] ?? null;

  const agendaEntries = useMemo(() => {
    if (!selectedDay) return [];
    type AgendaEntry =
      | { kind: "session"; start: number; session: SessionBlock }
      | { kind: "commitment"; start: number; commitment: RangeEntry };
    const entries: AgendaEntry[] = [
      ...selectedDay.sessions.map((session) => ({
        kind: "session" as const,
        start: toMinutes(session.startTime),
        session,
      })),
      ...selectedDay.commitments.map((commitment) => ({
        kind: "commitment" as const,
        start: commitment.startTime ? toMinutes(commitment.startTime) : 24 * 60,
        commitment,
      })),
    ];
    return entries.sort((a, b) => a.start - b.start);
  }, [selectedDay]);

  const timingsFor = (day: WeekDayData) => {
    const intervals: TimedInterval[] = day.sessions.map((s) => ({
      key: `session-${s.id}`,
      start: toMinutes(s.startTime),
      end: toMinutes(s.endTime),
    }));
    for (const c of day.commitments) {
      if (c.startTime && c.endTime) {
        intervals.push({
          key: `commitment-${c.itemId}`,
          start: toMinutes(c.startTime),
          end: toMinutes(c.endTime),
        });
      }
    }
    return layoutOverlaps(intervals);
  };

  return (
    <section aria-label="Week calendar" className="dashboard-card">
      <p className="text-sm text-muted-foreground">{summaryLine}</p>
      <div className="mt-3">
        <button
          type="button"
          aria-expanded={showLegend}
          onClick={() => setShowLegend((v) => !v)}
          className="text-xs font-medium text-accent underline underline-offset-2"
        >
          {showLegend ? "Hide legend" : "What do the shapes mean?"}
        </button>
        {showLegend && (
          <div className="mt-3 space-y-3 text-xs text-muted-foreground">
            {objectivesInWeek.length > 0 && (
              <ul className="flex flex-wrap gap-x-5 gap-y-2">
                {objectivesInWeek.map((objective) => (
                  <li key={objective.key} className="flex items-center gap-1.5">
                    <ObjectiveShape
                      shape={objective.shape}
                      color={objective.swatch}
                      stroke={objective.ink}
                      size={14}
                    />
                    <span className="font-mono text-[9px] opacity-80">{objective.short}</span>
                    <span>{objective.label}</span>
                  </li>
                ))}
              </ul>
            )}
            <ul className="space-y-1">
              <li className="flex items-center gap-2">
                <span className="inline-block h-3 w-6 rounded border border-dashed border-zinc-400 commitment-hatch align-middle" />
                Dashed, hatched block with lock — a fixed commitment that stays put.
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block h-3 w-6 rounded border border-dashed border-zinc-400 bg-zinc-100/70 align-middle opacity-60 dark:bg-zinc-800/40" />
                Faded, hatched block — a session you released before it started.
              </li>
              <li className="flex items-center gap-2">
                <Flag className="h-3.5 w-3.5" />
                Flag at the top — a deadline due that day.
              </li>
            </ul>
            <p>Colours are fixed per objective and always paired with a shape and code.</p>
          </div>
        )}
      </div>

      {/* Day strip — kept on every viewport, including 390px. */}
      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {days.map((day) => {
          const isToday = day.date === todayStr;
          const isSelected = day.date === selectedDate;
          return (
            <button
              key={day.date}
              type="button"
              aria-label={`Open agenda for ${fullDate(day.date)}${day.unavailable ? " (unavailable)" : ""}`}
              aria-pressed={isSelected}
              onClick={() => {
                onSelectDate(day.date);
                onOpenBlock({ type: "day", day });
              }}
              className={
                isToday
                  ? "min-w-[3.25rem] shrink-0 rounded-full border-2 border-accent px-1 py-1.5 text-center text-xs font-semibold"
                  : isSelected
                  ? "min-w-[3.25rem] shrink-0 rounded-full bg-accent/10 px-1 py-1.5 text-center text-xs font-semibold"
                  : "min-w-[3.25rem] shrink-0 rounded-full px-1 py-1.5 text-center text-xs font-medium text-muted-foreground hover:bg-muted"
              }
            >
              <span className="block">
                {new Date(`${day.date}T00:00:00`).toLocaleDateString("en-US", {
                  weekday: "short",
                })}
              </span>
              <span className="block">
                {new Date(`${day.date}T00:00:00`).getDate()}
              </span>
            </button>
          );
        })}
      </div>

      {compact ? (
        // 390px: the day strip above plus a single-day agenda. No inner scrollbar.
        <div className="mt-4">
          <h3 className="text-sm font-semibold">{shortDate(selectedDay?.date ?? "")}</h3>
          {selectedDay?.unavailable ? (
            <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
              This day&apos;s schedule could not be loaded.
            </p>
          ) : selectedDay &&
            selectedDay.sessions.length === 0 &&
            selectedDay.commitments.length === 0 &&
            selectedDay.deadlines.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">Nothing planned</p>
          ) : (
            <ol className="mt-2 space-y-2">
              {selectedDay?.deadlines.map((dl) => (
                <li key={`deadline-${dl.itemId}`}>
                  <button
                    type="button"
                    aria-label={`${fullDate(selectedDay.date)}, deadline ${dl.title}`}
                    onClick={() => onOpenBlock({ type: "deadline", day: selectedDay, item: dl })}
                    className="flex w-full items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-left text-sm"
                  >
                    <Flag className="h-4 w-4 shrink-0 text-warning" />
                    <span className="truncate">{dl.title}</span>
                    <span className="ml-auto text-xs text-muted-foreground">Due {dl.dueOn ?? selectedDay.date}</span>
                  </button>
                </li>
              ))}
              {agendaEntries.map((entry) => {
                if (entry.kind === "commitment") {
                  const c = entry.commitment;
                  return (
                    <li key={`commitment-${c.itemId}`}>
                      <button
                        type="button"
                        aria-label={`${dayName(selectedDay.date)} ${c.startTime ?? ""} to ${c.endTime ?? ""}, ${c.title}, fixed commitment`}
                        onClick={() => onOpenBlock({ type: "commitment", day: selectedDay, item: c })}
                        className="flex w-full items-center gap-2 rounded-lg border border-dashed border-zinc-400 commitment-hatch px-3 py-2 text-left text-sm text-zinc-700 dark:border-zinc-500 dark:text-zinc-200"
                      >
                        <Lock className="h-4 w-4 shrink-0" />
                        <span className="truncate">{c.title}</span>
                        <span className="ml-auto shrink-0 text-xs opacity-75">
                          {c.startTime && c.endTime ? `${c.startTime}–${c.endTime}` : "Fixed"}
                        </span>
                      </button>
                    </li>
                  );
                }
                const s = entry.session;
                const objective = sessionObjective(s);
                const stateClass = s.releasedAt
                  ? "border-dashed border-zinc-400 commitment-hatch opacity-60"
                  : s.completed
                    ? "border-2"
                    : "border";
                return (
                  <li key={`session-${s.id}`}>
                    <button
                      type="button"
                      data-objective={objective.key}
                      aria-label={`${dayName(selectedDay.date)} ${s.startTime} to ${s.endTime}, ${s.title}, planned session${s.releasedAt ? ", released" : s.completed ? ", completed" : ""}`}
                      aria-describedby={`objective-agenda-${selectedDay.date}-${s.id}`}
                      onClick={() => onOpenBlock({ type: "session", day: selectedDay, session: s })}
                      className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${stateClass}`}
                      style={{
                        backgroundColor: s.releasedAt ? undefined : objective.tint,
                        color: s.releasedAt ? undefined : objective.ink,
                        borderColor: s.releasedAt ? undefined : objective.ink,
                      }}
                    >
                      <ObjectiveCaption
                        objective={objective}
                        id={`objective-agenda-${selectedDay.date}-${s.id}`}
                      />
                      <ObjectiveShape shape={objective.shape} color="currentColor" size={14} />
                      <span aria-hidden="true" className="font-mono text-[10px] opacity-80">
                        {objective.short}
                      </span>
                      <span className="truncate">{s.title}</span>
                      <span className="ml-auto shrink-0 text-xs opacity-75">
                        {s.startTime}–{s.endTime}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      ) : (
        // Desktop: full-width, tall grid. Overlapping blocks sit side by side.
        <div className="mt-4">
          <div className="grid grid-cols-7 gap-2">
            {days.map((day, dayIndex) => {
              const isEmpty =
                !day.unavailable &&
                day.sessions.length === 0 &&
                day.commitments.length === 0 &&
                day.deadlines.length === 0;
              const positions = timingsFor(day);
              return (
                <div key={day.date} className="min-w-0">
                  <div className="calendar-column relative rounded-lg border border-border/50 bg-muted/5">
                    {dayIndex === 0 && (
                      <div className="pointer-events-none absolute inset-0">
                        {AXIS_LABELS.map((h) => (
                          <span
                            key={h}
                            className="absolute right-1 text-[9px] text-muted-foreground/70"
                            style={{ top: `${((h * 60 - AXIS_START) / AXIS_MINUTES) * 100}%` }}
                          >
                            {h.toString().padStart(2, "0")}
                          </span>
                        ))}
                      </div>
                    )}

                    {day.unavailable && (
                      <p className="absolute left-1 right-1 top-2 text-center text-[10px] text-amber-700 dark:text-amber-300">
                        Unavailable
                      </p>
                    )}
                    {isEmpty && (
                      <p className="absolute left-1 right-1 top-2 text-center text-[10px] text-muted-foreground">
                        Nothing planned
                      </p>
                    )}

                    {day.deadlines.map((dl, i) => (
                      <button
                        key={`deadline-${dl.itemId}`}
                        id={`deadline-${dayIndex}-${dl.itemId}`}
                        type="button"
                        title={`${dl.title} — due ${dl.dueOn ?? day.date}`}
                        aria-label={`${fullDate(day.date)}, deadline ${dl.title}`}
                        onClick={() => onOpenBlock({ type: "deadline", day, item: dl })}
                        onKeyDown={(e) => handleBlockKeyDown(e, dayIndex, i, "deadline")}
                        className="absolute left-1 z-10 flex items-center gap-1 rounded bg-warning/15 px-1.5 py-0.5 text-[10px] font-medium text-warning"
                        style={{ top: `${i * 20}px` }}
                      >
                        <Flag className="h-3 w-3 shrink-0" />
                        <span className="max-w-[5rem] truncate">{dl.title}</span>
                      </button>
                    ))}

                    {day.sessions.map((s, i) => (
                      <SessionButton
                        key={`session-${s.id}`}
                        session={s}
                        day={day}
                        dayIndex={dayIndex}
                        index={i}
                        objective={sessionObjective(s)}
                        position={positions.get(`session-${s.id}`)}
                        nowrap
                        onOpenBlock={onOpenBlock}
                        onKeyDown={handleSessionKeys}
                      />
                    ))}

                    {day.commitments.map((c, i) => (
                      <CommitmentButton
                        key={`commitment-${c.itemId}`}
                        commitment={c}
                        day={day}
                        dayIndex={dayIndex}
                        index={i}
                        position={c.startTime ? positions.get(`commitment-${c.itemId}`) : undefined}
                        onOpenBlock={onOpenBlock}
                        onKeyDown={handleCommitmentKeys}
                      />
                    ))}

                    {day.date === todayStr &&
                      nowMinutes >= AXIS_START &&
                      nowMinutes <= 1440 && (
                        <div
                          className="pointer-events-none absolute left-0 right-0 z-10 h-px bg-accent"
                          style={{ top: `${nowTop}%` }}
                          aria-hidden="true"
                        />
                      )}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="sr-only">Week starting {fullDate(days[0]?.date ?? "")}</p>
        </div>
      )}

      {/* Kept for callers that pass the week start; the visible strip uses `days`. */}
      <span className="sr-only">Week of {weekStart.toDateString()}</span>
    </section>
  );
}
