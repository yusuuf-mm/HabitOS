import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Login from "../pages/Login";
import { BrowserRouter } from "react-router-dom";

// Mock the useAuth hook
const mockLogin = vi.fn();

vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => ({
        login: mockLogin,
        isAuthenticated: false,
        isLoading: false,
    }),
}));

describe("Login Page", () => {
    it("renders login form", () => {
        render(
            <BrowserRouter>
                <Login />
            </BrowserRouter>
        );

        expect(screen.getByText(/Sign in to continue to HabitOS/i)).toBeInTheDocument();
        expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
        expect(screen.getByPlaceholderText(/••••••••/i)).toBeInTheDocument();
    });

    it("calls login on form submission", async () => {
        mockLogin.mockResolvedValue({ success: true });

        render(
            <BrowserRouter>
                <Login />
            </BrowserRouter>
        );

        const emailInput = screen.getByPlaceholderText(/you@example.com/i);
        const passwordInput = screen.getByPlaceholderText(/••••••••/i);
        const submitButton = screen.getByRole("button", { name: /sign in/i });

        fireEvent.change(emailInput, { target: { value: "test@example.com" } });
        fireEvent.change(passwordInput, { target: { value: "password123" } });
        fireEvent.click(submitButton);

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith({
                email: "test@example.com",
                password: "password123",
            });
        });
    });
});
