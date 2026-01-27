import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Calendar, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OptimizationPanel } from "@/components/OptimizationPanel";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { PageLoader } from "@/components/Loader";
import { apiClient } from "@/services/apiClient";
import type { OptimizationRun, AnalyticsData, OptimizationResult } from "@/types";

export default function Optimization() {
  const [lastRun, setLastRun] = useState<OptimizationRun | undefined>();
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [historyRes, analyticsRes] = await Promise.all([
          apiClient.optimization.getOptimizationHistory(),
          apiClient.analytics.getAnalytics("7d"),
        ]);
        
        if (historyRes.data.length > 0) {
          setLastRun(historyRes.data[0]);
        }
        setAnalytics(analyticsRes.data);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleRunOptimization = async (): Promise<OptimizationResult> => {
    const response = await apiClient.optimization.runOptimization();
    setLastRun(response.data.run);
    return response.data;
  };

  if (isLoading) {
    return <PageLoader text="Loading optimization..." />;
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Optimization</h1>
        <p className="page-subtitle">
          Run the optimization engine to generate your optimal daily schedule
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid gap-8 lg:grid-cols-2">
        {/* Left Column - Optimization Panel */}
        <div className="space-y-6">
          <OptimizationPanel
            lastRun={lastRun}
            onRunOptimization={handleRunOptimization}
          />

          {/* Quick Actions */}
          <div className="flex flex-wrap gap-3">
            <Link to="/schedule">
              <Button variant="outline" className="gap-2">
                <Calendar className="h-4 w-4" />
                View Schedule
              </Button>
            </Link>
            <Link to="/history">
              <Button variant="ghost" className="gap-2">
                View History
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>

        {/* Right Column - Analytics */}
        <div>
          {analytics ? (
            <AnalyticsPanel data={analytics} />
          ) : (
            <div className="dashboard-card flex items-center justify-center py-12">
              <p className="text-muted-foreground">Analytics unavailable</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
