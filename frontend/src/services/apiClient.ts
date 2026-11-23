/**
 * HabitOS API Client
 *
 * Centralized API layer for all backend communication.
 * ALL backend communication MUST go through this file.
 */

import type {
  User,
  UserCredentials,
  RegisterPayload,
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
import type {
  HelperStatus,
  HelperDraftResponse,
  HelperConfirmResponse,
  HelperDraftItem,
  HelperDayItem,
} from "@/types/helper";
import type { RangeEntry, SeriesDay, ItemDetail } from "@/types/dashboard";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// =============================================================================
// AUTH API
// =============================================================================

export const authApi = {
  async login(
    credentials: UserCredentials,
  ): Promise<{ accessToken: string; refreshToken: string; tokenType: string; user: User }> {
    return apiPost("/auth/login", credentials);
  },

  async register(
    payload: RegisterPayload,
  ): Promise<{ accessToken: string; refreshToken: string; tokenType: string; user: User }> {
    return apiPost("/auth/register", payload);
  },

  async refreshToken(
    refreshToken: string,
  ): Promise<{ accessToken: string; tokenType: string }> {
    return apiPost("/auth/refresh", { refreshToken });
  },

  async logout(): Promise<{ message: string }> {
    return apiPost("/auth/logout");
  },
};

// =============================================================================
// BEHAVIORS API
// =============================================================================

export const behaviorsApi = {
  async getBehaviors(): Promise<ApiResponse<Behavior[]>> {
    return apiGet("/behaviors");
  },

  async getBehavior(id: string): Promise<ApiResponse<Behavior>> {
    return apiGet(`/behaviors/${id}`);
  },

  async createBehavior(data: BehaviorFormData): Promise<ApiResponse<Behavior>> {
    return apiPost("/behaviors", data);
  },

  async updateBehavior(
    id: string,
    data: Partial<BehaviorFormData>,
  ): Promise<ApiResponse<Behavior>> {
    return apiPut(`/behaviors/${id}`, data);
  },

  async deleteBehavior(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiDelete(`/behaviors/${id}`);
  },

  async getObjectives(): Promise<ApiResponse<Objective[]>> {
    return apiGet("/behaviors/objectives");
  },

  async updateObjectiveWeight(
    objectiveId: string,
    weight: number,
  ): Promise<ApiResponse<Objective[]>> {
    return apiPut(`/behaviors/objectives/${objectiveId}`, { weight });
  },
};

// =============================================================================
// OPTIMIZATION API
// =============================================================================

export const optimizationApi = {
  async runOptimization(
    request?: OptimizationRequest,
  ): Promise<ApiResponse<OptimizationResult>> {
    return apiPost("/optimization/solve", request || {});
  },

  async getOptimizationHistory(): Promise<ApiResponse<OptimizationRun[]>> {
    return apiGet("/optimization/history");
  },

  async getOptimizationRun(id: string): Promise<ApiResponse<OptimizationRun>> {
    return apiGet(`/optimization/history/${id}`);
  },

  async forcedInclude(
    behaviorIds: string[],
    targetDate?: string,
  ): Promise<ApiResponse<ForcedIncludeResult>> {
    return apiPost("/optimization/forced-include", { behaviorIds, targetDate });
  },
};

// =============================================================================
// SCHEDULE API
// =============================================================================

export const scheduleApi = {
  async getSchedule(date?: string): Promise<ApiResponse<DailySchedule>> {
    const endpoint = date ? `/schedule?date=${date}` : "/schedule";
    return apiGet(endpoint);
  },

  async markBehaviorComplete(
    scheduledBehaviorId: string,
  ): Promise<ApiResponse<{ message: string }>> {
    return apiPost(`/schedule/${scheduledBehaviorId}/complete`);
  },

  async markBehaviorIncomplete(
    scheduledBehaviorId: string,
  ): Promise<ApiResponse<{ message: string }>> {
    return apiPost(`/schedule/${scheduledBehaviorId}/incomplete`);
  },

  async releaseSession(
    scheduledBehaviorId: string,
  ): Promise<ApiResponse<{ released_at: string }>> {
    return apiPost(`/schedule/${scheduledBehaviorId}/release`);
  },

  async commitDay(): Promise<ApiResponse<{ committed_at?: string; message?: string }>> {
    return apiPost("/schedule/commit");
  },

  async reoptimize(): Promise<ApiResponse<{ new_run_id: string; schedule?: DailySchedule; disruption?: { carried_sessions: number; minutes_shifted: number; penalty_applied: number; lambda_per_minute: number } | null }>> {
    return apiPost("/schedule/reoptimize");
  },
};

// =============================================================================
// ANALYTICS API
// =============================================================================

export const analyticsApi = {
  async getStats(): Promise<ApiResponse<DashboardStats>> {
    return apiGet("/analytics/stats");
  },

  async getDashboardSummary(days?: number): Promise<ApiResponse<DashboardSummary>> {
    return apiGet(days ? `/analytics/summary?days=${days}` : "/analytics/summary");
  },

  async getSeries(days: number = 7): Promise<SeriesDay[]> {
    return apiGet<SeriesDay[]>(`/analytics/series?days=${days}`);
  },

  async getAnalytics(period: string = "7d"): Promise<ApiResponse<AnalyticsData>> {
    return apiGet(`/analytics?period=${period}`);
  },
};

// =============================================================================
// HELPER API
// =============================================================================

export const helperApi = {
  async getStatus(): Promise<HelperStatus> {
    return apiGet<HelperStatus>("/helper/status");
  },

  async draft(transcript: string): Promise<HelperDraftResponse> {
    return apiPost<HelperDraftResponse>("/helper/draft", { transcript });
  },

  async confirm(payload: {
    draftId: string;
    transcript: string;
    items: HelperDraftItem[];
  }): Promise<HelperConfirmResponse> {
    return apiPost<HelperConfirmResponse>("/helper/confirm", payload);
  },
};

// =============================================================================
// ITEMS API
// =============================================================================

export const itemsApi = {
  async getDay(date: string): Promise<HelperDayItem[]> {
    return apiGet<HelperDayItem[]>(`/items/day?date=${date}`);
  },

  async getRange(from: string, to: string): Promise<RangeEntry[]> {
    return apiGet<RangeEntry[]>(`/items/range?from=${from}&to=${to}`);
  },

  async get(id: string): Promise<ItemDetail> {
    return apiGet<ItemDetail>(`/items/${id}`);
  },

  async update(id: string, data: Record<string, unknown>): Promise<ItemDetail> {
    return apiPut<ItemDetail>(`/items/${id}`, data);
  },

  async remove(id: string): Promise<{ deleted: boolean }> {
    return apiDelete<{ deleted: boolean }>(`/items/${id}`);
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
  helper: helperApi,
  items: itemsApi,
};

export default apiClient;
