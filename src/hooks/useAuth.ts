import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { apiClient } from "@/services/apiClient";
import type { UserCredentials, RegisterPayload } from "@/types";

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
      const storedTokens = useAuthStore.getState().tokens;
      
      if (storedTokens && storedTokens.expiresAt > Date.now()) {
        setLoading(false);
      } else if (storedTokens?.refreshToken) {
        try {
          const response = await apiClient.auth.refreshToken(storedTokens.refreshToken);
          useAuthStore.getState().setTokens(response.data);
        } catch {
          storeLogout();
        }
      } else {
        setLoading(false);
      }
    };

    checkAuth();
  }, [setLoading, storeLogout]);

  const login = useCallback(
    async (credentials: UserCredentials) => {
      setLoading(true);
      try {
        const response = await apiClient.auth.login(credentials);
        storeLogin(response.data.user, response.data.tokens);
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
        storeLogin(response.data.user, response.data.tokens);
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
