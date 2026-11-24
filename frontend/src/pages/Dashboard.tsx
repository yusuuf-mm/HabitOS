import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarRange, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageLoader } from "@/components/Loader";
import { PlanHealthRail } from "@/components/PlanHealthRail";
import { WeekCalendar } from "@/components/WeekCalendar";
import { DayDetailPanel } from "@/components/DayDetailPanel";
import { WeekPlanDialog } from "@/components/WeekPlanDialog";
import { InsightTiles } from "@/components/InsightTiles";
import { LifeMap } from "@/components/LifeMap";
import { HelperOrb } from "@/components/HelperOrb";
import { apiClient } from "@/services/apiClient";
import { addDays, localISODate, mondayOf } from "@/lib/localDate";
import { highestImpactObjective } from "@/lib/objectivePalette";
import type { DashboardSummary } from "@/types";
import type {
  HeroObjective,
  RangeEntry,
  SelectedBlock,
  SeriesDay,
  WeekDayData,
} from "@/types/dashboard";

const iso = localISODate;

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [series, setSeries] = useState<SeriesDay[]>([]);
  const [rangeDays, setRangeDays] = useState(7);
  const [weekStart, setWeekStart] = useState<Date>(() => mondayOf(new Date()));
  const [weekPlanOpen, setWeekPlanOpen] = useState(false);
  const [days, setDays] = useState<WeekDayData[]>([]);
  const [selectedDate, setSelectedDate] = useState(iso(new Date()));
  const [selectedBlock, setSelectedBlock] = useState<SelectedBlock | null>(null);
  const [objectives, setObjectives] = useState<HeroObjective[]>([]);
  const [upcoming, setUpcoming] = useState<RangeEntry[]>([]);
  const [helperText, setHelperText] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const [loadFailed, setLoadFailed] = useState(false);
  const [failures, setFailures] = useState({
    schedule: false,
    range: false,
    series: false,
    upcoming: false,
  });
  const rangeRequest = useRef(0);
  const weekRequest = useRef(0);

  const setFailure = useCallback((key: keyof typeof failures, failed: boolean) => {
    setFailures((prev) => (prev[key] === failed ? prev : { ...prev, [key]: failed }));
  }, []);

  const fetchSummary = useCallback(async () => {
    const requestId = rangeRequest.current;
    try {
      const response = await apiClient.analytics.getDashboardSummary(rangeDays);
      if (requestId !== rangeRequest.current) return;
      setSummary(response.data);
      setLoadFailed(false);
    } catch (error) {
      if (requestId !== rangeRequest.current) return;
      console.error("Failed to fetch dashboard summary:", error);
      setLoadFailed(true);
    } finally {
      if (requestId === rangeRequest.current) setIsLoading(false);
    }
  }, [rangeDays]);

  const fetchSeries = useCallback(async () => {
    const requestId = rangeRequest.current;
    try {
      const result = await apiClient.analytics.getSeries(rangeDays);
      if (requestId !== rangeRequest.current) return;
      setSeries(result);
      setFailure("series", false);
    } catch {
      if (requestId !== rangeRequest.current) return;
      // Keep the last good series: a failed request is not an empty history.
      setFailure("series", true);
    }
  }, [rangeDays, setFailure]);

  const fetchWeek = useCallback(async () => {
    const requestId = ++weekRequest.current;
    const dates = Array.from({ length: 7 }, (_, i) => iso(addDays(weekStart, i)));
    const schedules = await Promise.all(
      dates.map(async (date) => {
        try {
          return (await apiClient.schedule.getSchedule(date)).data;
        } catch {
          return null;
        }
      }),
    );
    let range: RangeEntry[] | null = null;
    try {
      range = await apiClient.items.getRange(dates[0], dates[6]);
    } catch {
      range = null;
    }
    if (requestId !== weekRequest.current) return;

    setFailure("schedule", schedules.some((s) => s === null));
    setFailure("range", range === null);

    const byDate = new Map<string, RangeEntry[]>();
    for (const entry of range ?? []) {
      const list = byDate.get(entry.date) ?? [];
      list.push(entry);
      byDate.set(entry.date, list);
    }

    // The life map reads each day's resolved plan, not the optimization-history
    // call (whose runs are dated by creation time and can be empty for a week
    // that is fully planned). Average each objective's share across the days
    // that actually reported it.
    const totals = new Map<string, { pct: number; count: number }>();
    for (const schedule of schedules) {
      for (const score of schedule?.objectiveScores ?? []) {
        if (!score.objectiveName) continue;
        const entry = totals.get(score.objectiveName) ?? { pct: 0, count: 0 };
        entry.pct += score.percentage ?? 0;
        entry.count += 1;
        totals.set(score.objectiveName, entry);
      }
    }
    setObjectives(
      Array.from(totals.entries())
        .filter(([, v]) => v.count > 0)
        .map(([name, v]) => {
          const pct = v.pct / v.count;
          return { name, value: pct, share: pct / 100 };
        })
        .filter((o) => o.share > 0)
        .sort((a, b) => b.share - a.share),
    );

    setDays((prev) => {
      const previous = new Map(prev.map((day) => [day.date, day]));
      return dates.map((date, idx) => {
        const schedule = schedules[idx];
        if (!schedule) {
          // Keep the last response for this day but say it is stale/unavailable;
          // an empty array here would claim the user has nothing planned.
          const old = previous.get(date);
          return {
            date,
            sessions: old?.sessions ?? [],
            commitments: old?.commitments ?? [],
            deadlines: old?.deadlines ?? [],
            unavailable: true,
          };
        }
        const entries = byDate.get(date) ?? previous.get(date)?.commitments ?? [];
        const oldDeadlines = range === null ? (previous.get(date)?.deadlines ?? []) : [];
        return {
          date,
          sessions: schedule.scheduledBehaviors.map((sb) => ({
            id: sb.id,
            title: sb.behavior?.name ?? "Session",
            startTime: sb.startTime,
            endTime: sb.endTime,
            duration: sb.duration,
            behaviorName: sb.behavior?.name ?? "Session",
            // A behaviour's main objective is the impact with the highest
            // impact_score, not the first row returned by the API.
            objectiveName: highestImpactObjective(sb.behavior?.objectiveImpacts)?.objectiveName,
            completed: sb.isCompleted,
            releasedAt: sb.releasedAt ?? null,
          })),
          commitments: entries.filter((e) => e.kind === "commitment"),
          deadlines: [
            ...entries.filter((e) => e.kind === "deadline"),
            ...oldDeadlines,
          ],
        };
      });
    });
  }, [weekStart, setFailure]);

  const fetchUpcoming = useCallback(async () => {
    const today = new Date();
    const from = iso(addDays(today, -14));
    const to = iso(addDays(today, 14));
    try {
      const result = await apiClient.items.getRange(from, to);
      setUpcoming(result);
      setFailure("upcoming", false);
    } catch {
      // Keep the last good list; a failed request is not "nothing upcoming".
      setFailure("upcoming", true);
    }
  }, [setFailure]);

  const fetchHelperStatus = useCallback(async () => {
    try {
      const s = await apiClient.helper.getStatus();
      setHelperText(
        s.configured
          ? "Plan assistant is switched on."
          : "Plan assistant is not switched on.",
      );
    } catch {
      setHelperText("Plan assistant status is unavailable.");
    }
  }, []);

  const fetchAll = useCallback(async () => {
    await Promise.all([
      fetchSummary(),
      fetchSeries(),
      fetchWeek(),
      fetchUpcoming(),
      fetchHelperStatus(),
    ]);
  }, [fetchSummary, fetchSeries, fetchWeek, fetchUpcoming, fetchHelperStatus]);

  useEffect(() => {
    rangeRequest.current += 1;
    void fetchSummary();
    void fetchSeries();
  }, [fetchSummary, fetchSeries]);

  useEffect(() => {
    void fetchWeek();
  }, [fetchWeek]);

  useEffect(() => {
    void fetchUpcoming();
    void fetchHelperStatus();
  }, [fetchUpcoming, fetchHelperStatus]);

  const upcomingSections = useMemo(() => {
    const today = iso(new Date());
    const deadlines = upcoming.filter((e) => e.kind === "deadline");
    const overdue = deadlines.filter((e) => (e.dueOn ?? e.date) < today);
    const dueSoon = deadlines.filter((e) => {
      const d = e.dueOn ?? e.date;
      const diff = Math.round((new Date(`${d}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime()) / 86400000);
      return diff >= 0 && diff <= 3;
    });
    // A recurring item emits the same warning on every occurrence. Show it once.
    const seen = new Set<string>();
    const warnings = upcoming
      .flatMap((e) => (e.warnings ?? []).map((w) => ({ title: e.title, warning: w })))
      .filter((w) => {
        const key = `${w.title}:${w.warning}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    return { overdue, dueSoon, warnings };
  }, [upcoming]);

  if (isLoading && !summary && days.length === 0) {
    return <PageLoader text="Loading dashboard..." />;
  }

  if (loadFailed && !summary) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Failed to load dashboard data</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() => {
            setIsLoading(true);
            void fetchAll();
          }}
        >
          Try again
        </Button>
      </div>
    );
  }

  const weekLabel = `${iso(weekStart)} to ${iso(addDays(weekStart, 6))}`;
  const goWeek = (weeks: number) => {
    const next = addDays(weekStart, weeks * 7);
    setWeekStart(next);
    setSelectedDate(iso(next));
  };
  const retry = () => {
    setIsLoading(true);
    void fetchAll();
  };
  const anyFailure = Object.values(failures).some(Boolean);

  return (
    <div className="font-sans">
      <header className="mb-6">
        <h1 className="font-display text-4xl text-foreground">Your week, at a glance</h1>
        <p className="mt-1 text-muted-foreground">
          {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          {helperText ? ` · ${helperText}` : ""}
        </p>
      </header>

      {anyFailure && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <p className="font-medium">Some dashboard data could not be loaded.</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {failures.schedule && (
              <li>Week schedules are unavailable. Affected days are marked unavailable.</li>
            )}
            {failures.range && <li>Fixed commitments and deadlines are unavailable.</li>}
            {failures.series && <li>Trend data is unavailable; the last loaded range is still shown.</li>}
            {failures.upcoming && <li>Upcoming items are unavailable; the last loaded list is still shown.</li>}
          </ul>
          <Button variant="outline" size="sm" className="mt-2" onClick={retry}>
            Retry
          </Button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <PlanHealthRail
          summary={summary}
          rangeDays={rangeDays}
          onRangeChange={setRangeDays}
        />

        <div className="min-w-0 space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              aria-label="Previous week"
              onClick={() => goWeek(-1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">{weekLabel}</span>
            <Button
              variant="outline"
              size="sm"
              aria-label="Next week"
              onClick={() => goWeek(1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setWeekStart(mondayOf(new Date()));
                setSelectedDate(iso(new Date()));
              }}
            >
              Today
            </Button>
            <Button
              size="sm"
              className="ml-auto"
              onClick={() => setWeekPlanOpen(true)}
            >
              <CalendarRange className="h-4 w-4" aria-hidden="true" />
              Plan my week
            </Button>
          </div>

          <WeekCalendar
            weekStart={weekStart}
            days={days}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
            onOpenBlock={setSelectedBlock}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <LifeMap objectives={objectives} unavailable={failures.schedule} />
            <InsightTiles series={series} days={rangeDays} failed={failures.series} />
          </div>

          <section aria-label="Upcoming" className="dashboard-card">
            <h2 className="text-sm font-semibold">Upcoming</h2>
            <div className="mt-3 space-y-4">
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Overdue
                </h3>
                {upcomingSections.overdue.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {failures.upcoming ? "Upcoming items could not be loaded." : "Nothing overdue."}
                  </p>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {upcomingSections.overdue.map((d) => (
                      <li key={d.itemId} className="text-sm">
                        <span className="status-badge status-badge-destructive">Overdue</span>{" "}
                        {d.title} · due {d.dueOn ?? d.date}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Due soon
                </h3>
                {upcomingSections.dueSoon.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {failures.upcoming
                      ? "Upcoming items could not be loaded."
                      : "Nothing due in the next 3 days."}
                  </p>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {upcomingSections.dueSoon.map((d) => (
                      <li key={d.itemId} className="text-sm">
                        {d.title} · due {d.dueOn ?? d.date}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Next 14 days
                </h3>
                {upcoming.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {failures.upcoming
                      ? "Upcoming items could not be loaded."
                      : "No fixed commitments or deadlines in the next two weeks."}
                  </p>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {upcoming
                      .filter((e) => e.date >= iso(new Date()))
                      .slice(0, 12)
                      .map((e) => (
                        <li key={`${e.itemId}-${e.date}`} className="text-sm">
                          {e.kind === "deadline" ? (
                            <>
                              {e.title} · due {e.dueOn ?? e.date}
                            </>
                          ) : (
                            <>
                              {e.title} · {e.date} {e.startTime}–{e.endTime}
                            </>
                          )}
                          {e.isPrivate ? " · Private" : ""}
                        </li>
                      ))}
                  </ul>
                )}
              </div>
              {upcomingSections.warnings.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Heads up
                  </h3>
                  <ul className="mt-1 space-y-1">
                    {upcomingSections.warnings.map((w, i) => (
                      <li key={i} className="text-sm text-amber-800 dark:text-amber-200">
                        {w.title}: {w.warning}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      {selectedBlock && (
        <DayDetailPanel
          block={selectedBlock}
          onClose={() => setSelectedBlock(null)}
          onChanged={() => void fetchAll()}
          onOpenBlock={setSelectedBlock}
        />
      )}

      <WeekPlanDialog
        open={weekPlanOpen}
        onOpenChange={setWeekPlanOpen}
        weekStart={iso(weekStart)}
        onApplied={() => void fetchAll()}
      />

      <HelperOrb onChanged={() => void fetchAll()} />
    </div>
  );
}
