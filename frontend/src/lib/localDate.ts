/**
 * Local calendar dates.
 *
 * `toISOString().slice(0, 10)` reports the UTC day. For a user east of UTC that
 * is yesterday for most of the morning, and west of UTC it is tomorrow in the
 * evening; either way the calendar highlights the wrong day. Every date sent
 * to the API or compared with an API date must use the local calendar day.
 */
export function localISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function mondayOf(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = (d.getDay() + 6) % 7; // Monday = 0
  d.setDate(d.getDate() - day);
  return d;
}

export function addDays(date: Date, n: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}
