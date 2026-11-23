import type { DashboardSummary } from "@/types";

interface PlanHealthRailProps {
  summary: DashboardSummary | null;
  rangeDays: number;
  onRangeChange: (days: number) => void;
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

export function PlanHealthRail({ summary, rangeDays, onRangeChange }: PlanHealthRailProps) {
  const stats = summary?.stats;
  const hasFinishedDays =
    stats !== null && stats !== undefined &&
    (stats.completionRate !== null || stats.completionRateVsFeasible !== null);
  return (
    <section
      aria-label="Plan health"
      className="rounded-xl bg-zinc-900 p-6 text-zinc-100"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
        Plan health
      </h2>
      <dl className="mt-5 space-y-4">
        <div>
          <dt
            className="text-xs text-zinc-400"
            title="Planned sessions completed in this range. Committed sessions are excluded from this rate and reported separately (docs/METRIC.md)."
          >
            Kept my plan
          </dt>
          <dd className="text-2xl font-semibold">{pct(stats?.completionRate)}</dd>
        </div>
        <div>
          <dt
            className="text-xs text-zinc-400"
            title="Completion against the day's feasible plan after released and system-dropped sessions are removed (docs/METRIC.md)."
          >
            Handled the day
          </dt>
          <dd className="text-2xl font-semibold">{pct(stats?.completionRateVsFeasible)}</dd>
        </div>
        <div>
          <dt
            className="text-xs text-zinc-400"
            title="Sessions withdrawn before they started, and sessions dropped by a later re-plan. Reported separately from the completion rate."
          >
            Released / dropped
          </dt>
          <dd className="text-sm">
            {stats ? `${stats.released} released · ${stats.systemDropped} dropped` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-400">Streak</dt>
          <dd className="text-2xl font-semibold">
            {stats ? `${stats.streakDays} days` : "—"}
          </dd>
        </div>
      </dl>
      {!hasFinishedDays && (
        <p className="mt-4 text-xs text-zinc-400">No finished days yet in this range.</p>
      )}
      <div className="mt-5 flex gap-2" role="group" aria-label="Health range">
        <button
          type="button"
          aria-pressed={rangeDays === 7}
          onClick={() => onRangeChange(7)}
          className={
            rangeDays === 7
              ? "rounded-full bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground"
              : "rounded-full bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300"
          }
        >
          7 days
        </button>
        <button
          type="button"
          aria-pressed={rangeDays === 30}
          onClick={() => onRangeChange(30)}
          className={
            rangeDays === 30
              ? "rounded-full bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground"
              : "rounded-full bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300"
          }
        >
          30 days
        </button>
      </div>
    </section>
  );
}
