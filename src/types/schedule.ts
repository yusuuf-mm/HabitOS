import type { ScheduledBehavior, ObjectiveContribution } from "./optimization";

export interface TimeSlotGroup {
  slot: string;
  label: string;
  startHour: number;
  endHour: number;
  behaviors: ScheduledBehavior[];
}

export interface DaySchedule {
  date: string;
  dayOfWeek: string;
  isToday: boolean;
  timeSlotGroups: TimeSlotGroup[];
  totalBehaviors: number;
  totalDuration: number;
  completedCount: number;
}

export interface WeekSchedule {
  startDate: string;
  endDate: string;
  days: DaySchedule[];
  totalBehaviors: number;
  completionRate: number;
}

export interface ScheduleStats {
  totalScheduled: number;
  totalCompleted: number;
  completionRate: number;
  averageDailyDuration: number;
  topObjectiveContributions: ObjectiveContribution[];
}

export interface ScheduleFilters {
  dateFrom?: string;
  dateTo?: string;
  behaviorIds?: string[];
  timeSlots?: string[];
  showCompleted?: boolean;
}
