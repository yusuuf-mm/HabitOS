import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { WeekPlanDialog } from "../components/WeekPlanDialog";
import { apiClient } from "@/services/apiClient";
import { addDays, localISODate, mondayOf } from "@/lib/localDate";

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

function nextWeekStart(): string {
    return localISODate(addDays(mondayOf(new Date()), 7));
}

function dateAt(weekStart: string, offset: number): string {
    return localISODate(addDays(new Date(`${weekStart}T12:00:00`), offset));
}

function shortRangeDate(date: string): string {
    return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", {
        weekday: "short",
        day: "numeric",
    });
}

function day(weekStart: string, offset: number, overrides: Record<string, unknown> = {}) {
    const date = dateAt(weekStart, offset);
    return {
        date,
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
        resultHash: `hash-${date}`,
        ...overrides,
    };
}

function previewResponse(
    weekStart: string,
    days: ReturnType<typeof day>[],
    skippedDays: Array<{ date: string; code: string; message: string }> = [],
) {
    return {
        data: {
            weekStart,
            rangeStart: days[0]?.date ?? weekStart,
            rangeEnd: days[days.length - 1]?.date ?? weekStart,
            generatedAt: "2026-06-08T12:00:00Z",
            fingerprint: "fp-1",
            days,
            skippedDays,
        },
        success: true,
    };
}

function applyResponse(
    weekStart: string,
    appliedDays: number,
    skippedDays: Array<{ date: string; code: string; message: string }> = [],
) {
    return {
        data: {
            weekStart,
            rangeStart: weekStart,
            rangeEnd: dateAt(weekStart, 6),
            fingerprint: "fp-1",
            appliedDays,
            days: [],
            skippedDays,
        },
        success: true,
    };
}

function renderDialog(
    weekStart = nextWeekStart(),
    onApplied = vi.fn(),
    onOpenChange = vi.fn(),
) {
    render(
        <WeekPlanDialog
            open
            onOpenChange={onOpenChange}
            weekStart={weekStart}
            onApplied={onApplied}
        />,
    );
    return { onApplied, onOpenChange };
}

describe("WeekPlanDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("states the exact range and an honest planning count while solving", async () => {
        const weekStart = nextWeekStart();
        const rangeEnd = dateAt(weekStart, 6);
        previewWeek.mockReturnValue(new Promise(() => { }));

        renderDialog(weekStart);

        const dialog = screen.getByRole("dialog", { name: /plan my week/i });
        expect(dialog).toHaveTextContent(
            `Planning ${shortRangeDate(weekStart)} to ${shortRangeDate(rangeEnd)}`,
        );
        expect(screen.getByRole("status")).toHaveTextContent("Planning 7 days...");
        expect(screen.queryByText(/progress/i)).not.toBeInTheDocument();
    });

    it("enables apply with one solved day and labels failures Unavailable", async () => {
        const weekStart = nextWeekStart();
        const busyDate = dateAt(weekStart, 1);
        previewWeek.mockResolvedValue(
            previewResponse(
                weekStart,
                [
                    day(weekStart, 0),
                    day(weekStart, 1, {
                        available: false,
                        error: {
                            code: "solver_busy",
                            message: "The solver is busy on this day.",
                        },
                        sessionsAfter: null,
                        minutesAfter: null,
                    }),
                ],
                [
                    {
                        date: busyDate,
                        code: "solver_busy",
                        message: "The solver is busy on this day.",
                    },
                ],
            ),
        );

        renderDialog(weekStart);

        expect(await screen.findByText("1 of 2 days can be planned.")).toBeInTheDocument();
        expect(screen.getByText("1 day unavailable")).toBeInTheDocument();
        expect(screen.getByText("The solver is busy on this day.")).toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        const unavailableSection = screen
            .getByText("The solver is busy on this day.")
            .closest("section");
        expect(unavailableSection).not.toHaveTextContent("No changes to this day.");
        expect(
            (screen.getByRole("button", { name: /apply 1 day/i }) as HTMLButtonElement)
                .disabled,
        ).toBe(false);
    });

    it("applies only solved dates with their hashes and reports skipped days", async () => {
        const weekStart = nextWeekStart();
        const skippedDate = dateAt(weekStart, 2);
        previewWeek.mockResolvedValue(
            previewResponse(
                weekStart,
                [
                    day(weekStart, 0),
                    day(weekStart, 1),
                    day(weekStart, 2, {
                        available: false,
                        error: {
                            code: "infeasible",
                            message: "No feasible plan on this date.",
                        },
                        sessionsAfter: null,
                        minutesAfter: null,
                    }),
                ],
                [
                    {
                        date: skippedDate,
                        code: "infeasible",
                        message: "No feasible plan on this date.",
                    },
                ],
            ),
        );
        applyWeek.mockResolvedValue(
            applyResponse(weekStart, 2, [
                {
                    date: skippedDate,
                    code: "infeasible",
                    message: "No feasible plan on this date.",
                },
            ]),
        );
        const { onApplied } = renderDialog(weekStart);

        fireEvent.click(
            await screen.findByRole("button", { name: /apply 2 days/i }),
        );

        await waitFor(() =>
            expect(applyWeek).toHaveBeenCalledWith({
                weekStart,
                fingerprint: "fp-1",
                dates: [dateAt(weekStart, 0), dateAt(weekStart, 1)],
                expectedResults: {
                    [dateAt(weekStart, 0)]: `hash-${dateAt(weekStart, 0)}`,
                    [dateAt(weekStart, 1)]: `hash-${dateAt(weekStart, 1)}`,
                },
            }),
        );
        expect(await screen.findByText("Week planned")).toBeInTheDocument();
        expect(screen.getByText(/2 days applied/i)).toBeInTheDocument();
        expect(screen.getByText("1 day skipped")).toBeInTheDocument();
        expect(screen.getByText(new RegExp(`No feasible plan`))).toBeInTheDocument();
        expect(onApplied).toHaveBeenCalled();
    });

    it("keeps the preview and offers a refresh after a changed result diff", async () => {
        const weekStart = nextWeekStart();
        previewWeek.mockResolvedValue(previewResponse(weekStart, [day(weekStart, 0)]));
        applyWeek.mockRejectedValue({
            code: "week_plan_changed",
            message: "The preview no longer matches the current plan.",
            detail: { skippedDays: [] },
        });
        const { onApplied, onOpenChange } = renderDialog(weekStart);

        fireEvent.click(
            await screen.findByRole("button", { name: /apply 1 day/i }),
        );

        expect(
            await screen.findByText("This preview is out of date."),
        ).toBeInTheDocument();
        expect(
            screen.getByText("The preview no longer matches the current plan."),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /refresh preview/i }),
        ).toBeInTheDocument();
        expect(onApplied).not.toHaveBeenCalled();
        expect(onOpenChange).not.toHaveBeenCalled();
    });

    it("uses removed-from-draft wording for sessions the draft drops", async () => {
        const weekStart = nextWeekStart();
        previewWeek.mockResolvedValue(
            previewResponse(weekStart, [
                day(weekStart, 0, {
                    sessionsBefore: 1,
                    sessionsAfter: 0,
                    dropped: [
                        {
                            plannedSessionId: "old-1",
                            behaviorId: "b-1",
                            behaviorName: "Morning Walk",
                            startTime: "09:00",
                            endTime: "09:30",
                            duration: 30,
                        },
                    ],
                }),
            ]),
        );

        renderDialog(weekStart);

        expect(
            await screen.findByText("Removed from draft · 1"),
        ).toBeInTheDocument();
        expect(screen.queryByText(/^Dropped/)).not.toBeInTheDocument();
        expect(screen.queryByText(/system dropped/i)).not.toBeInTheDocument();
    });

    it("shows an explicit error state when preview fails and can retry", async () => {
        previewWeek.mockRejectedValue(new Error("network down"));

        renderDialog();

        expect(await screen.findByText("Week preview unavailable")).toBeInTheDocument();
        expect(screen.getByText("network down")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /try again/i }));
        await waitFor(() => expect(previewWeek).toHaveBeenCalledTimes(2));
    });
});
