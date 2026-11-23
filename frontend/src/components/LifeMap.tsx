import { HabitOSLogo } from "@/components/HabitOSLogo";
import type { HeroObjective } from "@/types/dashboard";

interface LifeMapProps {
  objectives: HeroObjective[];
  unavailable?: boolean;
}

const VIEW_W = 340;
const CX = 170;
const CY = 140;
const ORBIT_R = 96;

export function LifeMap({ objectives, unavailable = false }: LifeMapProps) {
  const emptyMessage = unavailable
    ? "This week's plans could not be loaded."
    : objectives.length === 0
      ? "No objective scores were reported for this week's plans."
      : null;

  if (emptyMessage) {
    return (
      <section aria-label="Life map" className="dashboard-card">
        <h2 className="text-sm font-semibold">Life map</h2>
        <p className="mt-2 text-sm text-muted-foreground">{emptyMessage}</p>
      </section>
    );
  }

  return (
    <section aria-label="Life map" className="dashboard-card">
      <h2 className="text-sm font-semibold">Life map</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Each orb is an objective's share of the plans for this week, averaged across all seven days.
      </p>
      <div className="relative mx-auto mt-2 max-w-[340px]">
        <div
          aria-hidden="true"
          className="absolute inset-0 rounded-full bg-accent/10 blur-2xl motion-safe:animate-pulse"
        />
        <svg
          viewBox={`0 0 ${VIEW_W} 280`}
          className="relative w-full"
          role="img"
          aria-label="Objectives for this week"
        >
          <circle cx={CX} cy={CY} r={ORBIT_R} fill="none" stroke="currentColor" strokeWidth="1" className="text-border" />
          <circle cx={CX} cy={CY} r={34} fill="currentColor" className="text-accent" />
          <g transform={`translate(${CX - 12} ${CY - 12})`}>
            <HabitOSLogo width={24} height={24} className="text-accent-foreground" />
          </g>
          {objectives.map((obj, i) => {
            const angle = (i / objectives.length) * Math.PI * 2 - Math.PI / 2;
            const x = CX + ORBIT_R * Math.cos(angle);
            const y = CY + ORBIT_R * Math.sin(angle);
            const r = Math.max(10, Math.min(22, 10 + obj.share * 40));
            // Labels sit under the orb with a middle anchor, clamped inside the
            // viewBox so long objective names cannot be clipped at the edges.
            const labelX = Math.max(52, Math.min(VIEW_W - 52, x));
            const labelY = y < CY ? y - r - 7 : y + r + 13;
            return (
              <g key={obj.name}>
                <circle cx={x} cy={y} r={r} fill="currentColor" className="text-accent/70" />
                <text
                  x={labelX}
                  y={labelY}
                  textAnchor="middle"
                  className="fill-foreground text-[10px] font-medium"
                >
                  {obj.name} {Math.round(obj.share * 100)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {objectives.map((o) => (
          <li key={o.name} className="text-xs text-muted-foreground">
            {o.name}: {Math.round(o.share * 100)}%
          </li>
        ))}
      </ul>
    </section>
  );
}
