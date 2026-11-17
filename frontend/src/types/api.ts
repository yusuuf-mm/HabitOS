export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  timestamp: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, string>;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface DashboardStats {
  totalBehaviors: number;
  activeBehaviors: number;
  totalOptimizationRuns: number;
  // Null when the week had no baseline sessions to count against.
  completionRate: number | null;
  released: number;
  systemDropped: number;
  completionRateVsFeasible: number | null;
  averageScore: number;
  streakDays: number;
}

export interface DashboardSummary {
  stats: DashboardStats;
  recentOptimizations: Array<{
    id: string;
    status: string;
    score: number;
    createdAt: string;
  }>;
  recentBehaviors: Array<{
    id: string;
    name: string;
    category: string;
    isActive: boolean;
    createdAt: string;
  }>;
  todaySchedule: Array<{
    id: string;
    behaviorName: string;
    timeSlot: string;
    startTime: string;
    isCompleted: boolean;
  }>;
}

export interface AnalyticsData {
  period: string;
  behaviorCompletions: Array<{
    date: string;
    completed: number;
    scheduled: number;
  }>;
  objectiveProgress: Array<{
    objectiveName: string;
    progress: number;
    trend: "up" | "down" | "stable";
  }>;
  categoryDistribution: Array<{
    category: string;
    count: number;
    percentage: number;
  }>;
}

export interface ForcedSession {
  behaviorId: string;
  behaviorName: string;
  startTime: string;
  endTime: string;
  duration: number;
}

export interface DisplacedSession {
  behaviorId: string;
  behaviorName: string;
  reason: string;
  minutes: number;
}

export interface ForcedIncludeResult {
  fits: boolean;
  forced: ForcedSession[];
  displaced: DisplacedSession[];
  relaxations: Array<{ kind: string; behaviorId: string; detail: string }>;
  objectiveChange: number;
  solverObjective?: number;
  seconds: number;
  reason?: string;
}
