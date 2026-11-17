/**
 * Reason codes are for the solver; people get sentences.
 *
 * The four codes the planner can emit today are in docs/FORMULATION.md
 * §Declines. Anything new must get a sentence here before it reaches a user —
 * the fallback says plainly that the planner did not explain itself rather than
 * inventing a reason.
 */

export interface Decline {
  behaviorId: string;
  behaviorName: string;
  reason: string;
}

const SENTENCES: Record<string, string> = {
  no_fit:
    "No free stretch in the windows you chose was long enough for it.",
  over_capacity:
    "The day was full: every window it could use was taken by other sessions.",
  preempted_by_protected:
    "A protected habit needed the only time it could use.",
};

export function declineSentence(reason: string): string {
  return SENTENCES[reason] ?? "The planner did not give a reason for this one.";
}

export function declineSummary(declines: Decline[]): string {
  if (!declines.length) return "Everything you asked for fitted today.";
  if (declines.length === 1) return "One habit did not fit today.";
  return `${declines.length} habits did not fit today.`;
}

export function relaxationSentence(
  displaced: Array<{ behaviorName: string; minutes: number }>,
  objectiveChange: number,
): string {
  const cost =
    objectiveChange >= 0
      ? `the day is worth ${objectiveChange.toFixed(1)} more`
      : `the day is worth ${Math.abs(objectiveChange).toFixed(1)} less`;
  if (!displaced.length) {
    return `It fits without moving anything; ${cost}.`;
  }
  const names = displaced
    .map((item) => `${item.behaviorName} (${item.minutes} min)`)
    .join(", ");
  return `It fits if you give up ${names}; ${cost}.`;
}
