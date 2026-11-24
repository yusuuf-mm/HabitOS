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
  // draft | committed | fallback | none. Future week plans are drafts; today's
  // accepted baseline is committed and a partly re-planned today is fallback.
  planSource?: "draft" | "committed" | "fallback" | "none";
}

export interface WeekSessionSlot {
  startTime: string;
  endTime: string;
  duration: number;
}

export interface WeekSession extends WeekSessionSlot {
  plannedSessionId: string;
  behaviorId: string;
  behaviorName: string;
}

export interface WeekSessionMove extends WeekSessionSlot {
  plannedSessionId: string;
  behaviorId: string;
  behaviorName: string;
  before: WeekSessionSlot;
  after: WeekSessionSlot;
}

export interface WeekPlanningError {
  code: string;
  message: string;
}

export interface WeekDaySkip extends WeekPlanningError {
  date: string;
}

export interface WeekDayResult {
  date: string;
  mode: "full" | "partial";
  available: boolean;
  solverStatus?: string | null;
  error?: WeekPlanningError | null;
  sessionsBefore: number;
  sessionsAfter?: number | null;
  minutesBefore: number;
  minutesAfter?: number | null;
  added: WeekSession[];
  moved: WeekSessionMove[];
  dropped: WeekSession[];
  declines: Array<{ behaviorId: string; behaviorName: string; reason: string }>;
  // Hash of the diff without generated session IDs, used to detect stale previews.
  resultHash: string;
}

export interface WeekPreviewResult {
  weekStart: string;
  rangeStart: string;
  rangeEnd: string;
  generatedAt: string;
  fingerprint: string;
  days: WeekDayResult[];
  skippedDays: WeekDaySkip[];
}

export interface WeekApplyRequest {
  weekStart: string;
  fingerprint: string;
  dates: string[];
  expectedResults: Record<string, string>;
}

export interface WeekDayApplyResult {
  date: string;
  runId: string;
  planRevision: number;
  mode: "full" | "partial";
  added: number;
  moved: number;
  dropped: number;
  resultHash: string;
}

export interface WeekApplyResult {
  weekStart: string;
  rangeStart: string;
  rangeEnd: string;
  fingerprint: string;
  appliedDays: number;
  days: WeekDayApplyResult[];
  skippedDays: WeekDaySkip[];
}
