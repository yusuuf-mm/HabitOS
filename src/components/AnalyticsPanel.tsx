import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { AnalyticsData } from "@/types";

interface AnalyticsPanelProps {
  data: AnalyticsData;
}

export function AnalyticsPanel({ data }: AnalyticsPanelProps) {
  const trendIcons = {
    up: TrendingUp,
    down: TrendingDown,
    stable: Minus,
  };

  const trendColors = {
    up: "text-success",
    down: "text-destructive",
    stable: "text-muted-foreground",
  };

  // Calculate average completion rate
  const avgCompletionRate =
    data.behaviorCompletions.reduce((acc, day) => {
      return acc + (day.scheduled > 0 ? day.completed / day.scheduled : 0);
    }, 0) / data.behaviorCompletions.length;

  return (
    <div className="space-y-6">
      {/* Completion Trend */}
      <div className="dashboard-card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-foreground">Completion Rate</h3>
          <span className="text-2xl font-semibold text-accent">
            {(avgCompletionRate * 100).toFixed(0)}%
          </span>
        </div>

        <div className="space-y-2">
          {data.behaviorCompletions.slice(-7).map((day, i) => {
            const rate = day.scheduled > 0 ? (day.completed / day.scheduled) * 100 : 0;
            return (
              <div key={day.date} className="flex items-center gap-3">
                <span className="w-16 text-xs text-muted-foreground">
                  {new Date(day.date).toLocaleDateString("en-US", {
                    weekday: "short",
                  })}
                </span>
                <div className="flex-1">
                  <Progress value={rate} className="h-2" />
                </div>
                <span className="w-12 text-right text-xs font-medium text-foreground">
                  {day.completed}/{day.scheduled}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Objective Progress */}
      <div className="dashboard-card space-y-4">
        <h3 className="font-medium text-foreground">Objective Progress</h3>

        <div className="space-y-4">
          {data.objectiveProgress.map((obj) => {
            const TrendIcon = trendIcons[obj.trend];
            return (
              <div key={obj.objectiveName} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    {obj.objectiveName}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <TrendIcon
                      className={cn("h-4 w-4", trendColors[obj.trend])}
                    />
                    <span className="font-medium text-foreground">
                      {(obj.progress * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <Progress value={obj.progress * 100} className="h-2" />
              </div>
            );
          })}
        </div>
      </div>

      {/* Category Distribution */}
      <div className="dashboard-card space-y-4">
        <h3 className="font-medium text-foreground">Category Distribution</h3>

        <div className="flex flex-wrap gap-2">
          {data.categoryDistribution.map((cat) => (
            <div
              key={cat.category}
              className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2"
            >
              <span className="text-sm capitalize text-muted-foreground">
                {cat.category}
              </span>
              <span className="font-medium text-foreground">
                {cat.percentage}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Energy Usage */}
      <div className="dashboard-card space-y-4">
        <h3 className="font-medium text-foreground">Energy Budget</h3>

        <div className="space-y-2">
          {data.energyUsage.slice(-5).map((day) => {
            const percentage = (day.energySpent / day.energyBudget) * 100;
            const isOver = percentage > 100;
            return (
              <div key={day.date} className="flex items-center gap-3">
                <span className="w-16 text-xs text-muted-foreground">
                  {new Date(day.date).toLocaleDateString("en-US", {
                    weekday: "short",
                  })}
                </span>
                <div className="flex-1">
                  <div className="relative h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "absolute left-0 top-0 h-full rounded-full transition-all",
                        isOver ? "bg-warning" : "bg-accent"
                      )}
                      style={{ width: `${Math.min(percentage, 100)}%` }}
                    />
                  </div>
                </div>
                <span
                  className={cn(
                    "w-16 text-right text-xs font-medium",
                    isOver ? "text-warning" : "text-foreground"
                  )}
                >
                  {day.energySpent}/{day.energyBudget}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
