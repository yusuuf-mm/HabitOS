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
import { apiClient } from "@/services/apiClient";
import type { WeekDayResult, WeekSessionSlot } from "@/types";

interface WeekPlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  weekStart: string;
  onApplied: () => void;
}

type Phase = "loading" | "ready" | "applying" | "error";

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "The request could not be completed.";
}

function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", {
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

      <section aria-label={`Dropped on ${day.date}`}>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-destructive">
          Dropped · {day.dropped.length}
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
  const [error, setError] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setPhase("loading");
    setError(null);
    setApplyError(null);
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
  const blocking = (preview?.days ?? []).filter(
    (day) => !day.available && day.error?.code !== "past_day",
  );

  const handleApply = async () => {
    if (!preview) return;
    setPhase("applying");
    setApplyError(null);
    try {
      await apiClient.optimization.applyWeek(weekStart, preview.fingerprint);
      onApplied();
      onOpenChange(false);
    } catch (cause) {
      setApplyError(errorMessage(cause));
      setPhase("ready");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" aria-busy={phase === "applying"}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarRange className="h-5 w-5" aria-hidden="true" />
            Plan my week
          </DialogTitle>
          <DialogDescription>
            Preview only — nothing is saved until you apply. Each day uses your
            saved objective weights and existing fixed commitments.
          </DialogDescription>
        </DialogHeader>

        {phase === "loading" && (
          <div role="status" aria-live="polite" className="py-10 text-center text-sm text-muted-foreground">
            Solving each day…
          </div>
        )}

        {phase === "error" && (
          <div role="alert" className="dashboard-card border-destructive/30">
            <p className="flex items-center gap-2 font-medium text-destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              Week preview unavailable
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => void loadPreview()}>
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
              {blocking.length > 0 && (
                <span className="status-badge status-badge-warning">
                  {blocking.length} day{blocking.length === 1 ? "" : "s"} unavailable
                </span>
              )}
            </div>

            {applyError && (
              <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                <p className="font-medium">The plan could not be applied.</p>
                <p className="mt-1">{applyError}</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => void loadPreview()}>
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
                Applying re-checks your saved settings and writes every planned
                day together. Future days are not committed as baselines.
              </p>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => void handleApply()}
                disabled={phase === "applying" || blocking.length > 0 || applicable.length === 0}
              >
                {phase === "applying"
                  ? "Applying…"
                  : `Apply ${applicable.length} day${applicable.length === 1 ? "" : "s"}`}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
