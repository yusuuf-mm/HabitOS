import { useMemo, useState } from "react";
import { Flag, Lock } from "lucide-react";
import { localISODate } from "@/lib/localDate";
import type { WeekDayData, SelectedBlock } from "@/types/dashboard";

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

function toMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function topPct(time: string): number {
  return ((toMinutes(time) - AXIS_START) / AXIS_MINUTES) * 100;
}

function heightPct(startTime: string, endTime: string): number {
  const start = Math.max(toMinutes(startTime), AXIS_START);
  const end = Math.min(toMinutes(endTime), 1440);
  return Math.max(((end - start) / AXIS_MINUTES) * 100, 2);
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

export function WeekCalendar({
  weekStart,
  days,
  selectedDate,
  onSelectDate,
  onOpenBlock,
}: WeekCalendarProps) {
  const [showLegend, setShowLegend] = useState(false);
  const todayStr = localISODate(new Date());
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nowTop = ((nowMinutes - AXIS_START) / AXIS_MINUTES) * 100;

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
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            <li>
              <span className="mr-2 inline-block h-3 w-6 rounded border border-accent/30 bg-accent/15 align-middle" />
              Solid block — a planned session you can mark done.
            </li>
            <li>
              <span className="mr-2 inline-block h-3 w-6 rounded border border-dashed border-zinc-400 align-middle" />
              Dashed block with lock — a fixed commitment that stays put.
            </li>
            <li>
              <span className="mr-2 inline-block h-3 w-6 rounded border border-dashed border-zinc-400 bg-zinc-100 align-middle opacity-60 dark:bg-zinc-800/60" />
              Faded block — a session you released before it started.
            </li>
            <li>
              <Flag className="mr-2 inline h-3.5 w-3.5 align-middle" />
              Flag at the top — a deadline due that day.
            </li>
          </ul>
        )}
      </div>

      <div className="mt-4 overflow-x-auto">
        <div className="grid min-w-[640px] grid-cols-7 gap-2">
          {days.map((day, dayIndex) => {
            const isToday = day.date === todayStr;
            const isSelected = day.date === selectedDate;
            const isEmpty =
              !day.unavailable &&
              day.sessions.length === 0 &&
              day.commitments.length === 0 &&
              day.deadlines.length === 0;
            return (
              <div key={day.date} className="min-w-0">
                <button
                  type="button"
                  aria-label={`Open agenda for ${fullDate(day.date)}${day.unavailable ? " (unavailable)" : ""}`}
                  aria-pressed={isSelected}
                  onClick={() => {
                    onSelectDate(day.date);
                    onOpenBlock({ type: "day", day });
                  }}
                  className={
                    isToday
                      ? "mb-2 w-full rounded-full border-2 border-accent px-1 py-1.5 text-center text-xs font-semibold"
                      : isSelected
                      ? "mb-2 w-full rounded-full bg-accent/10 px-1 py-1.5 text-center text-xs font-semibold"
                      : "mb-2 w-full rounded-full px-1 py-1.5 text-center text-xs font-medium text-muted-foreground hover:bg-muted"
                  }
                >
                  <span className="hidden sm:block">
                    {new Date(`${day.date}T00:00:00`).toLocaleDateString("en-US", {
                      weekday: "short",
                    })}
                  </span>
                  <span className="block">
                    {new Date(`${day.date}T00:00:00`).getDate()}
                  </span>
                </button>

                <div className="relative h-64 rounded-lg border border-border/50 bg-muted/10">
                  {/* axis labels */}
                  <div className="pointer-events-none absolute inset-0">
                    {AXIS_LABELS.map((h) => (
                      <span
                        key={h}
                        className="absolute right-1 text-[9px] text-muted-foreground/60"
                        style={{ top: `${((h * 60 - AXIS_START) / AXIS_MINUTES) * 100}%` }}
                      >
                        {h.toString().padStart(2, "0")}
                      </span>
                    ))}
                  </div>

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

                  {/* deadlines as flags pinned at top */}
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

                  {/* sessions */}
                  {day.sessions.map((s, i) => {
                    const released = Boolean(s.releasedAt);
                    const stateClass = released
                      ? "border-dashed border-zinc-400 bg-zinc-100/70 opacity-60 dark:border-zinc-500 dark:bg-zinc-800/40"
                      : s.completed
                      ? "border-accent/50 bg-accent/25"
                      : "border-accent/30 bg-accent/15";
                    return (
                      <button
                        key={`session-${s.id}`}
                        id={`session-${dayIndex}-${s.id}`}
                        type="button"
                        aria-label={`${dayName(day.date)} ${s.startTime} to ${s.endTime}, ${s.title}, planned session${released ? ", released" : s.completed ? ", completed" : ""}`}
                        onClick={() => onOpenBlock({ type: "session", day, session: s })}
                        onKeyDown={(e) => handleBlockKeyDown(e, dayIndex, i, "session")}
                        className={`absolute left-1 right-1 overflow-hidden rounded border px-1 py-0.5 text-left ${stateClass}`}
                        style={{
                          top: `${topPct(s.startTime)}%`,
                          height: `${heightPct(s.startTime, s.endTime)}%`,
                          minHeight: "18px",
                        }}
                      >
                        <span className="block truncate text-[10px] font-medium leading-tight">
                          {s.title}
                        </span>
                        <span className="block text-[9px] leading-tight text-muted-foreground">
                          {s.startTime}–{s.endTime}
                          {released ? " · Released" : s.completed ? " · Done" : ""}
                        </span>
                      </button>
                    );
                  })}

                  {/* commitments */}
                  {day.commitments.map((c, i) => (
                    <button
                      key={`commitment-${c.itemId}`}
                      id={`commitment-${dayIndex}-${c.itemId}`}
                      type="button"
                      aria-label={`${dayName(day.date)} ${c.startTime ?? ""} to ${c.endTime ?? ""}, ${c.title}, fixed commitment`}
                      onClick={() => onOpenBlock({ type: "commitment", day, item: c })}
                      onKeyDown={(e) => handleBlockKeyDown(e, dayIndex, i, "commitment")}
                      className="absolute left-1 right-1 overflow-hidden rounded border border-dashed border-zinc-400 bg-zinc-100 px-1 py-0.5 text-left dark:border-zinc-500 dark:bg-zinc-800/60"
                      style={{
                        top: c.startTime ? `${topPct(c.startTime)}%` : "auto",
                        height: c.startTime && c.endTime ? `${heightPct(c.startTime, c.endTime)}%` : "24px",
                        minHeight: "18px",
                        marginTop: c.startTime ? undefined : `${i * 24}px`,
                      }}
                    >
                      <span className="flex items-center gap-1 text-[10px] font-medium leading-tight">
                        <Lock className="h-3 w-3 shrink-0" />
                        <span className="truncate">{c.title}</span>
                      </span>
                      <span className="block text-[9px] leading-tight text-muted-foreground">
                        Fixed{c.startTime ? ` ${c.startTime}–${c.endTime ?? ""}` : ""}
                      </span>
                    </button>
                  ))}

                  {/* now line */}
                  {isToday && nowMinutes >= AXIS_START && nowMinutes <= 1440 && (
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
    </section>
  );
}
