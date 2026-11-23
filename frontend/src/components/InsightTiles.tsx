import type { SeriesDay } from "@/types/dashboard";

interface InsightTilesProps {
  series: SeriesDay[];
  days: number;
  failed?: boolean;
}

function sparkline(points: number[]): string {
  if (points.length === 0) return "";
  const max = Math.max(...points, 1);
  const step = points.length > 1 ? 100 / (points.length - 1) : 0;
  return points
    .map((v, i) => `${(i * step).toFixed(1)},${(30 - (v / max) * 28).toFixed(1)}`)
    .join(" ");
}

export function InsightTiles({ series, days, failed = false }: InsightTilesProps) {
  // The headline is the total across the selected range; the sparkline shows
  // the daily shape. Mixing a "latest day" rate into a count label was wrong.
  const completedTotal = series.reduce((sum, d) => sum + (d.completed ?? 0), 0);
  const minutesTotal = series.reduce((sum, d) => sum + (d.plannedMinutes ?? 0), 0);
  const hasData = series.length > 0;
  const rangeLabel = `across ${days} days`;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="dashboard-card">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Sessions done
        </p>
        <p className="mt-1 text-3xl font-semibold">{hasData ? completedTotal : "—"}</p>
        {hasData ? (
          <svg viewBox="0 0 100 32" className="mt-2 h-8 w-full" aria-hidden="true">
            <polyline
              points={sparkline(series.map((d) => d.completed))}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-accent"
            />
          </svg>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            {failed ? "Trend data could not be loaded." : "No data yet"}
          </p>
        )}
        <p className="mt-1 text-[11px] text-muted-foreground">
          completed sessions, {rangeLabel} · daily sparkline
        </p>
      </div>
      <div className="dashboard-card">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Minutes planned
        </p>
        <p className="mt-1 text-3xl font-semibold">{hasData ? minutesTotal : "—"}</p>
        {hasData ? (
          <svg viewBox="0 0 100 32" className="mt-2 h-8 w-full" aria-hidden="true">
            <polyline
              points={sparkline(series.map((d) => d.plannedMinutes))}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-accent"
            />
          </svg>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            {failed ? "Trend data could not be loaded." : "No data yet"}
          </p>
        )}
        <p className="mt-1 text-[11px] text-muted-foreground">
          planned minutes, {rangeLabel} · daily sparkline
        </p>
      </div>
    </div>
  );
}
