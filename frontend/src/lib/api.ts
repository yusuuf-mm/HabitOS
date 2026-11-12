import axios, { type AxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/authStore";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

/**
 * Centralized Axios instance for all backend communication.
 *
 * Automatically injects the active JWT from Zustand auth state into every
 * outgoing request. Components must never make direct fetch calls — always
 * import this instance or the typed API modules built on top of it.
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ---------------------------------------------------------------------------
// Request interceptor: inject Bearer token from Zustand store
// ---------------------------------------------------------------------------
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().tokens?.accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor: unwrap Axios envelope so callers receive the JSON body
// directly (matching the old apiCall contract)
// ---------------------------------------------------------------------------
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status;
    const message =
      err.response?.data?.message || err.message || "Request failed";
    return Promise.reject({ code: "API_ERROR", message, status });
  },
);

// ---------------------------------------------------------------------------
// Typed helper – keeps request bodies neat
// ---------------------------------------------------------------------------
export async function apiGet<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  return api.get(url, config) as unknown as Promise<T>;
}

export async function apiPost<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return api.post(url, data, config) as unknown as Promise<T>;
}

export async function apiPut<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return api.put(url, data, config) as unknown as Promise<T>;
}

export async function apiDelete<T>(
  url: string,
  config?: AxiosRequestConfig,
): Promise<T> {
  return api.delete(url, config) as unknown as Promise<T>;
}

export default api;
