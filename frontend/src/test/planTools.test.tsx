import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PlanTools } from "@/components/PlanTools";
import { WeightsEditor } from "@/components/WeightsEditor";
import { summariseChanges } from "@/lib/planDiff";
import { declineSentence, declineSummary, relaxationSentence } from "@/lib/declines";
import type { DailySchedule } from "@/types";

const getSchedule = vi.fn();
const reoptimize = vi.fn();
const commitDay = vi.fn();
const releaseSession = vi.fn();
const forcedInclude = vi.fn();
const getObjectives = vi.fn();
const updateObjectiveWeight = vi.fn();

vi.mock("@/services/apiClient", () => ({
  apiClient: {
    schedule: {
      getSchedule: (...args: unknown[]) => getSchedule(...args),
      reoptimize: (...args: unknown[]) => reoptimize(...args),
      commitDay: (...args: unknown[]) => commitDay(...args),
      releaseSession: (...args: unknown[]) => releaseSession(...args),
    },
    optimization: {
      forcedInclude: (...args: unknown[]) => forcedInclude(...args),
    },
    behaviors: {
      getObjectives: (...args: unknown[]) => getObjectives(...args),
      updateObjectiveWeight: (...args: unknown[]) => updateObjectiveWeight(...args),
    },
  },
}));

function schedule(overrides: Partial<DailySchedule> = {}): DailySchedule {
  return {
    id: "run-1",
    userId: "user-1",
    date: "2026-06-08",
    totalDuration: 60,
    objectiveScores: [],
    createdAt: "2026-06-08T06:00:00Z",
    declines: [
      { behaviorId: "b-2", behaviorName: "Strength", reason: "over_capacity" },
    ],
    scheduledBehaviors: [
      {
        id: "s-1",
        behaviorId: "b-1",
        behavior: { id: "b-1", name: "Deep work" } as never,
        scheduledDate: "2026-06-08",
        timeSlot: "flexible",
        startTime: "09:00",
        endTime: "10:00",
        duration: 60,
        isCompleted: false,
      },
    ],
    ...overrides,
  } as DailySchedule;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("plan changes", () => {
  it("describes kept, moved and dropped sessions by id", () => {
    const before = [
      { id: "a", behaviorId: "1", startTime: "09:00", duration: 60, behavior: { name: "Deep work" } },
      { id: "b", behaviorId: "2", startTime: "13:00", duration: 30, behavior: { name: "Lunch" } },
      { id: "c", behaviorId: "3", startTime: "18:00", duration: 45, behavior: { name: "Gym" } },
    ];
    const after = [
      { id: "a", behaviorId: "1", startTime: "09:00", duration: 60, behavior: { name: "Deep work" } },
      { id: "b", behaviorId: "2", startTime: "12:30", duration: 30, behavior: { name: "Lunch" } },
    ];
    const changes = summariseChanges(before, after);
    expect(changes.kept).toHaveLength(1);
    expect(changes.moved).toHaveLength(1);
    expect(changes.dropped).toHaveLength(1);
    expect(changes.sentences.join(" ")).toContain("Lunch to 12:30");
    expect(changes.sentences.join(" ")).toContain("Gym");
    expect(changes.sentences.join(" ")).toContain("kept as they were");
  });

  it("says plainly when nothing moved", () => {
    const same = [{ id: "a", behaviorId: "1", startTime: "09:00", duration: 60 }];
    expect(summariseChanges(same, same).sentences[0]).toContain("Nothing moved");
  });
});

describe("decline reasons", () => {
  it("translates every shipped reason code", () => {
    expect(declineSentence("no_fit")).toContain("No free stretch");
    expect(declineSentence("over_capacity")).toContain("day was full");
    expect(declineSentence("something_new")).toContain("did not give a reason");
  });

  it("summarises a list", () => {
    expect(declineSummary([])).toContain("Everything");
    expect(declineSummary([{ behaviorId: "1", behaviorName: "A", reason: "no_fit" }])).toContain("One habit");
  });

  it("phrases the cost of fitting a habit", () => {
    expect(
      relaxationSentence([{ behaviorName: "Lunch", minutes: 30 }], -12.5),
    ).toContain("give up Lunch (30 min)");
    expect(relaxationSentence([], 4)).toContain("without moving anything");
  });
});

describe("PlanTools", () => {
  it("re-plans and explains what changed", async () => {
    reoptimize.mockResolvedValue({ data: { new_run_id: "run-2" } });
    getSchedule.mockResolvedValue({
      data: schedule({
        scheduledBehaviors: [
          {
            id: "s-1",
            behaviorId: "b-1",
            behavior: { id: "b-1", name: "Deep work" } as never,
            scheduledDate: "2026-06-08",
            timeSlot: "flexible",
            startTime: "10:00",
            endTime: "11:00",
            duration: 60,
            isCompleted: false,
          },
        ],
        declines: [],
      }),
    });
    const onChanged = vi.fn();
    render(<PlanTools schedule={schedule()} date="2026-06-08" onChanged={onChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /re-plan the rest of my day/i }));

    await waitFor(() => expect(reoptimize).toHaveBeenCalled());
    expect(await screen.findByText(/What changed/i)).toBeInTheDocument();
    expect(screen.getByText(/Deep work to 10:00/)).toBeInTheDocument();
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("shows declined habits with a sentence and the cost of fitting them", async () => {
    forcedInclude.mockResolvedValue({
      data: {
        fits: true,
        forced: [],
        displaced: [{ behaviorId: "b-1", behaviorName: "Deep work", reason: "over_capacity", minutes: 60 }],
        relaxations: [],
        objectiveChange: -24,
        seconds: 0.2,
      },
    });
    render(<PlanTools schedule={schedule()} date="2026-06-08" onChanged={vi.fn()} />);

    expect(screen.getByText("Strength")).toBeInTheDocument();
    expect(screen.getByText(/day was full/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /what would it cost/i }));

    expect(await screen.findByText(/give up Deep work \(60 min\)/)).toBeInTheDocument();
    expect(forcedInclude).toHaveBeenCalledWith(["b-2"], "2026-06-08");
  });

  it("releases a session through the API", async () => {
    releaseSession.mockResolvedValue({ data: {} });
    getSchedule.mockResolvedValue({ data: schedule() });
    render(<PlanTools schedule={schedule()} date="2026-06-08" onChanged={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /^release$/i }));
    await waitFor(() => expect(releaseSession).toHaveBeenCalledWith("s-1"));
  });

  it("commits the day", async () => {
    commitDay.mockResolvedValue({ message: "Baseline committed" });
    render(<PlanTools schedule={schedule()} date="2026-06-08" onChanged={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /commit \/ start my day/i }));
    await waitFor(() => expect(commitDay).toHaveBeenCalled());
    expect(await screen.findByText(/Baseline committed/)).toBeInTheDocument();
  });
});

describe("WeightsEditor", () => {
  it("loads weights and saves a normalised value", async () => {
    getObjectives.mockResolvedValue({
      data: [
        { id: "o-1", name: "health", weight: 0.5 },
        { id: "o-2", name: "learning", weight: 0.5 },
      ],
    });
    updateObjectiveWeight.mockResolvedValue({
      data: [
        { id: "o-1", name: "health", weight: 0.75 },
        { id: "o-2", name: "learning", weight: 0.25 },
      ],
    });

    render(<WeightsEditor />);

    expect(await screen.findByText("health")).toBeInTheDocument();
    expect(screen.getAllByText("50%")).toHaveLength(2);

    const sliders = screen.getAllByRole("slider");
    fireEvent.change(sliders[0], { target: { value: "75" } });
    fireEvent.click(screen.getAllByRole("button", { name: /save/i })[0]);

    await waitFor(() => expect(updateObjectiveWeight).toHaveBeenCalledWith("o-1", 0.75));
    expect(await screen.findByText(/rescaled the rest/i)).toBeInTheDocument();
  });
});
