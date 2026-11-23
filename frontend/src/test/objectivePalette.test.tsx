import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  ALL_OBJECTIVE_STYLES,
  contrastRatio,
  highestImpactObjective,
  resolveObjective,
} from "@/lib/objectivePalette";
import { layoutOverlaps, WeekCalendar } from "@/components/WeekCalendar";
import type { WeekDayData } from "@/types/dashboard";

const originalMatchMedia = window.matchMedia;

afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

describe("objective palette", () => {
  it("uses the highest impact score, not the first impact row", () => {
    const impacts = [
      { objectiveName: "Health", impactScore: 0.2 },
      { objectiveName: "Learning", impactScore: 0.85 },
      { objectiveName: "Wellness", impactScore: -0.4 },
    ];
    expect(highestImpactObjective(impacts)?.objectiveName).toBe("Learning");
    expect(highestImpactObjective([])).toBeUndefined();
    expect(
      highestImpactObjective([
        { objectiveName: "Health" },
        { objectiveName: "Learning", impactScore: Number.NaN },
      ]),
    ).toBeUndefined();
    expect(
      highestImpactObjective([
        { objectiveName: "Health", impactScore: 0.5 },
        { objectiveName: "Learning", impactScore: 0.5 },
      ])?.objectiveName,
    ).toBe("Health");
  });

  it("maps known objectives to fixed styles and unknown names deterministically", () => {
    expect(resolveObjective("  HEALTH ").key).toBe("health");
    expect(resolveObjective("productivity").short).toBe("PR");
    expect(resolveObjective(null).label).toBe("Unassigned");
    expect(resolveObjective("a new objective").key).toBe(resolveObjective("a new objective").key);
    expect(new Set(ALL_OBJECTIVE_STYLES.map((style) => style.shape)).size).toBe(8);
  });

  it("meets WCAG AA contrast in both themes", () => {
    for (const objective of ALL_OBJECTIVE_STYLES) {
      expect(contrastRatio(objective.light.ink, objective.light.tint), `${objective.key} light ink/tint`).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(objective.dark.ink, objective.dark.tint), `${objective.key} dark ink/tint`).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(objective.light.ink, "#FFFFFF"), `${objective.key} light ink/card`).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(objective.dark.ink, "#18181B"), `${objective.key} dark ink/card`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the CSS variables in sync with the checked palette values", () => {
    const css = readFileSync("src/index.css", "utf8");
    const declared = new Map<string, string[]>();
    for (const match of css.matchAll(/(--objective-[a-z-]+):\s*(#[0-9A-Fa-f]{6});/g)) {
      const [, name, value] = match;
      declared.set(name, [...(declared.get(name) ?? []), value.toUpperCase()]);
    }
    for (const objective of ALL_OBJECTIVE_STYLES) {
      const pairs = [
        [`--objective-${objective.key}`, objective.light.swatch, objective.dark.swatch],
        [`--objective-${objective.key}-ink`, objective.light.ink, objective.dark.ink],
        [`--objective-${objective.key}-tint`, objective.light.tint, objective.dark.tint],
      ] as const;
      for (const [name, light, dark] of pairs) {
        expect(declared.get(name), `${name} declarations`).toEqual(
          expect.arrayContaining([light.toUpperCase(), dark.toUpperCase()]),
        );
      }
    }
  });
});

describe("calendar layout", () => {
  it("assigns overlapping blocks to side-by-side columns", () => {
    const positions = layoutOverlaps([
      { key: "a", start: 540, end: 600 },
      { key: "b", start: 570, end: 630 },
      { key: "c", start: 600, end: 660 },
    ]);
    expect(positions.get("a")).toEqual({ column: 0, columns: 2 });
    expect(positions.get("b")).toEqual({ column: 1, columns: 2 });
    expect(positions.get("c")?.columns).toBe(2);
  });

  function dayWithTwoOverlaps(): WeekDayData {
    return {
      date: "2026-06-08",
      sessions: [
        {
          id: "s1",
          title: "First overlap",
          startTime: "09:00",
          endTime: "10:00",
          duration: 60,
          behaviorName: "Deep work",
          objectiveName: "Health",
          completed: false,
        },
        {
          id: "s2",
          title: "Second overlap",
          startTime: "09:30",
          endTime: "10:30",
          duration: 60,
          behaviorName: "Reading",
          objectiveName: "Learning",
          completed: false,
        },
      ],
      commitments: [],
      deadlines: [],
    };
  }

  function renderCalendar(days: WeekDayData[], selectedDate = "2026-06-08") {
    return render(
      <WeekCalendar
        weekStart={new Date("2026-06-08T00:00:00")}
        days={days}
        selectedDate={selectedDate}
        onSelectDate={vi.fn()}
        onOpenBlock={vi.fn()}
      />,
    );
  }

  it("renders overlapping sessions side by side using objective ink", () => {
    renderCalendar([dayWithTwoOverlaps()]);
    const first = screen.getByRole("button", { name: /first overlap, planned session/i });
    const second = screen.getByRole("button", { name: /second overlap, planned session/i });

    expect(first.style.left).not.toBe(second.style.left);
    expect(first.style.width).toContain("50%");
    expect(second.style.width).toContain("50%");
    expect(first).toHaveAttribute("data-objective", "health");
    expect(second).toHaveAttribute("data-objective", "learning");
    expect(first.style.height).toBe("72px");
  });

  it("shows objective colours, shapes and labels in the legend", () => {
    renderCalendar([dayWithTwoOverlaps()]);
    fireEvent.click(screen.getByRole("button", { name: /what do the shapes mean/i }));

    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("Learning")).toBeInTheDocument();
    expect(screen.getByText(/colours are fixed per objective/i)).toBeInTheDocument();
  });

  it("orders the 390px agenda chronologically and keeps objective hooks", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("max-width"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const selected: WeekDayData = {
      ...dayWithTwoOverlaps(),
      commitments: [
        {
          date: "2026-06-08",
          itemId: "c1",
          kind: "commitment",
          title: "Mid-morning call",
          isPrivate: false,
          startTime: "09:15",
          endTime: "09:45",
          warnings: [],
        },
      ],
    };
    renderCalendar([selected]);

    const agenda = [...document.querySelectorAll("ol > li")].map((item) => item.textContent ?? "");
    expect(agenda[0]).toContain("First overlap");
    expect(agenda[1]).toContain("Mid-morning call");
    expect(agenda[2]).toContain("Second overlap");
    expect(screen.getByRole("button", { name: /first overlap, planned session/i })).toHaveAttribute(
      "data-objective",
      "health",
    );
  });

  it("shows only the selected day's agenda at 390px", () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("max-width"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const selected = dayWithTwoOverlaps();
    const other: WeekDayData = {
      ...selected,
      date: "2026-06-09",
      sessions: [
        {
          ...selected.sessions[0],
          id: "s-other",
          title: "Tuesday only",
        },
      ],
    };
    renderCalendar([selected, other]);

    expect(screen.getAllByRole("button", { name: /open agenda for/i })).toHaveLength(2);
    expect(screen.getByText("First overlap")).toBeInTheDocument();
    expect(screen.queryByText("Tuesday only")).not.toBeInTheDocument();
  });
});
