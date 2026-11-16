import { useMemo, useState } from "react";
import { CalendarClock, Link2, RefreshCw, ShieldCheck, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/services/apiClient";
import { declineSentence, declineSummary, relaxationSentence } from "@/lib/declines";
import { summariseChanges, type PlanSession } from "@/lib/planDiff";
import type { DailySchedule, ForcedIncludeResult } from "@/types";

interface PlanToolsProps {
  schedule: DailySchedule;
  date: string;
  onChanged: (schedule: DailySchedule) => void;
}

function asPlanSessions(schedule: DailySchedule): PlanSession[] {
  return schedule.scheduledBehaviors.map((item) => ({
    id: item.id,
    plannedSessionId: item.plannedSessionId,
    behaviorId: item.behaviorId,
    startTime: item.startTime,
    duration: item.duration,
    isCompleted: item.isCompleted,
    behavior: { name: item.behavior?.name },
  }));
}

export function PlanTools({ schedule, date, onChanged }: PlanToolsProps) {
  const [busy, setBusy] = useState<null | "replan" | "commit" | "release">(null);
  const [changeSentences, setChangeSentences] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [forcedFor, setForcedFor] = useState<string | null>(null);
  const [forced, setForced] = useState<Record<string, ForcedIncludeResult>>({});

  const declines = useMemo(
    () =>
      (schedule.declines ?? []).map((decline) => ({
        behaviorId: decline.behaviorId,
        behaviorName: decline.behaviorName,
        reason: decline.reason,
      })),
    [schedule.declines],
  );

  const handleReplan = async () => {
    setBusy("replan");
    setNotice(null);
    try {
      const before = asPlanSessions(schedule);
      await apiClient.schedule.reoptimize();
      const fresh = await apiClient.schedule.getSchedule(date);
      const changes = summariseChanges(before, asPlanSessions(fresh.data));
      setChangeSentences(changes.sentences);
      onChanged(fresh.data);
    } catch (error) {
      setNotice(
        (error as { message?: string }).message ??
          "The day could not be re-planned. Nothing was changed.",
      );
    } finally {
      setBusy(null);
    }
  };

  const handleCommit = async () => {
    setBusy("commit");
    try {
      const response = await apiClient.schedule.commitDay();
      setNotice(response.message ?? "Your day is committed. It is now the baseline.");
    } catch (error) {
      setNotice(
        (error as { message?: string }).message ?? "The day could not be committed.",
      );
    } finally {
      setBusy(null);
    }
  };

  const handleRelease = async (sessionId: string) => {
    setBusy("release");
    try {
      await apiClient.schedule.releaseSession(sessionId);
      const fresh = await apiClient.schedule.getSchedule(date);
      onChanged(fresh.data);
      setNotice("Session released. It no longer counts against you.");
    } catch (error) {
      setNotice(
        (error as { message?: string }).message ?? "That session could not be released.",
      );
    } finally {
      setBusy(null);
    }
  };

  const handleForced = async (behaviorId: string) => {
    setForcedFor(behaviorId);
    try {
      const response = await apiClient.optimization.forcedInclude([behaviorId], date);
      setForced((previous) => ({ ...previous, [behaviorId]: response.data }));
    } catch (error) {
      setNotice(
        (error as { message?: string }).message ??
          "The what-if solve could not run; the day is unchanged.",
      );
    } finally {
      setForcedFor(null);
    }
  };

  return (
    <div className="space-y-4 rounded-lg border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={handleReplan} disabled={busy !== null} className="gap-2">
          <RefreshCw className={`h-4 w-4 ${busy === "replan" ? "animate-spin" : ""}`} />
          Re-plan the rest of my day
        </Button>
        <Button variant="outline" onClick={handleCommit} disabled={busy !== null} className="gap-2">
          <ShieldCheck className="h-4 w-4" />
          Commit / start my day
        </Button>
        <span className="text-xs text-muted-foreground">
          Re-planning never moves a session that already started.
        </span>
      </div>

      {notice && <p className="text-sm text-muted-foreground">{notice}</p>}

      {changeSentences.length > 0 && (
        <div className="rounded-md border border-border bg-background/60 p-3">
          <p className="mb-1 text-sm font-medium text-foreground">What changed</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {changeSentences.map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="text-sm font-medium text-foreground">
          <CalendarClock className="mr-1 inline h-4 w-4" />
          {declineSummary(declines)}
        </p>
        {declines.length > 0 && (
          <ul className="mt-2 space-y-2">
            {declines.map((decline) => {
              const result = forced[decline.behaviorId];
              return (
                <li key={decline.behaviorId} className="rounded-md border border-border p-3">
                  <p className="text-sm font-medium text-foreground">{decline.behaviorName}</p>
                  <p className="text-sm text-muted-foreground">
                    {declineSentence(decline.reason)}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      disabled={forcedFor === decline.behaviorId}
                      onClick={() => handleForced(decline.behaviorId)}
                    >
                      <Link2 className="h-3.5 w-3.5" />
                      What would it cost to fit it?
                    </Button>
                    {result && (
                      <p className="text-sm text-muted-foreground">
                        {result.fits
                          ? relaxationSentence(result.displaced, result.objectiveChange)
                          : "It cannot fit today without a shorter duration or another window."}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {schedule.scheduledBehaviors.length > 0 && (
        <div>
          <p className="text-sm font-medium text-foreground">Release a session</p>
          <p className="text-xs text-muted-foreground">
            Releasing removes it from the rate instead of counting it as missed. A
            session that already started counts as missed.
          </p>
          <ul className="mt-2 space-y-1">
            {schedule.scheduledBehaviors.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
              >
                <span className="text-sm text-foreground">
                  {item.behavior?.name} · {item.startTime} · {item.duration} min
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="gap-1"
                  disabled={busy !== null || item.isCompleted}
                  onClick={() => handleRelease(item.id)}
                >
                  <Undo2 className="h-3.5 w-3.5" />
                  Release
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
