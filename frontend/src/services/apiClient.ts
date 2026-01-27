/**
 * HabitOS API Client
 * 
 * Centralized API layer for all backend communication.
 * Currently uses mock data - designed to be easily replaced with real FastAPI backend.
 * 
 * ALL backend communication MUST go through this file.
 * Components should NEVER import mock data directly.
 */

import type {
  User,
  UserCredentials,
  RegisterPayload,
  AuthTokens,
  Behavior,
  BehaviorFormData,
  Objective,
  OptimizationRun,
  OptimizationRequest,
  OptimizationResult,
  DailySchedule,
  DashboardStats,
  DashboardSummary,
  AnalyticsData,
  ApiResponse,
} from "@/types";

// =============================================================================
// MOCK DATA - Production-like data
// =============================================================================

const MOCK_USER: User = {
  id: "usr_01HV8KE2X3Y4Z5A6B7C8D9E0F",
  email: "alex.chen@techcorp.io",
  name: "Alex Chen",
  avatar: undefined,
  createdAt: "2024-01-15T08:00:00Z",
  updatedAt: "2024-03-20T14:30:00Z",
};

const MOCK_OBJECTIVES: Objective[] = [
  {
    id: "obj_health_01",
    userId: MOCK_USER.id,
    name: "Physical Health",
    description: "Improve overall physical fitness and energy levels",
    priority: 9,
    createdAt: "2024-01-15T08:00:00Z",
  },
  {
    id: "obj_productivity_01",
    userId: MOCK_USER.id,
    name: "Career Growth",
    description: "Advance technical skills and professional development",
    priority: 8,
    createdAt: "2024-01-15T08:00:00Z",
  },
  {
    id: "obj_learning_01",
    userId: MOCK_USER.id,
    name: "Continuous Learning",
    description: "Maintain intellectual curiosity and skill development",
    priority: 7,
    createdAt: "2024-01-15T08:00:00Z",
  },
  {
    id: "obj_mindfulness_01",
    userId: MOCK_USER.id,
    name: "Mental Clarity",
    description: "Reduce stress and improve focus through mindfulness",
    priority: 8,
    createdAt: "2024-01-15T08:00:00Z",
  },
];

const MOCK_BEHAVIORS: Behavior[] = [
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1A",
    userId: MOCK_USER.id,
    name: "Morning Run",
    description: "30-45 minute run around the neighborhood or park",
    category: "health",
    energyCost: 6,
    durationMin: 30,
    durationMax: 45,
    preferredTimeSlots: ["early_morning", "morning"],
    objectiveImpacts: [
      { objectiveId: "obj_health_01", objectiveName: "Physical Health", impactScore: 0.85 },
      { objectiveId: "obj_mindfulness_01", objectiveName: "Mental Clarity", impactScore: 0.4 },
    ],
    isActive: true,
    frequency: "daily",
    createdAt: "2024-01-16T10:00:00Z",
    updatedAt: "2024-03-15T09:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1B",
    userId: MOCK_USER.id,
    name: "Deep Work Session",
    description: "Focused coding or technical work without distractions",
    category: "productivity",
    energyCost: 7,
    durationMin: 90,
    durationMax: 120,
    preferredTimeSlots: ["morning", "midday"],
    objectiveImpacts: [
      { objectiveId: "obj_productivity_01", objectiveName: "Career Growth", impactScore: 0.9 },
      { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", impactScore: 0.3 },
    ],
    isActive: true,
    frequency: "daily",
    createdAt: "2024-01-16T10:30:00Z",
    updatedAt: "2024-03-18T11:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1C",
    userId: MOCK_USER.id,
    name: "Meditation",
    description: "Guided or silent meditation for mental clarity",
    category: "mindfulness",
    energyCost: 2,
    durationMin: 10,
    durationMax: 20,
    preferredTimeSlots: ["early_morning", "evening"],
    objectiveImpacts: [
      { objectiveId: "obj_mindfulness_01", objectiveName: "Mental Clarity", impactScore: 0.95 },
      { objectiveId: "obj_health_01", objectiveName: "Physical Health", impactScore: 0.2 },
    ],
    isActive: true,
    frequency: "daily",
    createdAt: "2024-01-17T08:00:00Z",
    updatedAt: "2024-03-10T07:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1D",
    userId: MOCK_USER.id,
    name: "Technical Reading",
    description: "Read technical books, papers, or documentation",
    category: "learning",
    energyCost: 4,
    durationMin: 30,
    durationMax: 60,
    preferredTimeSlots: ["afternoon", "evening"],
    objectiveImpacts: [
      { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", impactScore: 0.8 },
      { objectiveId: "obj_productivity_01", objectiveName: "Career Growth", impactScore: 0.4 },
    ],
    isActive: true,
    frequency: "daily",
    createdAt: "2024-01-18T14:00:00Z",
    updatedAt: "2024-03-12T15:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1E",
    userId: MOCK_USER.id,
    name: "Strength Training",
    description: "Weightlifting or bodyweight exercises at the gym",
    category: "health",
    energyCost: 8,
    durationMin: 45,
    durationMax: 75,
    preferredTimeSlots: ["afternoon", "evening"],
    objectiveImpacts: [
      { objectiveId: "obj_health_01", objectiveName: "Physical Health", impactScore: 0.9 },
    ],
    isActive: true,
    frequency: "weekly",
    frequencyCount: 3,
    createdAt: "2024-01-20T16:00:00Z",
    updatedAt: "2024-03-19T17:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1F",
    userId: MOCK_USER.id,
    name: "Side Project Work",
    description: "Work on personal coding projects and experiments",
    category: "creativity",
    energyCost: 5,
    durationMin: 60,
    durationMax: 120,
    preferredTimeSlots: ["evening", "night"],
    objectiveImpacts: [
      { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", impactScore: 0.7 },
      { objectiveId: "obj_productivity_01", objectiveName: "Career Growth", impactScore: 0.5 },
    ],
    isActive: false,
    frequency: "weekly",
    frequencyCount: 2,
    createdAt: "2024-02-01T19:00:00Z",
    updatedAt: "2024-03-01T20:00:00Z",
  },
  {
    id: "bhv_01HV8KE2X3Y4Z5A6B7C8D9E1G",
    userId: MOCK_USER.id,
    name: "Language Practice",
    description: "Practice Japanese using Anki and conversation apps",
    category: "learning",
    energyCost: 3,
    durationMin: 15,
    durationMax: 30,
    preferredTimeSlots: ["morning", "evening"],
    objectiveImpacts: [
      { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", impactScore: 0.6 },
    ],
    isActive: true,
    frequency: "daily",
    createdAt: "2024-02-10T09:00:00Z",
    updatedAt: "2024-03-20T10:00:00Z",
  },
];

const generateMockOptimizationRuns = (): OptimizationRun[] => {
  const now = new Date();
  const runs: OptimizationRun[] = [];
  
  for (let i = 0; i < 10; i++) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    
    runs.push({
      id: `opt_run_${i.toString().padStart(3, "0")}`,
      userId: MOCK_USER.id,
      status: i === 0 ? "completed" : (i < 8 ? "completed" : (i === 8 ? "failed" : "completed")),
      solverStatus: i === 8 ? "timeout" : "optimal",
      scheduledBehaviors: [],
      objectiveContributions: [
        { objectiveId: "obj_health_01", objectiveName: "Physical Health", contribution: 0.75 + Math.random() * 0.2, percentage: 28 },
        { objectiveId: "obj_productivity_01", objectiveName: "Career Growth", contribution: 0.8 + Math.random() * 0.15, percentage: 32 },
        { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", contribution: 0.6 + Math.random() * 0.25, percentage: 22 },
        { objectiveId: "obj_mindfulness_01", objectiveName: "Mental Clarity", contribution: 0.7 + Math.random() * 0.2, percentage: 18 },
      ],
      totalScore: 0.72 + Math.random() * 0.2,
      executionTimeMs: 150 + Math.floor(Math.random() * 300),
      constraintsSatisfied: i === 8 ? 4 : 6,
      constraintsTotal: 6,
      createdAt: date.toISOString(),
      completedAt: i === 8 ? undefined : new Date(date.getTime() + 200).toISOString(),
    });
  }
  
  return runs;
};

const MOCK_OPTIMIZATION_RUNS = generateMockOptimizationRuns();

const generateTodaySchedule = (): DailySchedule => {
  const today = new Date().toISOString().split("T")[0];
  
  return {
    id: `schedule_${today}`,
    userId: MOCK_USER.id,
    date: today,
    scheduledBehaviors: [
      {
        id: "sb_001",
        behaviorId: MOCK_BEHAVIORS[2].id,
        behavior: MOCK_BEHAVIORS[2],
        scheduledDate: today,
        timeSlot: "early_morning",
        startTime: "06:00",
        endTime: "06:15",
        duration: 15,
        isCompleted: true,
        completedAt: `${today}T06:18:00Z`,
      },
      {
        id: "sb_002",
        behaviorId: MOCK_BEHAVIORS[0].id,
        behavior: MOCK_BEHAVIORS[0],
        scheduledDate: today,
        timeSlot: "early_morning",
        startTime: "06:30",
        endTime: "07:15",
        duration: 45,
        isCompleted: true,
        completedAt: `${today}T07:20:00Z`,
      },
      {
        id: "sb_003",
        behaviorId: MOCK_BEHAVIORS[6].id,
        behavior: MOCK_BEHAVIORS[6],
        scheduledDate: today,
        timeSlot: "morning",
        startTime: "08:00",
        endTime: "08:20",
        duration: 20,
        isCompleted: true,
        completedAt: `${today}T08:22:00Z`,
      },
      {
        id: "sb_004",
        behaviorId: MOCK_BEHAVIORS[1].id,
        behavior: MOCK_BEHAVIORS[1],
        scheduledDate: today,
        timeSlot: "morning",
        startTime: "09:00",
        endTime: "11:00",
        duration: 120,
        isCompleted: false,
      },
      {
        id: "sb_005",
        behaviorId: MOCK_BEHAVIORS[3].id,
        behavior: MOCK_BEHAVIORS[3],
        scheduledDate: today,
        timeSlot: "afternoon",
        startTime: "14:00",
        endTime: "14:45",
        duration: 45,
        isCompleted: false,
      },
      {
        id: "sb_006",
        behaviorId: MOCK_BEHAVIORS[4].id,
        behavior: MOCK_BEHAVIORS[4],
        scheduledDate: today,
        timeSlot: "evening",
        startTime: "18:00",
        endTime: "19:00",
        duration: 60,
        isCompleted: false,
      },
    ],
    totalDuration: 305,
    totalEnergySpent: 30,
    objectiveScores: [
      { objectiveId: "obj_health_01", objectiveName: "Physical Health", contribution: 0.82, percentage: 30 },
      { objectiveId: "obj_productivity_01", objectiveName: "Career Growth", contribution: 0.78, percentage: 28 },
      { objectiveId: "obj_learning_01", objectiveName: "Continuous Learning", contribution: 0.65, percentage: 24 },
      { objectiveId: "obj_mindfulness_01", objectiveName: "Mental Clarity", contribution: 0.71, percentage: 18 },
    ],
    createdAt: `${today}T05:00:00Z`,
  };
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const createResponse = <T>(data: T, success = true, message?: string): ApiResponse<T> => ({
  data,
  success,
  message,
  timestamp: new Date().toISOString(),
});

const generateId = (prefix: string) =>
  `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).substr(2, 9)}`;

// =============================================================================
// AUTH API
// =============================================================================

export const authApi = {
  async login(credentials: UserCredentials): Promise<ApiResponse<{ user: User; tokens: AuthTokens }>> {
    await delay(800);
    
    if (credentials.email === "demo@habitos.io" && credentials.password === "demo123") {
      const tokens: AuthTokens = {
        accessToken: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(JSON.stringify({ userId: MOCK_USER.id, exp: Date.now() + 3600000 }))}`,
        refreshToken: `refresh_${generateId("rt")}`,
        expiresAt: Date.now() + 3600000,
      };
      
      return createResponse({ user: MOCK_USER, tokens });
    }
    
    throw { code: "AUTH_INVALID_CREDENTIALS", message: "Invalid email or password" };
  },

  async register(payload: RegisterPayload): Promise<ApiResponse<{ user: User; tokens: AuthTokens }>> {
    await delay(1000);
    
    const newUser: User = {
      id: generateId("usr"),
      email: payload.email,
      name: payload.name,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    
    const tokens: AuthTokens = {
      accessToken: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(JSON.stringify({ userId: newUser.id, exp: Date.now() + 3600000 }))}`,
      refreshToken: `refresh_${generateId("rt")}`,
      expiresAt: Date.now() + 3600000,
    };
    
    return createResponse({ user: newUser, tokens });
  },

  async refreshToken(refreshToken: string): Promise<ApiResponse<AuthTokens>> {
    await delay(300);
    
    if (!refreshToken) {
      throw { code: "AUTH_INVALID_REFRESH_TOKEN", message: "Invalid refresh token" };
    }
    
    return createResponse({
      accessToken: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(JSON.stringify({ userId: MOCK_USER.id, exp: Date.now() + 3600000 }))}`,
      refreshToken: `refresh_${generateId("rt")}`,
      expiresAt: Date.now() + 3600000,
    });
  },

  async logout(): Promise<ApiResponse<null>> {
    await delay(200);
    return createResponse(null);
  },
};

// =============================================================================
// BEHAVIORS API
// =============================================================================

let mockBehaviors = [...MOCK_BEHAVIORS];

export const behaviorsApi = {
  async getBehaviors(): Promise<ApiResponse<Behavior[]>> {
    await delay(500);
    return createResponse(mockBehaviors);
  },

  async getBehavior(id: string): Promise<ApiResponse<Behavior>> {
    await delay(300);
    const behavior = mockBehaviors.find((b) => b.id === id);
    if (!behavior) {
      throw { code: "BEHAVIOR_NOT_FOUND", message: "Behavior not found" };
    }
    return createResponse(behavior);
  },

  async createBehavior(data: BehaviorFormData): Promise<ApiResponse<Behavior>> {
    await delay(600);
    const newBehavior: Behavior = {
      id: generateId("bhv"),
      userId: MOCK_USER.id,
      ...data,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    mockBehaviors = [newBehavior, ...mockBehaviors];
    return createResponse(newBehavior, true, "Behavior created successfully");
  },

  async updateBehavior(id: string, data: Partial<BehaviorFormData>): Promise<ApiResponse<Behavior>> {
    await delay(500);
    const index = mockBehaviors.findIndex((b) => b.id === id);
    if (index === -1) {
      throw { code: "BEHAVIOR_NOT_FOUND", message: "Behavior not found" };
    }
    mockBehaviors[index] = {
      ...mockBehaviors[index],
      ...data,
      updatedAt: new Date().toISOString(),
    };
    return createResponse(mockBehaviors[index], true, "Behavior updated successfully");
  },

  async deleteBehavior(id: string): Promise<ApiResponse<null>> {
    await delay(400);
    const index = mockBehaviors.findIndex((b) => b.id === id);
    if (index === -1) {
      throw { code: "BEHAVIOR_NOT_FOUND", message: "Behavior not found" };
    }
    mockBehaviors = mockBehaviors.filter((b) => b.id !== id);
    return createResponse(null, true, "Behavior deleted successfully");
  },

  async getObjectives(): Promise<ApiResponse<Objective[]>> {
    await delay(300);
    return createResponse(MOCK_OBJECTIVES);
  },
};

// =============================================================================
// OPTIMIZATION API
// =============================================================================

export const optimizationApi = {
  async runOptimization(request?: OptimizationRequest): Promise<ApiResponse<OptimizationResult>> {
    await delay(2500); // Simulate optimization processing
    
    const schedule = generateTodaySchedule();
    const run: OptimizationRun = {
      id: generateId("opt_run"),
      userId: MOCK_USER.id,
      status: "completed",
      solverStatus: "optimal",
      scheduledBehaviors: schedule.scheduledBehaviors,
      objectiveContributions: schedule.objectiveScores,
      totalScore: 0.78 + Math.random() * 0.15,
      executionTimeMs: 180 + Math.floor(Math.random() * 200),
      constraintsSatisfied: 6,
      constraintsTotal: 6,
      createdAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    };
    
    return createResponse({ run, schedule }, true, "Optimization completed successfully");
  },

  async getOptimizationHistory(): Promise<ApiResponse<OptimizationRun[]>> {
    await delay(600);
    return createResponse(MOCK_OPTIMIZATION_RUNS);
  },

  async getOptimizationRun(id: string): Promise<ApiResponse<OptimizationRun>> {
    await delay(400);
    const run = MOCK_OPTIMIZATION_RUNS.find((r) => r.id === id);
    if (!run) {
      throw { code: "OPTIMIZATION_NOT_FOUND", message: "Optimization run not found" };
    }
    return createResponse(run);
  },
};

// =============================================================================
// SCHEDULE API
// =============================================================================

export const scheduleApi = {
  async getSchedule(date?: string): Promise<ApiResponse<DailySchedule>> {
    await delay(500);
    const schedule = generateTodaySchedule();
    if (date) {
      schedule.date = date;
    }
    return createResponse(schedule);
  },

  async markBehaviorComplete(scheduledBehaviorId: string): Promise<ApiResponse<null>> {
    await delay(300);
    return createResponse(null, true, "Behavior marked as complete");
  },

  async markBehaviorIncomplete(scheduledBehaviorId: string): Promise<ApiResponse<null>> {
    await delay(300);
    return createResponse(null, true, "Behavior marked as incomplete");
  },
};

// =============================================================================
// ANALYTICS API
// =============================================================================

export const analyticsApi = {
  async getStats(): Promise<ApiResponse<DashboardStats>> {
    await delay(400);
    return createResponse({
      totalBehaviors: mockBehaviors.length,
      activeBehaviors: mockBehaviors.filter((b) => b.isActive).length,
      totalOptimizationRuns: MOCK_OPTIMIZATION_RUNS.length,
      completionRate: 0.73,
      averageScore: 0.81,
      streakDays: 12,
    });
  },

  async getDashboardSummary(): Promise<ApiResponse<DashboardSummary>> {
    await delay(700);
    const schedule = generateTodaySchedule();
    
    return createResponse({
      stats: {
        totalBehaviors: mockBehaviors.length,
        activeBehaviors: mockBehaviors.filter((b) => b.isActive).length,
        totalOptimizationRuns: MOCK_OPTIMIZATION_RUNS.length,
        completionRate: 0.73,
        averageScore: 0.81,
        streakDays: 12,
      },
      recentOptimizations: MOCK_OPTIMIZATION_RUNS.slice(0, 5).map((r) => ({
        id: r.id,
        status: r.status,
        score: r.totalScore,
        createdAt: r.createdAt,
      })),
      recentBehaviors: mockBehaviors.slice(0, 5).map((b) => ({
        id: b.id,
        name: b.name,
        category: b.category,
        isActive: b.isActive,
        createdAt: b.createdAt,
      })),
      todaySchedule: schedule.scheduledBehaviors.map((sb) => ({
        id: sb.id,
        behaviorName: sb.behavior.name,
        timeSlot: sb.timeSlot,
        startTime: sb.startTime,
        isCompleted: sb.isCompleted,
      })),
    });
  },

  async getAnalytics(period: string = "7d"): Promise<ApiResponse<AnalyticsData>> {
    await delay(600);
    
    const days = period === "30d" ? 30 : period === "7d" ? 7 : 14;
    const behaviorCompletions = [];
    const energyUsage = [];
    
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split("T")[0];
      
      behaviorCompletions.push({
        date: dateStr,
        completed: 4 + Math.floor(Math.random() * 3),
        scheduled: 6,
      });
      
      energyUsage.push({
        date: dateStr,
        energySpent: 25 + Math.floor(Math.random() * 15),
        energyBudget: 40,
      });
    }
    
    return createResponse({
      period,
      behaviorCompletions,
      objectiveProgress: [
        { objectiveName: "Physical Health", progress: 0.78, trend: "up" },
        { objectiveName: "Career Growth", progress: 0.82, trend: "up" },
        { objectiveName: "Continuous Learning", progress: 0.65, trend: "stable" },
        { objectiveName: "Mental Clarity", progress: 0.71, trend: "up" },
      ],
      categoryDistribution: [
        { category: "health", count: 2, percentage: 28 },
        { category: "productivity", count: 1, percentage: 14 },
        { category: "learning", count: 2, percentage: 28 },
        { category: "mindfulness", count: 1, percentage: 14 },
        { category: "creativity", count: 1, percentage: 14 },
      ],
      energyUsage,
    });
  },
};

// =============================================================================
// UNIFIED API EXPORT
// =============================================================================

export const apiClient = {
  auth: authApi,
  behaviors: behaviorsApi,
  optimization: optimizationApi,
  schedule: scheduleApi,
  analytics: analyticsApi,
};

export default apiClient;
