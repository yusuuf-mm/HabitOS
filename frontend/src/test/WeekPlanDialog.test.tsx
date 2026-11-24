import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { WeekPlanDialog } from "../components/WeekPlanDialog";
import { apiClient } from "@/services/apiClient";

const { previewWeek, applyWeek } = vi.hoisted(() => ({
    previewWeek: vi.fn(),
    applyWeek: vi.fn(),
}));

vi.mock("@/services/apiClient", () => ({
    apiClient: {
        optimization: {
            previewWeek,
            applyWeek,
        },
    },
}));

function day(overrides: Record<string, unknown> = {}) {
    return {
        date: "2026-06-08",
        mode: "full",
        available: true,
        solverStatus: "optimal",
        sessionsBefore: 0,
        sessionsAfter: 0,
        minutesBefore: 0,
        minutesAfter: 0,
        added: [],
        moved: [],
        dropped: [],
        declines: [],
        ...overrides,
    };
}

function previewResponse(days: ReturnType<typeof day>[]) {
    return {
        data: {
            weekStart: "2026-06-08",
            generatedAt: "2026-06-08T12:00:00Z",
            fingerprint: "fp-1",
            days,
        },
        success: true,
    };
}

function renderDialog(onApplied = vi.fn(), onOpenChange = vi.fn()) {
    render(
        <WeekPlanDialog
            open
            onOpenChange={onOpenChange}
            weekStart="2026-06-08"
            onApplied={onApplied}
        />,
    );
    return { onApplied, onOpenChange };
}

describe("WeekPlanDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("labels an unavailable day instead of showing zero changes", async () => {
        previewWeek.mockResolvedValue(
            previewResponse([
                day(),
                day({
                    date: "2026-06-09",
                    available: false,
                    error: {
                        code: "infeasible",
                        message: "No feasible plan on this date.",
                    },
                    sessionsAfter: null,
                    minutesAfter: null,
                }),
            ]),
        );

        renderDialog();

        expect(
            await screen.findByRole("dialog", { name: /plan my week/i }),
        ).toBeInTheDocument();
        expect(screen.getByText("1 of 2 days can be planned.")).toBeInTheDocument();
        expect(screen.getByText("1 day unavailable")).toBeInTheDocument();
        expect(screen.getByText("No feasible plan on this date.")).toBeInTheDocument();
        expect(
            (screen.getByRole("button", { name: /apply 1 day/i }) as HTMLButtonElement)
                .disabled,
        ).toBe(true);
    });

    it("shows an explicit error state when preview fails and can retry", async () => {
        previewWeek.mockRejectedValue(new Error("network down"));

        renderDialog();

        expect(await screen.findByText("Week preview unavailable")).toBeInTheDocument();
        expect(screen.getByText("network down")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /try again/i }));
        await waitFor(() => expect(previewWeek).toHaveBeenCalledTimes(2));
    });

    it("keeps the preview and asks for a refresh when apply is stale", async () => {
        previewWeek.mockResolvedValue(previewResponse([day()]));
        applyWeek.mockRejectedValue(new Error("The plan changed since the preview."));
        const { onApplied, onOpenChange } = renderDialog();

        fireEvent.click(
            await screen.findByRole("button", { name: /apply 1 day/i }),
        );

        expect(
            await screen.findByText("The plan could not be applied."),
        ).toBeInTheDocument();
        expect(screen.getByText("The plan changed since the preview.")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /refresh preview/i }),
        ).toBeInTheDocument();
        expect(onApplied).not.toHaveBeenCalled();
        expect(onOpenChange).not.toHaveBeenCalled();
    });
});
