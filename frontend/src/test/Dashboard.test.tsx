import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import Dashboard from "../pages/Dashboard";
import { BrowserRouter } from "react-router-dom";
import { apiClient } from "@/services/apiClient";

// Mock apiClient
vi.mock("@/services/apiClient", () => ({
    apiClient: {
        analytics: {
            getDashboardSummary: vi.fn(),
        },
    },
}));

const mockSummaryData = {
    data: {
        stats: {
            totalBehaviors: 10,
            activeBehaviors: 5,
            totalOptimizationRuns: 3,
            completionRate: 0.85,
            streakDays: 7,
            averageScore: 0.9,
        },
        todaySchedule: [],
        recentBehaviors: [],
        recentOptimizations: [],
    },
    success: true,
};

describe("Dashboard Page", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("shows loading state initially", () => {
        // Mock a pending promise
        (apiClient.analytics.getDashboardSummary as Mock).mockReturnValue(new Promise(() => { }));

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>
        );

        expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
    });

    it("renders stats after data loads", async () => {
        (apiClient.analytics.getDashboardSummary as Mock).mockResolvedValue(mockSummaryData);

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>
        );

        // Wait for loading to finish and stats to show
        await waitFor(() => {
            expect(screen.getByText("Total Behaviors")).toBeInTheDocument();
            expect(screen.getByText("10")).toBeInTheDocument(); // totalBehaviors
            expect(screen.getByText("85%")).toBeInTheDocument(); // completionRate
        });
    });

    it("handles error state", async () => {
        (apiClient.analytics.getDashboardSummary as Mock).mockRejectedValue(new Error("Failed"));

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>
        );

        await waitFor(() => {
            expect(screen.getByText(/failed to load dashboard data/i)).toBeInTheDocument();
        });
    });
});
