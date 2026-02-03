/**
 * HabitOS API Client
 * 
 * Centralized API layer for all backend communication.
 * Connects to FastAPI backend at http://localhost:8000/api/v1
 * 
 * ALL backend communication MUST go through this file.
 * Components should NEVER make direct API calls.
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
// CONFIG
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// Helper to get auth token from localStorage
const getAuthToken = (): string | null => {
  try {
    return localStorage.getItem("authToken");
  } catch {
    return null;
  }
};

// Helper for API requests
const apiCall = async <T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> => {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options?.headers || {}),
  };

  // Add auth token if available
  const token = getAuthToken();
  if (token) {
    (headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw {
      code: "API_ERROR",
      message: error.message || `HTTP ${response.status}`,
      status: response.status,
    };
  }

  return response.json();
};

// Mock data removed


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
  async login(credentials: UserCredentials): Promise<{ accessToken: string; refreshToken: string; tokenType: string; user: User }> {
    return apiCall("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  async register(payload: RegisterPayload): Promise<{ accessToken: string; refreshToken: string; tokenType: string; user: User }> {
    return apiCall("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async refreshToken(refreshToken: string): Promise<{ accessToken: string; tokenType: string }> {
    return apiCall("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refreshToken }),
    });
  },

  async logout(): Promise<{ message: string }> {
    return apiCall("/auth/logout", {
      method: "POST",
    });
  },
};

// =============================================================================
// BEHAVIORS API
// =============================================================================

export const behaviorsApi = {
  async getBehaviors(): Promise<ApiResponse<Behavior[]>> {
    return apiCall("/behaviors");
  },

  async getBehavior(id: string): Promise<ApiResponse<Behavior>> {
    return apiCall(`/behaviors/${id}`);
  },

  async createBehavior(data: BehaviorFormData): Promise<ApiResponse<Behavior>> {
    return apiCall("/behaviors", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateBehavior(id: string, data: Partial<BehaviorFormData>): Promise<ApiResponse<Behavior>> {
    return apiCall(`/behaviors/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteBehavior(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiCall(`/behaviors/${id}`, {
      method: "DELETE",
    });
  },

  async getObjectives(): Promise<ApiResponse<Objective[]>> {
    return apiCall("/behaviors/objectives");
  },
};

// =============================================================================
// OPTIMIZATION API
// =============================================================================

export const optimizationApi = {
  async runOptimization(request?: OptimizationRequest): Promise<ApiResponse<OptimizationResult>> {
    return apiCall("/optimization/solve", {
      method: "POST",
      body: JSON.stringify(request || {}),
    });
  },

  async getOptimizationHistory(): Promise<ApiResponse<OptimizationRun[]>> {
    return apiCall("/optimization/history");
  },

  async getOptimizationRun(id: string): Promise<ApiResponse<OptimizationRun>> {
    return apiCall(`/optimization/history/${id}`);
  },
};

// =============================================================================
// SCHEDULE API
// =============================================================================

export const scheduleApi = {
  async getSchedule(date?: string): Promise<ApiResponse<DailySchedule>> {
    const endpoint = date ? `/schedule?date=${date}` : "/schedule";
    return apiCall(endpoint);
  },

  async markBehaviorComplete(scheduledBehaviorId: string): Promise<ApiResponse<{ message: string }>> {
    return apiCall(`/schedule/${scheduledBehaviorId}/complete`, {
      method: "POST",
    });
  },

  async markBehaviorIncomplete(scheduledBehaviorId: string): Promise<ApiResponse<{ message: string }>> {
    return apiCall(`/schedule/${scheduledBehaviorId}/incomplete`, {
      method: "POST",
    });
  },
};

// =============================================================================
// ANALYTICS API
// =============================================================================

export const analyticsApi = {
  async getStats(): Promise<ApiResponse<DashboardStats>> {
    return apiCall("/analytics/stats");
  },

  async getDashboardSummary(): Promise<ApiResponse<DashboardSummary>> {
    return apiCall("/analytics/summary");
  },

  async getAnalytics(period: string = "7d"): Promise<ApiResponse<AnalyticsData>> {
    return apiCall(`/analytics?period=${period}`);
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
