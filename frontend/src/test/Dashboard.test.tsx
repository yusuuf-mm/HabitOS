import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Dashboard from "../pages/Dashboard";
import { BrowserRouter } from "react-router-dom";
import { apiClient } from "@/services/apiClient";
import { WeekCalendar } from "@/components/WeekCalendar";
import { DayDetailPanel } from "@/components/DayDetailPanel";
import { HelperOrb } from "@/components/HelperOrb";
import { PlanHealthRail } from "@/components/PlanHealthRail";
import { InsightTiles } from "@/components/InsightTiles";
import { LifeMap } from "@/components/LifeMap";
import type { RangeEntry, SessionBlock, WeekDayData } from "@/types/dashboard";
import type { DashboardSummary } from "@/types";
import { addDays, localISODate, mondayOf } from "@/lib/localDate";

const {
    helperGetStatus,
    helperDraft,
    helperConfirm,
    itemsGet,
    itemsUpdate,
    itemsRemove,
    itemsGetDay,
    itemsGetRange,
    markBehaviorComplete,
    markBehaviorIncomplete,
    releaseSession,
    scheduleGetSchedule,
    optimizationHistory,
    previewWeek,
    applyWeek,
    analyticsSummary,
    analyticsStats,
    analyticsSeries,
    analyticsGet,
} = vi.hoisted(() => ({
    helperGetStatus: vi.fn(),
    helperDraft: vi.fn(),
    helperConfirm: vi.fn(),
    itemsGet: vi.fn(),
    itemsUpdate: vi.fn(),
    itemsRemove: vi.fn(),
    itemsGetDay: vi.fn(),
    itemsGetRange: vi.fn(),
    markBehaviorComplete: vi.fn(),
    markBehaviorIncomplete: vi.fn(),
    releaseSession: vi.fn(),
    scheduleGetSchedule: vi.fn(),
    optimizationHistory: vi.fn(),
    previewWeek: vi.fn(),
    applyWeek: vi.fn(),
    analyticsSummary: vi.fn(),
    analyticsStats: vi.fn(),
    analyticsSeries: vi.fn(),
    analyticsGet: vi.fn(),
}));

// Mock apiClient
vi.mock("@/services/apiClient", () => ({
    apiClient: {
        analytics: {
            getDashboardSummary: analyticsSummary,
            getStats: analyticsStats,
            getSeries: analyticsSeries,
            getAnalytics: analyticsGet,
        },
        helper: {
            getStatus: helperGetStatus,
            draft: helperDraft,
            confirm: helperConfirm,
        },
        items: {
            get: itemsGet,
            update: itemsUpdate,
            remove: itemsRemove,
            getDay: itemsGetDay,
            getRange: itemsGetRange,
        },
        schedule: {
            getSchedule: scheduleGetSchedule,
            markBehaviorComplete,
            markBehaviorIncomplete,
            releaseSession,
        },
        optimization: {
            getOptimizationHistory: optimizationHistory,
            previewWeek,
            applyWeek,
        },
    },
    helperApi: {
        getStatus: helperGetStatus,
        draft: helperDraft,
        confirm: helperConfirm,
    },
    itemsApi: {
        get: itemsGet,
        update: itemsUpdate,
        remove: itemsRemove,
        getDay: itemsGetDay,
        getRange: itemsGetRange,
    },
    scheduleApi: {
        getSchedule: scheduleGetSchedule,
        markBehaviorComplete,
        markBehaviorIncomplete,
        releaseSession,
    },
    optimizationApi: {
        getOptimizationHistory: optimizationHistory,
        previewWeek,
        applyWeek,
    },
    analyticsApi: {
        getDashboardSummary: analyticsSummary,
        getStats: analyticsStats,
        getSeries: analyticsSeries,
        getAnalytics: analyticsGet,
    },
}));

// Defaults the dashboard page relies on at mount; individual tests override.
itemsGetRange.mockResolvedValue([]);
itemsGetDay.mockResolvedValue([]);
scheduleGetSchedule.mockRejectedValue(new Error("no schedule"));
optimizationHistory.mockResolvedValue({ data: [] });
analyticsSeries.mockResolvedValue([]);
helperGetStatus.mockResolvedValue({ configured: false, fastModel: "", strongModel: "" });

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

function weekPreviewResponse() {
    const days = Array.from({ length: 7 }, (_, index) => {
        const date = `2026-06-${String(8 + index).padStart(2, "0")}`;
        return {
            date,
            mode: "full" as const,
            available: true,
            solverStatus: "optimal",
            sessionsBefore: 0,
            sessionsAfter: index === 0 ? 1 : 0,
            minutesBefore: 0,
            minutesAfter: index === 0 ? 30 : 0,
            added: index === 0
                ? [{
                    plannedSessionId: "s-new",
                    behaviorId: "b-1",
                    behaviorName: "Morning Walk",
                    startTime: "09:00",
                    endTime: "09:30",
                    duration: 30,
                }]
                : [],
            moved: [],
            dropped: [],
            declines: [],
            resultHash: `hash-${date}`,
        };
    });
    return {
        data: {
            weekStart: "2026-06-08",
            rangeStart: "2026-06-08",
            rangeEnd: "2026-06-14",
            generatedAt: "2026-06-08T12:00:00Z",
            fingerprint: "fp-1",
            days,
            skippedDays: [],
        },
        success: true,
    };
}

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

    it("disables Plan my week when the displayed week is entirely past", async () => {
        analyticsSummary.mockResolvedValue(mockSummaryData);

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>,
        );

        expect(await screen.findByText("Kept my plan")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /plan my week/i })).toBeEnabled();

        fireEvent.click(screen.getByRole("button", { name: "Previous week" }));

        const planButton = screen.getByRole("button", { name: /plan my week/i });
        expect(planButton).toBeDisabled();
        expect(planButton).toHaveAttribute("title", "This week is entirely in the past.");
    });

    it("renders stats after data loads", async () => {
        (apiClient.analytics.getDashboardSummary as Mock).mockResolvedValue(mockSummaryData);

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>
        );

        // Wait for loading to finish and the plan-health rail to show
        await waitFor(() => {
            expect(screen.getByText("Kept my plan")).toBeInTheDocument();
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

function session(overrides: Partial<SessionBlock> = {}): SessionBlock {
    return {
        id: "s-1",
        title: "Deep work",
        startTime: "09:00",
        endTime: "10:00",
        duration: 60,
        behaviorName: "Deep work",
        completed: false,
        ...overrides,
    };
}

function commitment(overrides: Partial<RangeEntry> = {}): RangeEntry {
    return {
        date: "2026-06-08",
        itemId: "c-1",
        kind: "commitment",
        title: "Hospital",
        isPrivate: false,
        startTime: "08:00",
        endTime: "09:00",
        warnings: [],
        ...overrides,
    };
}

function deadline(overrides: Partial<RangeEntry> = {}): RangeEntry {
    return {
        date: "2026-06-08",
        itemId: "d-1",
        kind: "deadline",
        title: "Quarterly report",
        isPrivate: false,
        dueOn: "2026-06-08",
        warnings: [],
        ...overrides,
    };
}

function emptyDay(date: string): WeekDayData {
    return { date, sessions: [], commitments: [], deadlines: [] };
}

function weekDays(): WeekDayData[] {
    return [
        {
            date: "2026-06-08",
            sessions: [session()],
            commitments: [commitment()],
            deadlines: [deadline()],
        },
        {
            date: "2026-06-09",
            sessions: [session({ id: "s-2", title: "Gym", startTime: "18:00", endTime: "19:00" })],
            commitments: [],
            deadlines: [],
        },
        emptyDay("2026-06-10"),
        emptyDay("2026-06-11"),
        emptyDay("2026-06-12"),
        emptyDay("2026-06-13"),
        emptyDay("2026-06-14"),
    ];
}

function summaryWith(
    stats: Partial<DashboardSummary["stats"]> = {},
): DashboardSummary {
    return {
        stats: {
            totalBehaviors: 4,
            activeBehaviors: 4,
            totalOptimizationRuns: 1,
            completionRate: null,
            released: 0,
            systemDropped: 0,
            completionRateVsFeasible: null,
            averageScore: 0,
            streakDays: 0,
            ...stats,
        },
        recentOptimizations: [],
        recentBehaviors: [],
        todaySchedule: [],
    };
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe("WeekCalendar", () => {
    it("renders 7 day headers and three block types distinguishably", () => {
        const days = weekDays();
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={days}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        // Seven day headers, one per day.
        expect(
            screen.getAllByRole("button", { name: /open agenda for/i }),
        ).toHaveLength(7);

        // A session shows its title and its time text.
        expect(
            screen.getByRole("button", {
                name: "Monday 09:00 to 10:00, Deep work, planned session",
            }),
        ).toBeInTheDocument();
        expect(screen.getByText("Deep work")).toBeInTheDocument();
        expect(screen.getByText("09:00–10:00")).toBeInTheDocument();

        // A commitment reads as a fixed block.
        expect(
            screen.getByRole("button", {
                name: "Monday 08:00 to 09:00, Hospital, fixed commitment",
            }),
        ).toBeInTheDocument();
        expect(screen.getByText(/fixed 08:00–09:00/i)).toBeInTheDocument();

        // A deadline is flagged by day and title.
        expect(
            screen.getByRole("button", {
                name: "Monday, Jun 8, deadline Quarterly report",
            }),
        ).toBeInTheDocument();
    });

    it("labels future draft days differently from today's committed plan", () => {
        const today = localISODate(new Date());
        const nextMonday = localISODate(addDays(mondayOf(new Date()), 7));
        const draftDate = localISODate(addDays(new Date(`${nextMonday}T12:00:00`), 1));
        const days: WeekDayData[] = [
            { ...emptyDay(today), planSource: "committed" },
            { ...emptyDay(draftDate), planSource: "draft" },
        ];

        render(
            <WeekCalendar
                weekStart={mondayOf(new Date())}
                days={days}
                selectedDate={today}
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        expect(
            screen.getByRole("button", { name: /committed plan/i }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /draft plan/i }),
        ).toBeInTheDocument();
        expect(screen.getAllByText("draft plan").length).toBeGreaterThan(0);
        expect(screen.getAllByText("committed plan").length).toBeGreaterThan(0);
    });

    it("moves focus to the next day's block with ArrowRight", () => {
        const days = weekDays().slice(0, 2);
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={days}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        const first = screen.getByRole("button", {
            name: /deep work, planned session/i,
        });
        const second = screen.getByRole("button", {
            name: /gym, planned session/i,
        });

        first.focus();
        fireEvent.keyDown(first, { key: "ArrowRight" });

        expect(document.activeElement).toBe(second);
    });

    it("opens the block on Enter", () => {
        const days = weekDays().slice(0, 2);
        const onOpenBlock = vi.fn();
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={days}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={onOpenBlock}
            />,
        );

        const block = screen.getByRole("button", {
            name: /deep work, planned session/i,
        });
        block.focus();
        // Browsers turn Enter on a focused button into a click; jsdom does
        // not, so dispatch the key press and then the click it would produce.
        fireEvent.keyDown(block, { key: "Enter", code: "Enter" });
        fireEvent.click(block);

        expect(onOpenBlock).toHaveBeenCalledWith({
            type: "session",
            day: days[0],
            session: days[0].sessions[0],
        });
    });

    it("distinguishes released and completed sessions from pending ones", () => {
        const day: WeekDayData = {
            ...emptyDay("2026-06-08"),
            sessions: [
                session({ id: "s-done", title: "Finished work", completed: true }),
                session({
                    id: "s-released",
                    title: "Withdrawn work",
                    startTime: "11:00",
                    endTime: "12:00",
                    releasedAt: "2026-06-08T10:00:00Z",
                }),
                session({
                    id: "s-pending",
                    title: "Upcoming work",
                    startTime: "13:00",
                    endTime: "14:00",
                }),
            ],
        };
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={[day]}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        expect(
            screen.getByRole("button", {
                name: "Monday 09:00 to 10:00, Finished work, planned session, completed",
            }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", {
                name: "Monday 11:00 to 12:00, Withdrawn work, planned session, released",
            }),
        ).toBeInTheDocument();
        expect(screen.getByText(/11:00–12:00 · Released/)).toBeInTheDocument();
        expect(screen.getByText(/09:00–10:00 · Done/)).toBeInTheDocument();
        // A normal session keeps the original accessible name and time text.
        expect(
            screen.getByRole("button", {
                name: "Monday 13:00 to 14:00, Upcoming work, planned session",
            }),
        ).toBeInTheDocument();
    });

    it("moves focus between blocks in a day with ArrowDown and ArrowUp", () => {
        const day: WeekDayData = {
            ...emptyDay("2026-06-08"),
            sessions: [
                session({ id: "s-a", title: "First block" }),
                session({ id: "s-b", title: "Second block", startTime: "11:00", endTime: "12:00" }),
            ],
        };
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={[day]}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        const first = screen.getByRole("button", { name: /first block, planned session/i });
        const second = screen.getByRole("button", { name: /second block, planned session/i });
        first.focus();
        fireEvent.keyDown(first, { key: "ArrowDown" });
        expect(document.activeElement).toBe(second);
        fireEvent.keyDown(second, { key: "ArrowUp" });
        expect(document.activeElement).toBe(first);
    });

    it("labels a day whose schedule failed instead of claiming it is empty", () => {
        render(
            <WeekCalendar
                weekStart={new Date("2026-06-08T00:00:00")}
                days={[{ ...emptyDay("2026-06-08"), unavailable: true }]}
                selectedDate="2026-06-08"
                onSelectDate={vi.fn()}
                onOpenBlock={vi.fn()}
            />,
        );

        expect(
            screen.getByRole("button", { name: /open agenda for monday, jun 8 \(unavailable\)/i }),
        ).toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(screen.queryByText("Nothing planned")).not.toBeInTheDocument();
    });
});

describe("DayDetailPanel commitment", () => {
    const day = weekDays()[0];
    const item = commitment({ warnings: ["Overlaps Deep work."] });

    it("shows warnings and deletes after confirmation", async () => {
        itemsGet.mockResolvedValue({
            id: "c-1",
            kind: "commitment",
            title: "Hospital",
            isPrivate: false,
            startTime: "08:00",
            startDate: "2026-06-08",
        });
        itemsRemove.mockResolvedValue({ deleted: true });
        const onClose = vi.fn();
        render(
            <DayDetailPanel
                block={{ type: "commitment", day, item }}
                onClose={onClose}
                onChanged={vi.fn()}
            />,
        );

        expect(await screen.findByText("Overlaps Deep work.")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
        expect(await screen.findByText("Are you sure?")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));
        await waitFor(() => expect(itemsRemove).toHaveBeenCalledWith("c-1"));
        await waitFor(() => expect(onClose).toHaveBeenCalled());
    });

    it("toggles private with update", async () => {
        itemsGet.mockResolvedValue({
            id: "c-1",
            kind: "commitment",
            title: "Hospital",
            isPrivate: false,
        });
        itemsUpdate.mockResolvedValue({ id: "c-1", isPrivate: true });
        render(
            <DayDetailPanel
                block={{ type: "commitment", day, item }}
                onClose={vi.fn()}
                onChanged={vi.fn()}
            />,
        );

        fireEvent.click(
            await screen.findByRole("button", { name: /make private/i }),
        );
        await waitFor(() =>
            expect(itemsUpdate).toHaveBeenCalledWith("c-1", { isPrivate: true }),
        );
    });
});

describe("DayDetailPanel session and agenda", () => {
    const day = weekDays()[0];

    it("updates its own status after marking a session complete", async () => {
        markBehaviorComplete.mockResolvedValue({});
        render(
            <DayDetailPanel
                block={{ type: "session", day, session: session({ id: "s-1" }) }}
                onClose={vi.fn()}
                onChanged={vi.fn()}
            />,
        );

        expect(screen.getByText("Planned")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /mark complete/i }));
        await waitFor(() => expect(screen.getByText("Completed")).toBeInTheDocument());
        expect(screen.queryByText("Planned")).not.toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /mark incomplete/i }),
        ).toBeInTheDocument();
    });

    it("does not offer completion actions for a released session", () => {
        render(
            <DayDetailPanel
                block={{
                    type: "session",
                    day,
                    session: session({ releasedAt: "2026-06-08T10:00:00Z" }),
                }}
                onClose={vi.fn()}
                onChanged={vi.fn()}
            />,
        );

        expect(screen.getByText("Released")).toBeInTheDocument();
        expect(screen.getByText(/withdrawn before it started/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /mark complete/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /^release$/i })).not.toBeInTheDocument();
    });

    it("keeps the panel open when a delete fails", async () => {
        itemsGet.mockResolvedValue({
            id: "c-1",
            kind: "commitment",
            title: "Hospital",
            isPrivate: false,
        });
        itemsRemove.mockRejectedValue(new Error("denied"));
        const onClose = vi.fn();
        render(
            <DayDetailPanel
                block={{ type: "commitment", day, item: commitment() }}
                onClose={onClose}
                onChanged={vi.fn()}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: /^delete$/i }));
        fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));
        await waitFor(() => expect(screen.getByText("denied")).toBeInTheDocument());
        expect(onClose).not.toHaveBeenCalled();
    });

    it("says Delete series for a recurring item", async () => {
        itemsGet.mockResolvedValue({
            id: "c-1",
            kind: "commitment",
            title: "Hospital",
            isPrivate: false,
            recurrence: "weekly",
        });
        render(
            <DayDetailPanel
                block={{ type: "commitment", day, item: commitment() }}
                onClose={vi.fn()}
                onChanged={vi.fn()}
            />,
        );

        fireEvent.click(await screen.findByRole("button", { name: /delete series/i }));
        expect(await screen.findByText("Delete this whole series?")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /confirm delete series/i }),
        ).toBeInTheDocument();
    });

    it("opens an agenda row in the same panel", () => {
        const onOpenBlock = vi.fn();
        render(
            <DayDetailPanel
                block={{ type: "day", day }}
                onClose={vi.fn()}
                onChanged={vi.fn()}
                onOpenBlock={onOpenBlock}
            />,
        );

        fireEvent.click(screen.getByRole("button", { name: /deep work \(session\)/i }));
        expect(onOpenBlock).toHaveBeenCalledWith({
            type: "session",
            day,
            session: day.sessions[0],
        });
    });
});

describe("HelperOrb", () => {
    it("shows the not-switched-on explanation when unconfigured", async () => {
        helperGetStatus.mockResolvedValue({
            configured: false,
            fastModel: "",
            strongModel: "",
        });
        render(<HelperOrb />);

        // The orb itself reports the state; the explanation appears in the sheet.
        expect(
            await screen.findByRole("button", { name: /plan assistant — unavailable/i }),
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /plan assistant/i }));
        expect(
            await screen.findByText(/isn't switched on for this workspace yet/i),
        ).toBeInTheDocument();
    });

    it("opens the sheet with the transcript field when configured", async () => {
        helperGetStatus.mockResolvedValue({
            configured: true,
            fastModel: "fast",
            strongModel: "strong",
        });
        render(<HelperOrb />);

        fireEvent.click(
            await screen.findByRole("button", { name: /plan assistant/i }),
        );

        expect(
            screen.getByRole("dialog", { name: /plan assistant/i }),
        ).toBeInTheDocument();
        expect(
            await screen.findByLabelText(/what would you like to plan/i),
        ).toBeInTheDocument();
    });
});

describe("PlanHealthRail", () => {
    it("renders dashes and the no-finished-days line when rates are null", () => {
        render(
            <PlanHealthRail
                summary={summaryWith({ released: 2, systemDropped: 1 })}
                rangeDays={7}
                onRangeChange={vi.fn()}
            />,
        );

        expect(screen.getAllByText("—")).toHaveLength(2);
        expect(
            screen.getByText(/no finished days yet in this range/i),
        ).toBeInTheDocument();
        expect(screen.getByText("2 released · 1 dropped")).toBeInTheDocument();
    });

    it("renders both rates and the released/dropped line when rates exist", () => {
        render(
            <PlanHealthRail
                summary={summaryWith({
                    completionRate: 0.8,
                    completionRateVsFeasible: 0.5,
                    released: 3,
                    systemDropped: 1,
                })}
                rangeDays={30}
                onRangeChange={vi.fn()}
            />,
        );

        expect(screen.getByText("80%")).toBeInTheDocument();
        expect(screen.getByText("50%")).toBeInTheDocument();
        expect(screen.getByText("3 released · 1 dropped")).toBeInTheDocument();
        expect(
            screen.queryByText(/no finished days yet in this range/i),
        ).not.toBeInTheDocument();
    });
});

describe("InsightTiles", () => {
    const series = [
        {
            date: "2026-06-08",
            completed: 2,
            baseline: 0,
            released: 0,
            dropped: 0,
            completionRate: 1,
            plannedMinutes: 90,
        },
        {
            date: "2026-06-09",
            completed: 3,
            baseline: 0,
            released: 0,
            dropped: 0,
            completionRate: 1,
            plannedMinutes: 120,
        },
    ];

    it("shows range totals, not the latest partial day", () => {
        render(<InsightTiles series={series} days={7} />);

        expect(screen.getByText("5")).toBeInTheDocument();
        expect(screen.getByText("210")).toBeInTheDocument();
        expect(screen.getAllByText(/across 7 days/i)).toHaveLength(2);
    });

    it("never presents a failed request as an empty range", () => {
        render(<InsightTiles series={[]} days={30} failed />);

        expect(
            screen.getAllByText("Trend data could not be loaded."),
        ).toHaveLength(2);
        expect(screen.queryByText("No data yet")).not.toBeInTheDocument();
    });
});

describe("LifeMap", () => {
    it("renders each objective's share from this week's plans", () => {
        render(
            <LifeMap
                objectives={[
                    { name: "Health", value: 60, share: 0.6 },
                    { name: "Learning", value: 40, share: 0.4 },
                ]}
            />,
        );

        expect(screen.getByText("Health: 60%")).toBeInTheDocument();
        expect(screen.getByText("Learning: 40%")).toBeInTheDocument();
        expect(screen.getByRole("img", { name: /objectives for this week/i })).toBeInTheDocument();
    });

    it("says when the week's plans could not be loaded", () => {
        render(<LifeMap objectives={[]} unavailable />);

        expect(screen.getByText(/could not be loaded/i)).toBeInTheDocument();
    });
});

describe("Dashboard data sources", () => {
    afterEach(() => {
        // Restore the module-level defaults; mock implementations survive
        // clearAllMocks and would leak into later suites.
        scheduleGetSchedule.mockRejectedValue(new Error("no schedule"));
        optimizationHistory.mockResolvedValue({ data: [] });
    });

    it("shows a failure banner instead of rendering a failed request as empty data", async () => {
        analyticsSummary.mockResolvedValue(mockSummaryData);
        analyticsSeries.mockRejectedValueOnce(new Error("network"));

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>,
        );

        expect(await screen.findByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/some dashboard data could not be loaded/i)).toBeInTheDocument();
        expect(screen.getByText(/trend data is unavailable/i)).toBeInTheDocument();
        expect(screen.getAllByText("Trend data could not be loaded.")).toHaveLength(2);
        expect(screen.queryByText("No data yet")).not.toBeInTheDocument();
    });

    it("derives the life map from the week's resolved plans, not the history endpoint", async () => {
        analyticsSummary.mockResolvedValue(mockSummaryData);
        analyticsSeries.mockResolvedValue([]);
        optimizationHistory.mockRejectedValue(new Error("history unavailable"));
        scheduleGetSchedule.mockImplementation(async (date?: string) => ({
            data: {
                id: "sch-1",
                userId: "u-1",
                date: date ?? "2026-06-08",
                scheduledBehaviors: [],
                totalDuration: 0,
                objectiveScores: [
                    {
                        objectiveId: "o-1",
                        objectiveName: "Health",
                        contribution: 60,
                        percentage: 60,
                    },
                ],
                createdAt: "2026-06-08T00:00:00Z",
            },
            success: true,
        }));

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>,
        );

        expect(await screen.findByText("Health: 60%")).toBeInTheDocument();
        expect(optimizationHistory).not.toHaveBeenCalled();
    });

    it("previews the week from the dashboard and applies only on explicit click", async () => {
        analyticsSummary.mockResolvedValue(mockSummaryData);
        analyticsSeries.mockResolvedValue([]);
        const preview = weekPreviewResponse();
        previewWeek.mockResolvedValue(preview);
        applyWeek.mockResolvedValue({
            data: {
                weekStart: "2026-06-08",
                rangeStart: "2026-06-08",
                rangeEnd: "2026-06-14",
                fingerprint: "fp-1",
                appliedDays: 7,
                days: [],
                skippedDays: [],
            },
            success: true,
        });

        render(
            <BrowserRouter>
                <Dashboard />
            </BrowserRouter>,
        );

        expect(await screen.findByText("Kept my plan")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /plan my week/i }));

        expect(
            await screen.findByRole("dialog", { name: /plan my week/i }),
        ).toBeInTheDocument();
        expect(await screen.findByText("7 of 7 days can be planned.")).toBeInTheDocument();
        expect(previewWeek).toHaveBeenCalledWith(expect.any(String));
        expect(applyWeek).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: /apply 7 days/i }));
        const solvedDates = preview.data.days.map((entry) => entry.date);
        await waitFor(() =>
            expect(applyWeek).toHaveBeenCalledWith({
                weekStart: preview.data.weekStart,
                fingerprint: "fp-1",
                dates: solvedDates,
                expectedResults: Object.fromEntries(
                    solvedDates.map((date) => [date, `hash-${date}`]),
                ),
            }),
        );
    });
});
