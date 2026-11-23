import type { Behavior, TimeSlot } from "./behavior";

export type OptimizationStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export type SolverStatus =
  | "optimal"
  | "feasible"
  | "infeasible"
  | "unbounded"
  | "timeout";

export interface ObjectiveContribution {
  objectiveId: string;
  objectiveName: string;
  contribution: number;
  percentage: number;
}

export interface ScheduledBehavior {
  id: string;
  behaviorId: string;
  behavior: Behavior;
  scheduledDate: string;
  timeSlot: TimeSlot;
  startTime: string; // HH:mm format
  endTime: string;
  duration: number; // minutes
  // Stable across re-plans; `id` is per run and must not be used as identity.
  plannedSessionId: string;
  isCompleted: boolean;
  completedAt?: string;
  // Set when the user withdrew the session before it started. Such a session is
  // neither pending nor completed and must not be counted as missed.
  releasedAt?: string | null;
}

export interface OptimizationRun {
  id: string;
  userId: string;
  status: OptimizationStatus;
  solverStatus?: SolverStatus;
  scheduledBehaviors: ScheduledBehavior[];
  objectiveContributions: ObjectiveContribution[];
  totalScore: number;
  executionTimeMs: number;
  /** @deprecated Always 0. No real constraint count exists; use declines and scheduledBehaviors.length. */
  constraintsSatisfied: number;
  /** @deprecated Always 0. Kept so older clients keep parsing. */
  constraintsTotal: number;
  createdAt: string;
  completedAt?: string;
}

export interface OptimizationRequest {
  targetDate?: string;
  includeInactiveBehaviors?: boolean;
  maxExecutionTimeMs?: number;
}

export interface OptimizationResult {
  run: OptimizationRun;
  schedule: DailySchedule;
}

export interface DailySchedule {
  id: string;
  userId: string;
  date: string;
  scheduledBehaviors: ScheduledBehavior[];
  totalDuration: number;
  objectiveScores: ObjectiveContribution[];
  createdAt: string;
  // Present on the schedule endpoint; why the planner left habits out.
  declines?: Array<{ behaviorId: string; behaviorName: string; reason: string }>;
}
