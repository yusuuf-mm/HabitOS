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
  isCompleted: boolean;
  completedAt?: string;
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
  constraintsSatisfied: number;
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
  totalEnergySpent: number;
  objectiveScores: ObjectiveContribution[];
  createdAt: string;
}
