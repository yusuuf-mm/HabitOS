/**
 * Plain-language summary of what a re-plan changed.
 *
 * Sessions keep their identity across revisions (docs/METRIC.md §4), so the
 * comparison is by id: a kept session is still there, a moved one changed its
 * start or length, a dropped one is gone, and anything new was added after the
 * baseline.
 */

export interface PlanSession {
  id: string;
  // Identity across plans. The row id changes on every run; this does not.
  plannedSessionId?: string;
  behaviorId: string;
  startTime: string;
  duration: number;
  isCompleted?: boolean;
  behavior?: { name?: string };
}

export interface PlanChanges {
  kept: PlanSession[];
  moved: PlanSession[];
  dropped: PlanSession[];
  added: PlanSession[];
  sentences: string[];
}

function nameOf(session: PlanSession): string {
  return session.behavior?.name ?? "a session";
}

/** The identity two plans share: the planned session, not the run's row. */
export function sessionKey(session: PlanSession): string {
  return session.plannedSessionId ?? session.id;
}

function hoursLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

export function summariseChanges(before: PlanSession[], after: PlanSession[]): PlanChanges {
  const afterById = new Map(after.map((session) => [sessionKey(session), session]));
  const beforeIds = new Set(before.map((session) => sessionKey(session)));

  const kept: PlanSession[] = [];
  const moved: PlanSession[] = [];
  const dropped: PlanSession[] = [];

  for (const session of before) {
    const next = afterById.get(sessionKey(session));
    if (!next) {
      dropped.push(session);
      continue;
    }
    if (next.startTime !== session.startTime || next.duration !== session.duration) {
      moved.push(next);
    } else {
      kept.push(next);
    }
  }

  const added = after.filter((session) => !beforeIds.has(sessionKey(session)));

  const sentences: string[] = [];
  if (moved.length) {
    sentences.push(
      `${moved.length} ${moved.length === 1 ? "session moved" : "sessions moved"}: ` +
        moved
          .map((session) => `${nameOf(session)} to ${session.startTime}`)
          .join(", ") +
        ".",
    );
  }
  if (dropped.length) {
    sentences.push(
      `${dropped.length} ${dropped.length === 1 ? "session was" : "sessions were"} dropped: ` +
        dropped.map((session) => nameOf(session)).join(", ") +
        ". You can re-add them from your behaviours.",
    );
  }
  if (added.length) {
    sentences.push(
      `${added.length} ${added.length === 1 ? "session was" : "sessions were"} added: ` +
        added
          .map((session) => `${nameOf(session)} at ${session.startTime}`)
          .join(", ") +
        ".",
    );
  }
  if (!sentences.length) {
    sentences.push("Nothing moved: the rest of the day is the same plan.");
  }
  if (kept.length) {
    sentences.push(
      `${kept.length} ${kept.length === 1 ? "session" : "sessions"} kept as they were.`,
    );
  }
  return { kept, moved, dropped, added, sentences };
}

export function totalMinutes(sessions: PlanSession[]): number {
  return sessions.reduce((sum, session) => sum + session.duration, 0);
}

export function hoursLabelFor(sessions: PlanSession[]): string {
  return hoursLabel(totalMinutes(sessions));
}
