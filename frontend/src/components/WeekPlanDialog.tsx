import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CalendarRange, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { addDays, localISODate } from "@/lib/localDate";
import { apiClient } from "@/services/apiClient";
import type { WeekDayResult, WeekDaySkip, WeekSessionSlot } from "@/types";

interface WeekPlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  weekStart: string;
  onApplied: () => void;
}

type Phase = "loading" | "ready" | "applying" | "applied" | "error";

interface ApplyFailure {
  message: string;
  code?: string;
  skippedDays?: WeekDaySkip[];
}

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "The request could not be completed.";
}

function applyFailure(error: unknown): ApplyFailure {
  if (!error || typeof error !== "object") return { message: errorMessage(error) };
  const raw = error as {
    message?: unknown;
    code?: unknown;
    detail?: unknown;
  };
  const detail =
    raw.detail && typeof raw.detail === "object"
      ? (raw.detail as { message?: unknown; skippedDays?: WeekDaySkip[] })
      : undefined;
  return {
    message: errorMessage(raw),
    code: raw.code === undefined ? undefined : String(raw.code),
    skippedDays: detail?.skippedDays,
  };
}

function dateAtNoon(date: string): Date {
  return new Date(`${date}T12:00:00`);
}

function shortRangeDate(date: string): string {
  const value = dateAtNoon(date);
  const weekday = value.toLocaleDateString("en-US", { weekday: "short" });
  return `${weekday} ${value.getDate()}`;
}

function rangeLabel(start: string, end: string): string {
  return `Planning ${shortRangeDate(start)} to ${shortRangeDate(end)}`;
}

function planableDates(weekStart: string): string[] {
  const monday = dateAtNoon(weekStart);
  const today = localISODate(new Date());
  return Array.from({ length: 7 }, (_, index) =>
    localISODate(addDays(monday, index)),
  ).filter((date) => date >= today);
}

function dayLabel(date: string): string {
  return dateAtNoon(date).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function slotLabel(slot: WeekSessionSlot): string {
  return `${slot.startTime}–${slot.endTime} · ${slot.duration} min`;
}

function ChangeList({ day }: { day: WeekDayResult }) {
  const empty =
    day.added.length === 0 && day.moved.length === 0 && day.dropped.length === 0;

  if (empty) {
    return <p className="text-sm text-muted-foreground">No changes to this day.</p>;
  }

  return (
    <div className="mt-2 grid gap-3 sm:grid-cols-3">
      <section aria-label={`Added on ${day.date}`}>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-success">
          Added · {day.added.length}
        </h4>
        {day.added.length === 0 ? (
          <p className="mt-1 text-xs text-muted-foreground">None</p>
        ) : (
          <ul className="mt-1 space-y-1 text-sm">
            {day.added.map((session) => (
              <li key={session.plannedSessionId}>
                <span className="font-medium">{session.behaviorName}</span>
                <span className="text-muted-foreground"> · {slotLabel(session)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label={`Moved on ${day.date}`}>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-info">
          Moved · {day.moved.length}
        </h4>
        {day.moved.length === 0 ? (
          <p className="mt-1 text-xs text-muted-foreground">None</p>
        ) : (
          <ul className="mt-1 space-y-1 text-sm">
            {day.moved.map((session) => (
              <li key={session.plannedSessionId}>
                <span className="font-medium">{session.behaviorName}</span>
                <span className="text-muted-foreground">
                  {" "}
                  · {session.before.startTime} → {session.after.startTime}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label={`Removed from draft on ${day.date}`}>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-destructive">
          Removed from draft · {day.dropped.length}
        </h4>
        {day.dropped.length === 0 ? (
          <p className="mt-1 text-xs text-muted-foreground">None</p>
        ) : (
          <ul className="mt-1 space-y-1 text-sm">
            {day.dropped.map((session) => (
              <li key={session.plannedSessionId}>
                <span className="font-medium">{session.behaviorName}</span>
                <span className="text-muted-foreground"> · {slotLabel(session)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function WeekPlanDialog({
  open,
  onOpenChange,
  weekStart,
  onApplied,
}: WeekPlanDialogProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof apiClient.optimization.previewWeek>
  >["data"]>(null);
  const [applied, setApplied] = useState<Awaited<
    ReturnType<typeof apiClient.optimization.applyWeek>
  >["data"]>(null);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApplyFailure | null>(null);

  const localDates = planableDates(weekStart);
  const rangeStart = preview?.rangeStart ?? weekStart;
  const rangeEnd =
    preview?.rangeEnd ?? localISODate(addDays(dateAtNoon(weekStart), 6));

  const loadPreview = useCallback(async () => {
    setPhase("loading");
    setError(null);
    setFailure(null);
    setApplied(null);
    try {
      const response = await apiClient.optimization.previewWeek(weekStart);
      setPreview(response.data);
      setPhase("ready");
    } catch (cause) {
      setPreview(null);
      setError(errorMessage(cause));
      setPhase("error");
    }
  }, [weekStart]);

  useEffect(() => {
    if (!open) return;
    void loadPreview();
  }, [open, loadPreview]);

  const applicable = (preview?.days ?? []).filter((day) => day.available);
  const solvedDates = applicable.map((day) => day.date);
  const skippedDays: WeekDaySkip[] =
    preview?.skippedDays ??
    (preview?.days ?? [])
      .filter((day) => !day.available)
      .map((day) => ({
        date: day.date,
        code: day.error?.code ?? "unavailable",
        message: day.error?.message ?? "This day could not be previewed.",
      }));

  const handleApply = async () => {
    if (!preview || solvedDates.length === 0) return;
    setPhase("applying");
    setFailure(null);
    try {
      const response = await apiClient.optimization.applyWeek({
        weekStart: preview.weekStart,
        fingerprint: preview.fingerprint,
        dates: solvedDates,
        expectedResults: Object.fromEntries(
          applicable.map((day) => [day.date, day.resultHash ?? ""]),
        ),
      });
      setApplied(response.data);
      setPhase("applied");
      onApplied();
    } catch (cause) {
      const parsed = applyFailure(cause);
      setFailure(parsed);
      setPhase("ready");
    }
  };

  const stalePreview =
    failure?.code === "week_plan_stale" || failure?.code === "week_plan_changed";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl"
        aria-busy={phase === "loading" || phase === "applying"}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarRange className="h-5 w-5" aria-hidden="true" />
            Plan my week
          </DialogTitle>
          <DialogDescription>
            {rangeLabel(rangeStart, rangeEnd)} · Preview only — nothing is saved
            until you apply. Each solved day uses your saved objective weights
            and existing fixed commitments.
          </DialogDescription>
        </DialogHeader>

        {phase === "loading" && (
          <div
            role="status"
            aria-live="polite"
            className="py-10 text-center text-sm text-muted-foreground"
          >
            Planning {localDates.length} day{localDates.length === 1 ? "" : "s"}...
          </div>
        )}

        {phase === "error" && (
          <div role="alert" className="dashboard-card border-destructive/30">
            <p className="flex items-center gap-2 font-medium text-destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              Week preview unavailable
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => void loadPreview()}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </Button>
          </div>
        )}

        {phase === "ready" && preview && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>
                {applicable.length} of {preview.days.length} days can be planned.
              </span>
              {skippedDays.length > 0 && (
                <span className="status-badge status-badge-warning">
                  {skippedDays.length} day{skippedDays.length === 1 ? "" : "s"}{" "}
                  unavailable
                </span>
              )}
            </div>

            {failure && (
              <div
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              >
                <p className="font-medium">
                  {stalePreview
                    ? "This preview is out of date."
                    : "The plan could not be applied."}
                </p>
                <p className="mt-1">{failure.message}</p>
                {failure.skippedDays && failure.skippedDays.length > 0 && (
                  <ul className="mt-1 list-disc pl-5">
                    {failure.skippedDays.map((skip) => (
                      <li key={skip.date}>{skip.message}</li>
                    ))}
                  </ul>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => void loadPreview()}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Refresh preview
                </Button>
              </div>
            )}

            <div className="max-h-[55vh] space-y-3 overflow-y-auto pr-1">
              {preview.days.map((day) => (
                <section key={day.date} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-medium">{dayLabel(day.date)}</h3>
                    {day.available ? (
                      <span className="status-badge status-badge-success">
                        {day.mode === "partial" ? "Re-plan remaining day" : "New plan"}
                      </span>
                    ) : (
                      <span className="status-badge status-badge-warning">
                        {day.error?.code === "past_day" ? "Past" : "Unavailable"}
                      </span>
                    )}
                  </div>

                  {day.available ? (
                    <>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {day.sessionsBefore} → {day.sessionsAfter} sessions · {day.minutesBefore} →{" "}
                        {day.minutesAfter} min
                      </p>
                      <ChangeList day={day} />
                      {day.declines.length > 0 && (
                        <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">
                          Not placed:{" "}
                          {day.declines
                            .map((decline) => `${decline.behaviorName} (${decline.reason})`)
                            .join("; ")}
                        </p>
                      )}
                    </>
                  ) : (
                    <p role="status" className="mt-2 text-sm text-muted-foreground">
                      {day.error?.message ?? "This day could not be previewed."}
                    </p>
                  )}
                </section>
              ))}
            </div>

            <DialogFooter className="gap-2 border-t pt-4">
              <p className="mr-auto max-w-sm text-xs text-muted-foreground">
                Applying re-checks your saved settings and re-solves only the
                days that can be planned. Skipped days are reported and never
                written as an empty plan.
              </p>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => void handleApply()}
                disabled={phase === "applying" || solvedDates.length === 0}
              >
                {phase === "applying"
                  ? `Applying ${solvedDates.length} day${solvedDates.length === 1 ? "" : "s"}...`
                  : `Apply ${solvedDates.length} day${solvedDates.length === 1 ? "" : "s"}`}
              </Button>
            </DialogFooter>
          </>
        )}

        {phase === "applied" && applied && (
          <div role="status" className="space-y-3">
            <div>
              <h3 className="font-medium">Week planned</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {applied.appliedDays} day{applied.appliedDays === 1 ? "" : "s"}{" "}
                applied. The calendar now shows each solved day's sessions.
              </p>
            </div>
            {applied.skippedDays.length > 0 && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
                <p className="font-medium text-amber-900 dark:text-amber-100">
                  {applied.skippedDays.length} day
                  {applied.skippedDays.length === 1 ? "" : "s"} skipped
                </p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-amber-900 dark:text-amber-100">
                  {applied.skippedDays.map((skip) => (
                    <li key={skip.date}>
                      {dayLabel(skip.date)} — {skip.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <DialogFooter className="border-t pt-4">
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
