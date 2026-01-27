import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Target,
  CheckCircle2,
  Zap,
  TrendingUp,
  ArrowRight,
  Clock,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/StatsCards";
import { PageLoader } from "@/components/Loader";
import { apiClient } from "@/services/apiClient";
import type { DashboardSummary } from "@/types";

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await apiClient.analytics.getDashboardSummary();
        setSummary(response.data);
      } catch (error) {
        console.error("Failed to fetch dashboard summary:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  if (isLoading) {
    return <PageLoader text="Loading dashboard..." />;
  }

  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Failed to load dashboard data</p>
      </div>
    );
  }

  const stats = [
    {
      title: "Total Behaviors",
      value: summary.stats.totalBehaviors,
      subtitle: `${summary.stats.activeBehaviors} active`,
      icon: Target,
      accentColor: "accent" as const,
    },
    {
      title: "Optimization Runs",
      value: summary.stats.totalOptimizationRuns,
      subtitle: "All time",
      icon: Sparkles,
      accentColor: "info" as const,
    },
    {
      title: "Completion Rate",
      value: `${(summary.stats.completionRate * 100).toFixed(0)}%`,
      subtitle: "This week",
      icon: CheckCircle2,
      trend: "up" as const,
      trendValue: "+5%",
      accentColor: "success" as const,
    },
    {
      title: "Current Streak",
      value: `${summary.stats.streakDays} days`,
      subtitle: "Keep it up!",
      icon: Zap,
      accentColor: "warning" as const,
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">
          Welcome back! Here's an overview of your behavioral optimization.
        </p>
      </div>

      {/* Stats Cards */}
      <StatsCards stats={stats} />

      {/* Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Today's Schedule */}
        <div className="dashboard-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-foreground">Today's Schedule</h2>
            <Link to="/schedule">
              <Button variant="ghost" size="sm" className="gap-1 text-accent">
                View all
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {summary.todaySchedule.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-muted-foreground">No schedule for today</p>
              <Link to="/optimization">
                <Button variant="outline" size="sm" className="mt-3">
                  Run Optimization
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {summary.todaySchedule.slice(0, 5).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 rounded-lg border border-border p-3"
                >
                  {item.isCompleted ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
                  ) : (
                    <Clock className="h-5 w-5 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {item.behaviorName}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {item.startTime} • {item.timeSlot.replace("_", " ")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Behaviors */}
        <div className="dashboard-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-foreground">Recent Behaviors</h2>
            <Link to="/behaviors">
              <Button variant="ghost" size="sm" className="gap-1 text-accent">
                View all
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {summary.recentBehaviors.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-muted-foreground">No behaviors created yet</p>
              <Link to="/behaviors">
                <Button variant="outline" size="sm" className="mt-3">
                  Create Behavior
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {summary.recentBehaviors.map((behavior) => (
                <div
                  key={behavior.id}
                  className="flex items-center justify-between rounded-lg border border-border p-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {behavior.name}
                    </p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {behavior.category}
                    </p>
                  </div>
                  <span
                    className={`status-badge ${
                      behavior.isActive
                        ? "status-badge-success"
                        : "status-badge-warning"
                    }`}
                  >
                    {behavior.isActive ? "Active" : "Inactive"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Optimizations */}
        <div className="dashboard-card space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-medium text-foreground">Recent Optimizations</h2>
            <Link to="/history">
              <Button variant="ghost" size="sm" className="gap-1 text-accent">
                View history
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {summary.recentOptimizations.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-muted-foreground">No optimization runs yet</p>
              <Link to="/optimization">
                <Button variant="outline" size="sm" className="mt-3">
                  Run First Optimization
                </Button>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recentOptimizations.map((opt) => (
                    <tr key={opt.id}>
                      <td className="font-mono text-sm">{opt.id.slice(0, 12)}...</td>
                      <td>
                        <span
                          className={`status-badge ${
                            opt.status === "completed"
                              ? "status-badge-success"
                              : opt.status === "failed"
                              ? "status-badge-destructive"
                              : "status-badge-info"
                          }`}
                        >
                          {opt.status}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center gap-1.5">
                          <TrendingUp className="h-4 w-4 text-success" />
                          <span>{(opt.score * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="text-muted-foreground">
                        {new Date(opt.createdAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
