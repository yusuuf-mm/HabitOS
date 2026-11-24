export interface SeriesDay {
  date: string;
  completed: number;
  baseline: number;
  released: number;
  dropped: number;
  completionRate: number | null;
  plannedMinutes: number;
}

export interface RangeEntry {
  date: string;
  itemId: string;
  kind: string;
  title: string;
  isPrivate: boolean;
  startTime?: string;
  endTime?: string;
  dueOn?: string;
  warnings: string[];
}

export interface ItemDetail {
  id: string;
  kind: string;
  title: string;
  notes?: string | null;
  isPrivate: boolean;
  startDate?: string | null;
  startTime?: string | null;
  durationMinutes?: number | null;
  recurrence?: string | null;
  recurrenceUntil?: string | null;
  weekdays?: number[] | null;
  dueOn?: string | null;
  warnings?: string[];
  [key: string]: unknown;
}

export interface SessionBlock {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  duration: number;
  behaviorName: string;
  objectiveName?: string;
  completed: boolean;
  releasedAt?: string | null;
}

export interface WeekDayData {
  date: string;
  sessions: SessionBlock[];
  commitments: RangeEntry[];
  deadlines: RangeEntry[];
  // The schedule request for this day failed; any sessions shown are stale.
  unavailable?: boolean;
  // draft = future week plan, committed = today's accepted baseline,
  // fallback = today re-planned around completed/released sessions.
  planSource?: "draft" | "committed" | "fallback" | "none";
}

export type DayData = WeekDayData;

export interface HeroObjective {
  name: string;
  value: number;
  share: number;
}

export type SelectedBlock =
  | { type: "session"; day: WeekDayData; session: SessionBlock }
  | { type: "commitment"; day: WeekDayData; item: RangeEntry }
  | { type: "deadline"; day: WeekDayData; item: RangeEntry }
  | { type: "day"; day: WeekDayData };
