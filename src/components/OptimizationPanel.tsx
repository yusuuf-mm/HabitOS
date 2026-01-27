import { useState } from "react";
import { Play, CheckCircle, AlertCircle, Clock, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { OptimizationRun, OptimizationResult, SolverStatus } from "@/types";

interface OptimizationPanelProps {
  lastRun?: OptimizationRun;
  onRunOptimization: () => Promise<OptimizationResult>;
}

const solverStatusConfig: Record<
  SolverStatus,
  { icon: typeof CheckCircle; label: string; className: string }
> = {
  optimal: {
    icon: CheckCircle,
    label: "Optimal Solution",
    className: "text-success",
  },
  feasible: {
    icon: CheckCircle,
    label: "Feasible Solution",
    className: "text-info",
  },
  infeasible: {
    icon: AlertCircle,
    label: "No Feasible Solution",
    className: "text-destructive",
  },
  unbounded: {
    icon: AlertCircle,
    label: "Unbounded",
    className: "text-warning",
  },
  timeout: {
    icon: Clock,
    label: "Timeout",
    className: "text-warning",
  },
};

export function OptimizationPanel({
  lastRun,
  onRunOptimization,
}: OptimizationPanelProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [currentRun, setCurrentRun] = useState<OptimizationRun | undefined>(lastRun);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setIsRunning(true);
    setError(null);

    try {
      const result = await onRunOptimization();
      setCurrentRun(result.run);
    } catch (err: unknown) {
      const error = err as { message?: string };
      setError(error.message || "Optimization failed");
    } finally {
      setIsRunning(false);
    }
  };

  const displayRun = currentRun || lastRun;

  return (
    <div className="space-y-6">
      {/* Run Button */}
      <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-muted/30 p-6">
        <div className="text-center">
          <h3 className="font-medium text-foreground">Optimization Engine</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Generate an optimized schedule based on your behaviors and constraints
          </p>
        </div>

        <Button
          onClick={handleRun}
          disabled={isRunning}
          size="lg"
          className="gap-2 bg-accent text-accent-foreground hover:bg-accent/90"
        >
          {isRunning ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Running Optimization...
            </>
          ) : (
            <>
              <Play className="h-5 w-5" />
              Run Optimization
            </>
          )}
        </Button>

        {isRunning && (
          <div className="w-full max-w-xs space-y-2">
            <Progress value={undefined} className="h-2 animate-pulse" />
            <p className="text-center text-xs text-muted-foreground">
              Analyzing behaviors and computing optimal schedule...
            </p>
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-medium">Optimization Failed</p>
            <p className="text-sm opacity-90">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {displayRun && !isRunning && (
        <div className="space-y-4 animate-fade-up">
          {/* Status Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {displayRun.solverStatus && (() => {
                const config = solverStatusConfig[displayRun.solverStatus];
                const Icon = config.icon;
                return (
                  <>
                    <Icon className={cn("h-5 w-5", config.className)} />
                    <span className={cn("font-medium", config.className)}>
                      {config.label}
                    </span>
                  </>
                );
              })()}
            </div>
            <span className="text-sm text-muted-foreground">
              {displayRun.executionTimeMs}ms
            </span>
          </div>

          {/* Score */}
          <div className="rounded-lg border border-border p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total Score</span>
              <span className="text-2xl font-semibold text-foreground">
                {(displayRun.totalScore * 100).toFixed(1)}%
              </span>
            </div>
            <Progress
              value={displayRun.totalScore * 100}
              className="mt-3 h-2"
            />
          </div>

          {/* Objective Contributions */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground">
              Objective Contributions
            </h4>
            <div className="space-y-2">
              {displayRun.objectiveContributions.map((obj) => (
                <div key={obj.objectiveId} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      {obj.objectiveName}
                    </span>
                    <span className="font-medium text-foreground">
                      {(obj.contribution * 100).toFixed(0)}%
                    </span>
                  </div>
                  <Progress
                    value={obj.contribution * 100}
                    className="h-1.5"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Constraints */}
          <div className="flex items-center justify-between rounded-lg border border-border p-4">
            <span className="text-sm text-muted-foreground">
              Constraints Satisfied
            </span>
            <span
              className={cn(
                "font-medium",
                displayRun.constraintsSatisfied === displayRun.constraintsTotal
                  ? "text-success"
                  : "text-warning"
              )}
            >
              {displayRun.constraintsSatisfied} / {displayRun.constraintsTotal}
            </span>
          </div>

          {/* Timestamp */}
          <p className="text-center text-xs text-muted-foreground">
            Last run: {new Date(displayRun.createdAt).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
