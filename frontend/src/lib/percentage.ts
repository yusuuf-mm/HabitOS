/**
 * Percentages the user sees must add up to 100.
 *
 * The stored weights are exact (eight objectives at 0.125 each), but rounding
 * each share independently gave 13% × 8 and a footer claiming the draft
 * totalled 104%. Largest-remainder rounding keeps every displayed number
 * within one point of the true share while summing to exactly 100: the
 * leftover points go, largest fractional part first, to the shares that lost
 * the most by rounding down.
 */
export function roundedPercentages(fractions: number[]): number[] {
  if (!fractions.length) return [];
  const scaled = fractions.map((fraction) => fraction * 100);
  const result = scaled.map((value) => Math.floor(value));
  const leftover = 100 - result.reduce((sum, value) => sum + value, 0);
  if (leftover <= 0) return result;
  const byRemainder = scaled
    .map((value, index) => ({ index, remainder: value - result[index] }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (const { index } of byRemainder.slice(0, Math.min(leftover, byRemainder.length))) {
    result[index] += 1;
  }
  return result;
}
