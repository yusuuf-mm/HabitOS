import { Clock, CheckCircle2, Circle, Timer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DailySchedule, TimeSlot, ScheduledBehavior } from "@/types";

interface ScheduleViewProps {
  schedule: DailySchedule;
  onMarkComplete?: (scheduledBehaviorId: string) => void;
  onMarkIncomplete?: (scheduledBehaviorId: string) => void;
}

const TIME_SLOT_CONFIG: Record<TimeSlot, { label: string; hours: string }> = {
  early_morning: { label: "Early Morning", hours: "5:00 - 7:00" },
  morning: { label: "Morning", hours: "7:00 - 12:00" },
  midday: { label: "Midday", hours: "12:00 - 14:00" },
  afternoon: { label: "Afternoon", hours: "14:00 - 17:00" },
  evening: { label: "Evening", hours: "17:00 - 21:00" },
  night: { label: "Night", hours: "21:00+" },
};

const SLOT_ORDER: TimeSlot[] = [
  "early_morning",
  "morning",
  "midday",
  "afternoon",
  "evening",
  "night",
];

interface GroupedSchedule {
  slot: TimeSlot;
  behaviors: ScheduledBehavior[];
}

function groupByTimeSlot(behaviors: ScheduledBehavior[]): GroupedSchedule[] {
  const groups: Record<TimeSlot, ScheduledBehavior[]> = {
    early_morning: [],
    morning: [],
    midday: [],
    afternoon: [],
    evening: [],
    night: [],
  };

  behaviors.forEach((b) => {
    groups[b.timeSlot].push(b);
  });

  return SLOT_ORDER.map((slot) => ({
    slot,
    behaviors: groups[slot].sort((a, b) => a.startTime.localeCompare(b.startTime)),
  })).filter((g) => g.behaviors.length > 0);
}

export function ScheduleView({
  schedule,
  onMarkComplete,
  onMarkIncomplete,
}: ScheduleViewProps) {
  const groupedSchedule = groupByTimeSlot(schedule.scheduledBehaviors);
  const completedCount = schedule.scheduledBehaviors.filter((b) => b.isCompleted).length;
  const totalCount = schedule.scheduledBehaviors.length;

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Total: <span className="font-medium text-foreground">{schedule.totalDuration} min</span>
          </span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <span className="text-sm text-muted-foreground">
            Completed:{" "}
            <span className="font-medium text-foreground">
              {completedCount}/{totalCount}
            </span>
          </span>
        </div>
        <div className="h-4 w-px bg-border" />
        <Badge variant="outline" className="text-accent border-accent/30">
          {new Date(schedule.date).toLocaleDateString("en-US", {
            weekday: "long",
            month: "short",
            day: "numeric",
          })}
        </Badge>
      </div>

      {/* Time Slot Groups */}
      {groupedSchedule.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
          <p className="text-muted-foreground">No scheduled behaviors</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Run optimization to generate a schedule
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {groupedSchedule.map((group) => (
            <div key={group.slot} className="space-y-3">
              {/* Slot Header */}
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10">
                  <Timer className="h-4 w-4 text-accent" />
                </div>
                <div>
                  <h3 className="font-medium text-foreground">
                    {TIME_SLOT_CONFIG[group.slot].label}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {TIME_SLOT_CONFIG[group.slot].hours}
                  </p>
                </div>
              </div>

              {/* Behaviors */}
              <div className="ml-4 border-l-2 border-border pl-6 space-y-3">
                {group.behaviors.map((sb) => (
                  <div
                    key={sb.id}
                    className={cn(
                      "schedule-card flex items-center justify-between gap-4",
                      sb.isCompleted && "bg-success/5 border-success/20"
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <button
                        onClick={() =>
                          sb.isCompleted
                            ? onMarkIncomplete?.(sb.id)
                            : onMarkComplete?.(sb.id)
                        }
                        className="shrink-0 transition-colors"
                      >
                        {sb.isCompleted ? (
                          <CheckCircle2 className="h-5 w-5 text-success" />
                        ) : (
                          <Circle className="h-5 w-5 text-muted-foreground hover:text-accent" />
                        )}
                      </button>

                      <div className="min-w-0">
                        <p
                          className={cn(
                            "font-medium truncate",
                            sb.isCompleted
                              ? "text-muted-foreground line-through"
                              : "text-foreground"
                          )}
                        >
                          {sb.behavior.name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {sb.startTime} - {sb.endTime} ({sb.duration} min)
                        </p>
                      </div>
                    </div>

                    <Badge variant="secondary" className="shrink-0 capitalize">
                      {sb.behavior.category}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Objective Scores */}
      {schedule.objectiveScores.length > 0 && (
        <div className="rounded-lg border border-border p-4 space-y-3">
          <h4 className="text-sm font-medium text-foreground">
            Today's Objective Progress
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {schedule.objectiveScores.map((obj) => (
              <div
                key={obj.objectiveId}
                className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2"
              >
                <span className="text-sm text-muted-foreground">
                  {obj.objectiveName}
                </span>
                <span className="font-medium text-accent">
                  {(obj.contribution * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
