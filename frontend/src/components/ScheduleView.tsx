import { useMemo } from "react";
import { Clock, CheckCircle2, Circle, Timer, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DailySchedule, ScheduledBehavior } from "@/types";
import type { HelperDayItem } from "@/types/helper";

interface ScheduleViewProps {
  schedule: DailySchedule;
  onMarkComplete?: (scheduledBehaviorId: string) => void;
  onMarkIncomplete?: (scheduledBehaviorId: string) => void;
  fixedItems?: HelperDayItem[];
}

const MINUTES_PER_PERIOD = 15;
const PERIODS_PER_DAY = 96;
const HOURS_IN_DAY = 24;

function timeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

function minutesToTime(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function minutesToPeriod(mins: number): number {
  return Math.floor(mins / MINUTES_PER_PERIOD);
}

interface MergedBlock {
  behaviorName: string;
  category: string;
  startPeriod: number;
  endPeriod: number;
  startMin: number;
  endMin: number;
  duration: number;
  isCompleted: boolean;
  id: string;
}

function mergeConsecutive(behaviors: ScheduledBehavior[]): MergedBlock[] {
  const sorted = [...behaviors].sort(
    (a, b) => timeToMinutes(a.startTime) - timeToMinutes(b.startTime),
  );

  const blocks: MergedBlock[] = [];

  for (const sb of sorted) {
    const startMin = timeToMinutes(sb.startTime);
    const endMin = timeToMinutes(sb.endTime);
    const startPeriod = minutesToPeriod(startMin);

    blocks.push({
      behaviorName: sb.behavior.name,
      category: sb.behavior.category,
      startPeriod,
      endPeriod: minutesToPeriod(endMin) - 1,
      startMin,
      endMin,
      duration: sb.duration,
      isCompleted: sb.isCompleted,
      id: sb.id,
    });
  }

  return blocks;
}

interface FixedBlock {
  itemId: string;
  title: string;
  isPrivate: boolean;
  startTime: string;
  endTime: string;
  startMin: number;
  endMin: number;
}

function TimelineTrack({ blocks, fixed }: { blocks: MergedBlock[]; fixed?: FixedBlock[] }) {
  const fixedBlocks = fixed ?? [];
  const totalMinutes = HOURS_IN_DAY * 60;

  return (
    <div className="relative rounded-xl border border-border/40 bg-muted/20 p-5 overflow-hidden">
      {/* Hour markers */}
      <div className="relative h-10 flex items-end mb-2">
        {Array.from({ length: HOURS_IN_DAY + 1 }, (_, i) => {
          const isMain = i % 6 === 0;
          return (
            <div
              key={i}
              className="absolute bottom-0"
              style={{ left: `${(i / HOURS_IN_DAY) * 100}%` }}
            >
              <div
                className={cn(
                  "w-px",
                  isMain ? "h-4 bg-foreground/20" : "h-2 bg-foreground/8",
                )}
              />
              {isMain && (
                <span className="absolute -bottom-5 -translate-x-1/2 text-[9px] font-mono text-muted-foreground/50">
                  {i.toString().padStart(2, "0")}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Behavior blocks */}
      <div className="relative h-12 mt-4">
        {blocks.map((block) => {
          const left = (block.startMin / totalMinutes) * 100;
          const width = ((block.endMin - block.startMin) / totalMinutes) * 100;

          return (
            <div
              key={block.id}
              className={cn(
                "absolute top-0 h-full rounded-lg flex items-center justify-center px-2 overflow-hidden",
                "transition-all duration-300 cursor-default group",
                block.isCompleted
                  ? "bg-success/15 border border-success/25"
                  : "bg-accent/10 border border-accent/20",
              )}
              style={{ left: `${left}%`, width: `${Math.max(width, 1.5)}%` }}
              title={`${block.behaviorName}: ${block.startTime || minutesToTime(block.startMin)} - ${block.endTime || minutesToTime(block.endMin)}`}
            >
              {width > 4 && (
                <span
                  className={cn(
                    "text-[10px] font-medium truncate",
                    block.isCompleted ? "text-success/80" : "text-accent/80",
                  )}
                >
                  {block.behaviorName}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {fixedBlocks.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Fixed
          </p>
          <div className="relative h-12">
            {fixedBlocks.map((block) => {
              const left = (block.startMin / totalMinutes) * 100;
              const width = ((block.endMin - block.startMin) / totalMinutes) * 100;
              return (
                <div
                  key={block.itemId}
                  className="absolute top-0 h-full rounded-lg border border-dashed border-zinc-400 bg-zinc-100 px-2 flex items-center gap-1 overflow-hidden dark:border-zinc-500 dark:bg-zinc-800/60"
                  style={{ left: `${left}%`, width: `${Math.max(width, 1.5)}%` }}
                  title={`${block.title}: ${block.startTime} - ${block.endTime}`}
                >
                  {block.isPrivate && (
                    <span className="shrink-0 flex items-center gap-1">
                      <Lock className="h-3 w-3 text-muted-foreground" />
                      <span className="sr-only">private</span>
                    </span>
                  )}
                  {width > 4 && (
                    <span className="text-[10px] font-medium truncate text-foreground">
                      {block.title} · {block.startTime}–{block.endTime}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <ul className="mt-2 space-y-1">
            {fixedBlocks.map((block) => (
              <li
                key={`caption-${block.itemId}`}
                className="text-xs text-muted-foreground"
              >
                {block.title} · {block.startTime}–{block.endTime}
                {block.isPrivate ? " · Private" : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Bottom axis labels */}
      <div className="flex justify-between mt-6 px-1">
        <span className="text-[10px] font-mono text-muted-foreground/40">00:00</span>
        <span className="text-[10px] font-mono text-muted-foreground/40">06:00</span>
        <span className="text-[10px] font-mono text-muted-foreground/40">12:00</span>
        <span className="text-[10px] font-mono text-muted-foreground/40">18:00</span>
        <span className="text-[10px] font-mono text-muted-foreground/40">24:00</span>
      </div>
    </div>
  );
}

export function ScheduleView({
  schedule,
  onMarkComplete,
  onMarkIncomplete,
  fixedItems,
}: ScheduleViewProps) {
  const fixed = fixedItems ?? [];
  const deadlines = fixed.filter((i) => i.kind === "deadline");
  const commitments = fixed.filter((i) => i.kind === "commitment");
  const fixedBlocks: FixedBlock[] = commitments
    .filter((i) => i.startTime && i.endTime)
    .map((i) => ({
      itemId: i.itemId,
      title: i.title,
      isPrivate: i.isPrivate,
      startTime: i.startTime as string,
      endTime: i.endTime as string,
      startMin: timeToMinutes(i.startTime as string),
      endMin: timeToMinutes(i.endTime as string),
    }));
  const blocks = useMemo(
    () => mergeConsecutive(schedule.scheduledBehaviors),
    [schedule.scheduledBehaviors],
  );

  const completedCount = schedule.scheduledBehaviors.filter(
    (b) => b.isCompleted,
  ).length;
  const totalCount = schedule.scheduledBehaviors.length;

  return (
    <div className="space-y-8">
      {/* Header Stats */}
      <div className="flex flex-wrap items-center gap-5 rounded-xl border border-border/40 bg-muted/20 p-5">
        <div className="flex items-center gap-2.5">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Total:{" "}
            <span className="font-medium text-foreground">
              {schedule.totalDuration} min
            </span>
          </span>
        </div>
        <div className="h-4 w-px bg-border/50" />
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <span className="text-sm text-muted-foreground">
            Completed:{" "}
            <span className="font-medium text-foreground">
              {completedCount}/{totalCount}
            </span>
          </span>
        </div>
        <div className="h-4 w-px bg-border/50" />
        <Badge
          variant="outline"
          className="text-accent border-accent/20 bg-accent/5"
        >
          {new Date(schedule.date).toLocaleDateString("en-US", {
            weekday: "long",
            month: "short",
            day: "numeric",
          })}
        </Badge>
      </div>

      {/* Deadline chips for today */}
      {deadlines.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {deadlines.map((d) => (
            <span
              key={d.itemId}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground"
            >
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              Deadline today: {d.title}
              {d.isPrivate && (
                <span className="inline-flex items-center gap-1">
                  <Lock className="h-3 w-3 text-muted-foreground" />
                  <span className="sr-only">private</span>
                </span>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Timeline track */}
      {(blocks.length > 0 || fixedBlocks.length > 0) && (
        <TimelineTrack blocks={blocks} fixed={fixedBlocks} />
      )}

      {/* Block list */}
      {blocks.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/40 py-16 text-center">
          <Timer className="h-8 w-8 text-muted-foreground/30 mb-3" />
          <p className="text-muted-foreground">No scheduled behaviors</p>
          <p className="mt-1 text-sm text-muted-foreground/60">
            Run optimization to generate a schedule
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {blocks.map((block) => (
            <div
              key={block.id}
              className={cn(
                "schedule-card flex items-center justify-between gap-4",
                block.isCompleted && "bg-success/[0.03] border-success/15",
              )}
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <button
                  onClick={() =>
                    block.isCompleted
                      ? onMarkIncomplete?.(block.id)
                      : onMarkComplete?.(block.id)
                  }
                  className="shrink-0 transition-all duration-200 active:scale-90"
                >
                  {block.isCompleted ? (
                    <CheckCircle2 className="h-5 w-5 text-success" />
                  ) : (
                    <Circle className="h-5 w-5 text-muted-foreground/40 hover:text-accent" />
                  )}
                </button>

                <div className="min-w-0">
                  <p
                    className={cn(
                      "font-medium truncate text-sm",
                      block.isCompleted
                        ? "text-muted-foreground line-through"
                        : "text-foreground",
                    )}
                  >
                    {block.behaviorName}
                  </p>
                  <p className="text-xs text-muted-foreground/60 font-mono">
                    {minutesToTime(block.startMin)} - {minutesToTime(block.endMin)}
                    <span className="ml-2 text-muted-foreground/40">
                      ({block.duration} min)
                    </span>
                  </p>
                </div>
              </div>

              <Badge
                variant="secondary"
                className="shrink-0 capitalize text-[10px] tracking-wider"
              >
                {block.category}
              </Badge>
            </div>
          ))}
        </div>
      )}

      {/* Objective Scores: these are shares of the run objective value,
          not weights or progress toward a goal. */}
      {schedule.objectiveScores.length > 0 && (
        <div className="rounded-xl border border-border/40 p-5 space-y-4">
          <h4 className="text-sm font-medium text-foreground">
            Today&apos;s Objective Value Share
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {schedule.objectiveScores.map((obj) => (
              <div
                key={obj.objectiveId}
                className="flex items-center justify-between rounded-lg bg-muted/30 px-4 py-2.5"
              >
                <span className="text-sm text-muted-foreground">
                  {obj.objectiveName}
                </span>
                <span className="font-mono text-sm font-medium text-accent">
                  {obj.percentage.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
