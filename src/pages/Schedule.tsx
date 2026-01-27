import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScheduleView } from "@/components/ScheduleView";
import { PageLoader } from "@/components/Loader";
import { apiClient } from "@/services/apiClient";
import { useToast } from "@/hooks/use-toast";
import type { DailySchedule } from "@/types";

export default function Schedule() {
  const { toast } = useToast();
  const [schedule, setSchedule] = useState<DailySchedule | null>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchSchedule();
  }, [currentDate]);

  const fetchSchedule = async () => {
    setIsLoading(true);
    try {
      const dateStr = currentDate.toISOString().split("T")[0];
      const response = await apiClient.schedule.getSchedule(dateStr);
      setSchedule(response.data);
    } catch (error) {
      console.error("Failed to fetch schedule:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrevDay = () => {
    setCurrentDate((prev) => {
      const newDate = new Date(prev);
      newDate.setDate(newDate.getDate() - 1);
      return newDate;
    });
  };

  const handleNextDay = () => {
    setCurrentDate((prev) => {
      const newDate = new Date(prev);
      newDate.setDate(newDate.getDate() + 1);
      return newDate;
    });
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  const handleMarkComplete = async (scheduledBehaviorId: string) => {
    try {
      await apiClient.schedule.markBehaviorComplete(scheduledBehaviorId);
      setSchedule((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          scheduledBehaviors: prev.scheduledBehaviors.map((sb) =>
            sb.id === scheduledBehaviorId
              ? { ...sb, isCompleted: true, completedAt: new Date().toISOString() }
              : sb
          ),
        };
      });
      toast({
        title: "Marked complete",
        description: "Great job! Keep up the momentum.",
      });
    } catch (error) {
      console.error("Failed to mark complete:", error);
    }
  };

  const handleMarkIncomplete = async (scheduledBehaviorId: string) => {
    try {
      await apiClient.schedule.markBehaviorIncomplete(scheduledBehaviorId);
      setSchedule((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          scheduledBehaviors: prev.scheduledBehaviors.map((sb) =>
            sb.id === scheduledBehaviorId
              ? { ...sb, isCompleted: false, completedAt: undefined }
              : sb
          ),
        };
      });
    } catch (error) {
      console.error("Failed to mark incomplete:", error);
    }
  };

  const isToday =
    currentDate.toISOString().split("T")[0] ===
    new Date().toISOString().split("T")[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Schedule</h1>
        <p className="page-subtitle">
          Your optimized daily schedule with time-blocked behaviors
        </p>
      </div>

      {/* Date Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={handlePrevDay}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={handleNextDay}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          {!isToday && (
            <Button variant="ghost" size="sm" onClick={handleToday}>
              Today
            </Button>
          )}
        </div>

        <div className="text-center">
          <p className="text-lg font-medium text-foreground">
            {currentDate.toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
          {isToday && (
            <p className="text-sm text-accent">Today</p>
          )}
        </div>

        <div className="w-20" /> {/* Spacer for alignment */}
      </div>

      {/* Schedule View */}
      {isLoading ? (
        <PageLoader text="Loading schedule..." />
      ) : schedule ? (
        <ScheduleView
          schedule={schedule}
          onMarkComplete={handleMarkComplete}
          onMarkIncomplete={handleMarkIncomplete}
        />
      ) : (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
          <p className="text-muted-foreground">No schedule for this date</p>
        </div>
      )}
    </div>
  );
}
