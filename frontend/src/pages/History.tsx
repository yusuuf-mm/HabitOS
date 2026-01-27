import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Clock, AlertCircle, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/Loader";
import { apiClient } from "@/services/apiClient";
import { cn } from "@/lib/utils";
import type { OptimizationRun, OptimizationStatus, SolverStatus } from "@/types";

const STATUS_CONFIG: Record<
  OptimizationStatus,
  { icon: typeof CheckCircle2; label: string; className: string }
> = {
  pending: { icon: Clock, label: "Pending", className: "status-badge-info" },
  running: { icon: Clock, label: "Running", className: "status-badge-info" },
  completed: { icon: CheckCircle2, label: "Completed", className: "status-badge-success" },
  failed: { icon: XCircle, label: "Failed", className: "status-badge-destructive" },
};

const SOLVER_CONFIG: Record<SolverStatus, { label: string; className: string }> = {
  optimal: { label: "Optimal", className: "bg-success/10 text-success" },
  feasible: { label: "Feasible", className: "bg-info/10 text-info" },
  infeasible: { label: "Infeasible", className: "bg-destructive/10 text-destructive" },
  unbounded: { label: "Unbounded", className: "bg-warning/10 text-warning" },
  timeout: { label: "Timeout", className: "bg-warning/10 text-warning" },
};

export default function History() {
  const [runs, setRuns] = useState<OptimizationRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<OptimizationRun | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await apiClient.optimization.getOptimizationHistory();
        setRuns(response.data);
      } catch (error) {
        console.error("Failed to fetch history:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, []);

  if (isLoading) {
    return <PageLoader text="Loading history..." />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Optimization History</h1>
        <p className="page-subtitle">
          View past optimization runs and their results
        </p>
      </div>

      {/* Summary Stats */}
      <div className="flex flex-wrap gap-4 rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Total Runs:</span>
          <span className="font-medium text-foreground">{runs.length}</span>
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Successful:</span>
          <span className="font-medium text-success">
            {runs.filter((r) => r.status === "completed").length}
          </span>
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Failed:</span>
          <span className="font-medium text-destructive">
            {runs.filter((r) => r.status === "failed").length}
          </span>
        </div>
      </div>

      {/* History List */}
      {runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
          <AlertCircle className="mb-3 h-8 w-8 text-muted-foreground" />
          <p className="text-muted-foreground">No optimization runs yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Run your first optimization to see history here
          </p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Run List */}
          <div className="space-y-3 lg:col-span-2">
            {runs.map((run) => {
              const statusConfig = STATUS_CONFIG[run.status];
              const StatusIcon = statusConfig.icon;
              const isSelected = selectedRun?.id === run.id;

              return (
                <button
                  key={run.id}
                  onClick={() => setSelectedRun(run)}
                  className={cn(
                    "w-full text-left dashboard-card flex items-center justify-between gap-4 p-4 transition-all hover:shadow-md",
                    isSelected && "ring-2 ring-accent"
                  )}
                >
                  <div className="flex items-center gap-4">
                    <StatusIcon
                      className={cn(
                        "h-5 w-5 shrink-0",
                        run.status === "completed" && "text-success",
                        run.status === "failed" && "text-destructive",
                        run.status === "pending" && "text-info",
                        run.status === "running" && "text-info"
                      )}
                    />
                    <div>
                      <p className="font-mono text-sm font-medium text-foreground">
                        {run.id.slice(0, 16)}...
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(run.createdAt).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {run.status === "completed" && (
                      <div className="flex items-center gap-1 text-sm">
                        <TrendingUp className="h-4 w-4 text-success" />
                        <span className="font-medium">
                          {(run.totalScore * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                    <span className={cn("status-badge", statusConfig.className)}>
                      {statusConfig.label}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Selected Run Details */}
          <div className="lg:col-span-1">
            {selectedRun ? (
              <div className="dashboard-card sticky top-6 space-y-4">
                <h3 className="font-medium text-foreground">Run Details</h3>

                {/* Basic Info */}
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <span className={cn("status-badge", STATUS_CONFIG[selectedRun.status].className)}>
                      {STATUS_CONFIG[selectedRun.status].label}
                    </span>
                  </div>

                  {selectedRun.solverStatus && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Solver</span>
                      <Badge
                        variant="secondary"
                        className={SOLVER_CONFIG[selectedRun.solverStatus].className}
                      >
                        {SOLVER_CONFIG[selectedRun.solverStatus].label}
                      </Badge>
                    </div>
                  )}

                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Score</span>
                    <span className="font-medium text-foreground">
                      {(selectedRun.totalScore * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Execution Time</span>
                    <span className="text-foreground">{selectedRun.executionTimeMs}ms</span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Constraints</span>
                    <span
                      className={cn(
                        "font-medium",
                        selectedRun.constraintsSatisfied === selectedRun.constraintsTotal
                          ? "text-success"
                          : "text-warning"
                      )}
                    >
                      {selectedRun.constraintsSatisfied}/{selectedRun.constraintsTotal}
                    </span>
                  </div>
                </div>

                {/* Objective Contributions */}
                {selectedRun.objectiveContributions.length > 0 && (
                  <div className="space-y-2 border-t border-border pt-4">
                    <h4 className="text-sm font-medium text-foreground">
                      Objective Contributions
                    </h4>
                    <div className="space-y-2">
                      {selectedRun.objectiveContributions.map((obj) => (
                        <div
                          key={obj.objectiveId}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="text-muted-foreground">
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

                {/* Timestamps */}
                <div className="space-y-2 border-t border-border pt-4 text-xs text-muted-foreground">
                  <p>Created: {new Date(selectedRun.createdAt).toLocaleString()}</p>
                  {selectedRun.completedAt && (
                    <p>Completed: {new Date(selectedRun.completedAt).toLocaleString()}</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="dashboard-card flex items-center justify-center py-12">
                <p className="text-muted-foreground">
                  Select a run to view details
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
