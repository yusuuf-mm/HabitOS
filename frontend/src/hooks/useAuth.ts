import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { apiClient } from "@/services/apiClient";
import type { UserCredentials, RegisterPayload } from "@/types";

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresAt: number;
}

export function useAuth() {
  const navigate = useNavigate();
  const {
    user,
    tokens,
    isAuthenticated,
    isLoading,
    login: storeLogin,
    logout: storeLogout,
    setLoading,
  } = useAuthStore();

  // Check auth status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("authToken");

      if (token) {
        // Token exists, user is authenticated
        setLoading(false);
      } else {
        setLoading(false);
      }
    };

    checkAuth();
  }, [setLoading]);

  const login = useCallback(
    async (credentials: UserCredentials) => {
      setLoading(true);
      try {
        const response = await apiClient.auth.login(credentials);
        // Save token to localStorage
        localStorage.setItem("authToken", response.accessToken);
        // Update auth store
        const authTokens: AuthTokens = {
          accessToken: response.accessToken,
          refreshToken: response.refreshToken,
          tokenType: response.tokenType,
          expiresAt: Date.now() + 3600000, // 1 hour
        };
        storeLogin(response.user, authTokens);
        navigate("/dashboard");
        return { success: true };
      } catch (error: unknown) {
        setLoading(false);
        const err = error as { message?: string };
        return { success: false, error: err.message || "Login failed" };
      }
    },
    [navigate, storeLogin, setLoading]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      setLoading(true);
      try {
        const response = await apiClient.auth.register(payload);
        // Save token to localStorage
        localStorage.setItem("authToken", response.accessToken);
        // Update auth store
        const authTokens: AuthTokens = {
          accessToken: response.accessToken,
          refreshToken: response.refreshToken,
          tokenType: response.tokenType,
          expiresAt: Date.now() + 3600000, // 1 hour
        };
        storeLogin(response.user, authTokens);
        navigate("/dashboard");
        return { success: true };
      } catch (error: unknown) {
        setLoading(false);
        const err = error as { message?: string };
        return { success: false, error: err.message || "Registration failed" };
      }
    },
    [navigate, storeLogin, setLoading]
  );

  const logout = useCallback(async () => {
    try {
      await apiClient.auth.logout();
    } finally {
      // Clear localStorage
      localStorage.removeItem("authToken");
      storeLogout();
      navigate("/login");
    }
  }, [navigate, storeLogout]);

  return {
    user,
    tokens,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
  };
}
