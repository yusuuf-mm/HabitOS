import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  VOICE_UNSUPPORTED_MESSAGE,
  type VoiceStatus,
} from "@/hooks/useSpeechRecognition";
import { apiClient } from "@/services/apiClient";
import type { HelperDraftItem, HelperDraftResponse, HelperStatus } from "@/types/helper";

export type HelperOrbState =
  | "idle"
  | "thinking"
  | "needsYou"
  | "done"
  | "error"
  | "listening"
  | "processing";

export interface HelperVoiceProps {
  supported: boolean;
  status: VoiceStatus;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
}

interface HelperPanelProps {
  date: string;
  onConfirmed?: () => void;
  onStateChange?: (s: HelperOrbState) => void;
  voiceTranscript?: { text: string; nonce: number };
  voice?: HelperVoiceProps;
}

const DEFAULT_VOICE: HelperVoiceProps = {
  supported: false,
  status: { state: "idle" },
  onStart: () => {},
  onStop: () => {},
  onReset: () => {},
};

type Phase = "idle" | "thinking" | "clarify" | "review" | "confirming" | "done";

function errorStatus(error: unknown): number | undefined {
  const e = error as {
    status?: number;
    response?: { status?: number };
    code?: string;
    statusCode?: number;
  } | null;
  if (!e) return undefined;
  if (typeof e.status === "number") return e.status;
  if (typeof e.response?.status === "number") return e.response.status;
  if (typeof e.statusCode === "number") return e.statusCode;
  return undefined;
}

function errorDetail(error: unknown): string {
  const e = error as Record<string, unknown> | null;
  if (!e) return "";
  const parts: string[] = [];
  const push = (v: unknown) => {
    if (typeof v === "string" && v) parts.push(v);
    else if (v && typeof v === "object") {
      const o = v as Record<string, unknown>;
      if (typeof o.message === "string") parts.push(o.message);
      if (typeof o.detail === "string") parts.push(o.detail);
      else if (o.detail && typeof o.detail === "object" && typeof (o.detail as Record<string, unknown>).message === "string")
        parts.push((o.detail as Record<string, unknown>).message as string);
    }
  };
  push(e.detail);
  push(e.message);
  const resp = e.response as Record<string, unknown> | undefined;
  if (resp) {
    const data = resp.data;
    push(data);
  }
  return parts.join(" ");
}

export function mapHelperError(error: unknown): string {
  const status = errorStatus(error);
  const detail = errorDetail(error);
  if (status === 429) {
    return "You're sending requests too quickly — wait a moment and try again.";
  }
  if (status === 503) {
    if (/nvidia|configured/i.test(detail)) {
      return "The assistant isn't configured on this server.";
    }
    return "The assistant is unavailable right now. Try again shortly.";
  }
  if (status === 422) {
    return "I couldn't turn that into a plan. Try saying it a different way.";
  }
  return "Something went wrong. Try again.";
}

function voiceStatusMessage(status: VoiceStatus): string | null {
  if (status.state === "listening") return "Listening…";
  if (status.state === "processing") return "Processing final transcript…";
  return null;
}

function recurrenceText(item: HelperDraftItem): string {
  const r = item.recurrence ?? "once";
  if (r === "daily") {
    if (typeof item.runDays === "number" && item.runDays > 0) {
      return `every day for ${item.runDays} days`;
    }
    return "every day";
  }
  if (r === "weekdays") return "weekdays";
  if (r === "weekly") return "weekly";
  return "one time";
}

function formatDateShort(value?: string): string {
  if (!value) return "";
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function addMinutes(start: string, durationMinutes?: number): string {
  if (!durationMinutes) return "";
  const [h, m] = start.split(":").map(Number);
  const total = h * 60 + m + durationMinutes;
  const hh = Math.floor(total / 60) % 24;
  const mm = total % 60;
  return `${hh.toString().padStart(2, "0")}:${mm.toString().padStart(2, "0")}`;
}

function timeSentence(item: HelperDraftItem): string {
  if (item.kind === "deadline") {
    const date = formatDateShort(item.dueOn);
    return date ? `${date} · Deadline` : "Deadline";
  }
  const date = formatDateShort(item.startDate);
  const start = item.startTime ?? "";
  const end = start ? addMinutes(start, item.durationMinutes) : "";
  const range = start && end ? `${start}–${end}` : start;
  const parts = [date, range, recurrenceText(item)].filter(Boolean);
  return parts.join(" · ");
}

function itemTitle(entry: unknown): string {
  if (entry && typeof entry === "object") {
    const e = entry as Record<string, unknown>;
    if (typeof e.title === "string") return e.title;
    const inner = e.item;
    if (inner && typeof inner === "object" && typeof (inner as Record<string, unknown>).title === "string") {
      return (inner as Record<string, unknown>).title as string;
    }
    if (typeof e.kind === "string") return e.kind;
  }
  return "Something";
}

const warnBox =
  "rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100";

function describeAddedItems(items: HelperDraftItem[]): string {
  if (items.length === 0) return "Added nothing.";
  const counts: Record<string, number> = {};
  for (const item of items) {
    const kind = item.kind === "commitment" || item.kind === "deadline" ? item.kind : "item";
    counts[kind] = (counts[kind] ?? 0) + 1;
  }
  const parts = Object.entries(counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([kind, count]) => `${count} ${kind}${count === 1 ? "" : "s"}`);
  const names = items.map((item) => item.title).filter(Boolean);
  return `Added ${parts.join(" and ")}${names.length <= 2 && names.length > 0 ? `: ${names.join(", ")}` : ""}.`;
}

export function HelperPanel({
  date,
  onConfirmed,
  onStateChange,
  voiceTranscript,
  voice,
}: HelperPanelProps) {
  const voiceProps = voice ?? DEFAULT_VOICE;
  const [status, setStatus] = useState<HelperStatus | null>(null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [transcript, setTranscript] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [draft, setDraft] = useState<HelperDraftResponse | null>(null);
  const [draftItems, setDraftItems] = useState<HelperDraftItem[]>([]);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [clarify, setClarify] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [addedSummary, setAddedSummary] = useState<string | null>(null);
  const [voiceInserted, setVoiceInserted] = useState(false);
  const undoTranscriptRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await apiClient.helper.getStatus();
        if (!cancelled) setStatus(s);
      } catch {
        if (!cancelled) setStatusFailed(true);
      } finally {
        if (!cancelled) setStatusLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const lastVoiceNonce = useRef(0);
  useEffect(() => {
    if (!voiceTranscript || voiceTranscript.nonce === lastVoiceNonce.current) return;
    const text = voiceTranscript.text.trim();
    if (!text) return;
    lastVoiceNonce.current = voiceTranscript.nonce;
    setTranscript((previous) => {
      undoTranscriptRef.current = previous;
      return text;
    });
    setVoiceInserted(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setAddedSummary(null);
    setClarify(null);
    setAnswer("");
    setDraft(null);
    setDraftItems([]);
    setPhase("idle");
    onStateChange?.("idle");
  }, [voiceTranscript, onStateChange]);

  const applyDraft = (resp: HelperDraftResponse, baseTranscript: string) => {
    setTranscript(baseTranscript);
    if (resp.clarify) {
      setClarify(resp.clarify);
      setDraft(resp);
      setPhase("clarify");
      onStateChange?.("needsYou");
      return;
    }
    setDraft(resp);
    setDraftItems(resp.items);
    const sel: Record<number, boolean> = {};
    resp.items.forEach((_, i) => {
      sel[i] = true;
    });
    setSelected(sel);
    setClarify(null);
    setPhase("review");
    onStateChange?.("needsYou");
  };

  const handleDraft = async (text: string) => {
    setPhase("thinking");
    onStateChange?.("thinking");
    setErrorMessage(null);
    setSuccessMessage(null);
    setAddedSummary(null);
    try {
      const resp = await apiClient.helper.draft(text);
      applyDraft(resp, text);
    } catch (error) {
      setErrorMessage(mapHelperError(error));
      setPhase("idle");
      onStateChange?.("error");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!transcript.trim() || phase === "thinking") return;
    void handleDraft(transcript.trim());
  };

  const handleAnswer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || phase === "thinking") return;
    const combined = `${transcript} — ${answer.trim()}`;
    void handleDraft(combined);
  };

  const handleApprove = async () => {
    if (!draft) return;
    setPhase("confirming");
    setErrorMessage(null);
    try {
      const items = draftItems.filter((_, i) => selected[i]);
      await apiClient.helper.confirm({
        draftId: draft.draftId,
        transcript,
        items,
      });
      setDraft(null);
      setDraftItems([]);
      setTranscript("");
      setClarify(null);
      setPhase("done");
      setSuccessMessage("Added to your plan.");
      setAddedSummary(describeAddedItems(items));
      onStateChange?.("done");
      onConfirmed?.();
    } catch (error) {
      setErrorMessage(mapHelperError(error));
      setPhase("review");
      onStateChange?.("error");
    }
  };

  const handleReject = () => {
    setDraft(null);
    setDraftItems([]);
    setTranscript("");
    setClarify(null);
    setAnswer("");
    setErrorMessage(null);
    setAddedSummary(null);
    setPhase("idle");
  };

  const updateItem = (index: number, patch: Partial<HelperDraftItem>) => {
    setDraftItems((prev) =>
      prev.map((it, i) => (i === index ? { ...it, ...patch } : it)),
    );
  };

  if (statusLoading) {
    return (
      <div className="space-y-4 rounded-lg border border-border bg-muted/20 p-4">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  const configured = status?.configured === true;
  const showDisabled = !configured;
  const voiceMessage = voiceStatusMessage(voiceProps.status);
  const voiceError =
    voiceProps.status.state === "error" ? voiceProps.status.message : null;

  return (
    <div className="space-y-4 rounded-lg border border-border bg-muted/20 p-4">
      <div className="space-y-1">
        <h2 className="text-sm font-medium text-foreground">Plan things in plain words</h2>
        <p className="text-xs text-muted-foreground">
          Describe what you need to do and check it before adding it to your plan.
        </p>
      </div>

      <div aria-live="polite" role="status" className="text-sm text-muted-foreground">
        {phase === "thinking" && "Thinking…"}
        {voiceMessage && <span className="block">{voiceMessage}</span>}
        {successMessage && !errorMessage && (
          <span className="block space-y-1">
            <span className="block">{successMessage}</span>
            {addedSummary && (
              <span className="block text-xs text-muted-foreground">
                {addedSummary}{" "}
                <a
                  href="/optimization"
                  className="font-medium text-accent underline underline-offset-2"
                >
                  Plan my week to fit it in
                </a>
              </span>
            )}
          </span>
        )}
      </div>

      {(voiceProps.status.state === "listening" ||
        voiceProps.status.state === "processing") && (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" onClick={voiceProps.onStop} className="min-h-[40px]">
            Done
          </Button>
          <span className="text-xs text-muted-foreground">
            Finish speaking, then select Done.
          </span>
        </div>
      )}

      {errorMessage && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage}
        </p>
      )}

      {voiceError && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p id="helper-voice-error" role="alert" className="text-sm text-destructive">
            {voiceError}
          </p>
          <Button type="button" variant="ghost" onClick={voiceProps.onReset} className="min-h-[40px]">
            Dismiss
          </Button>
        </div>
      )}

      {showDisabled ? (
        <div className="space-y-3">
          <label htmlFor="helper-transcript" className="text-sm font-medium text-foreground">
            What would you like to plan?
          </label>
          <textarea
            id="helper-transcript"
            disabled
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="For example: I have a dentist appointment on Tuesday at 10:00 for 45 minutes."
            maxLength={4000}
            rows={3}
            className="min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <p className="text-sm text-muted-foreground">
            The assistant isn&apos;t switched on for this workspace yet.
          </p>
        </div>
      ) : (
        <>
          {phase === "clarify" && clarify ? (
            <form onSubmit={handleAnswer} className="space-y-3">
              <div className={warnBox}>
                <p className="text-sm font-medium">One quick question</p>
                <p className="text-sm">{clarify}</p>
              </div>
              <div className="space-y-1">
                <label htmlFor="helper-answer" className="text-sm font-medium text-foreground">
                  Your answer
                </label>
                <input
                  id="helper-answer"
                  type="text"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  className="min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
              <Button type="submit" disabled={phase === "thinking"} className="min-h-[40px]">
                Send answer
              </Button>
            </form>
          ) : phase === "review" && draft ? (
            <div className="space-y-4">
              <div className="space-y-3">
                {draftItems.map((item, index) => {
                  const isCommitment = item.kind === "commitment";
                  const sentence = timeSentence(item);
                  return (
                    <fieldset
                      key={index}
                      className="space-y-2 rounded-md border border-border bg-background/60 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          type="checkbox"
                          checked={!!selected[index]}
                          onChange={(e) =>
                            setSelected((prev) => ({ ...prev, [index]: e.target.checked }))
                          }
                          aria-label={`Include ${item.title}`}
                          className="h-5 w-5"
                        />
                        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          {isCommitment ? "Fixed time" : "Deadline"}
                        </span>
                        {item.isPrivate && (
                          <span className="status-badge status-badge-info">Private</span>
                        )}
                      </div>
                      <div className="space-y-1">
                        <label
                          htmlFor={`helper-title-${index}`}
                          className="text-sm font-medium text-foreground"
                        >
                          Title
                        </label>
                        <input
                          id={`helper-title-${index}`}
                          type="text"
                          value={item.title}
                          onChange={(e) => updateItem(index, { title: e.target.value })}
                          className="min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        />
                      </div>
                      {isCommitment ? (
                        <div className="flex flex-wrap items-end gap-3">
                          <div className="space-y-1">
                            <label
                              htmlFor={`helper-start-${index}`}
                              className="text-sm font-medium text-foreground"
                            >
                              Start time
                            </label>
                            <input
                              id={`helper-start-${index}`}
                              type="time"
                              value={item.startTime ?? ""}
                              onChange={(e) => updateItem(index, { startTime: e.target.value })}
                              className="min-h-[40px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                            />
                          </div>
                          <p className="pb-2 text-sm text-muted-foreground">
                            {item.durationMinutes ? `${item.durationMinutes} minutes` : ""}
                          </p>
                          <div className="space-y-1">
                            <label
                              htmlFor={`helper-date-${index}`}
                              className="text-sm font-medium text-foreground"
                            >
                              Start date
                            </label>
                            <input
                              id={`helper-date-${index}`}
                              type="date"
                              value={item.startDate ?? ""}
                              onChange={(e) => updateItem(index, { startDate: e.target.value })}
                              className="min-h-[40px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <label
                            htmlFor={`helper-due-${index}`}
                            className="text-sm font-medium text-foreground"
                          >
                            Deadline date
                          </label>
                          <input
                            id={`helper-due-${index}`}
                            type="date"
                            value={item.dueOn ?? ""}
                            onChange={(e) => updateItem(index, { dueOn: e.target.value })}
                            className="min-h-[40px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                          />
                        </div>
                      )}
                      <p className="text-sm text-muted-foreground">{sentence}</p>
                    </fieldset>
                  );
                })}
              </div>

              {draft.assumptions.length > 0 && (
                <div className={warnBox}>
                  <p className="text-sm font-medium">Please check these assumptions</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {draft.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}

              {draft.warnings.length > 0 && (
                <div className={warnBox}>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {draft.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-1 text-sm text-muted-foreground">
                {draft.displaced.length === 0 && draft.dropped.length === 0 ? (
                  <p>Nothing already planned has to move.</p>
                ) : (
                  <>
                    {draft.displaced.map((d) => (
                      <p key={d.behaviorId}>
                        {d.behaviorName} would lose {d.minutes} minutes that day.
                      </p>
                    ))}
                    {draft.dropped.map((d) => (
                      <p key={d.behaviorId}>{d.behaviorName} would not fit that day.</p>
                    ))}
                  </>
                )}
              </div>

              {draft.unsupported.length > 0 && (
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {draft.unsupported.map((u, i) => (
                    <li key={i}>
                      {itemTitle(u)} — habits are added in the habit form for now.
                    </li>
                  ))}
                </ul>
              )}

              {draft.rejected.length > 0 && (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {draft.rejected.map((r, i) => (
                    <li key={i}>
                      {itemTitle(r)}: {r.reason ?? "not added"}
                    </li>
                  ))}
                </ul>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={handleApprove}
                  disabled={phase === "confirming"}
                  className="min-h-[40px]"
                >
                  {phase === "confirming" ? "Adding…" : "Approve selected"}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleReject}
                  disabled={phase === "confirming"}
                  className="min-h-[40px]"
                >
                  Reject
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1">
                <label htmlFor="helper-transcript" className="text-sm font-medium text-foreground">
                  What would you like to plan?
                </label>
                <textarea
                  id="helper-transcript"
                  value={transcript}
                  onChange={(e) => {
                    setVoiceInserted(false);
                    setTranscript(e.target.value);
                  }}
                  placeholder="For example: I have a dentist appointment on Tuesday at 10:00 for 45 minutes."
                  maxLength={4000}
                  rows={3}
                  className="min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  {transcript.length} / 4000 characters
                </p>
                {voiceInserted && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setTranscript(undoTranscriptRef.current);
                      setVoiceInserted(false);
                    }}
                    className="min-h-[40px]"
                  >
                    Undo voice input
                  </Button>
                )}
              </div>
              {voiceProps.supported ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={
                    voiceProps.status.state === "listening"
                      ? voiceProps.onStop
                      : voiceProps.onStart
                  }
                  disabled={voiceProps.status.state === "processing"}
                  aria-describedby={voiceError ? "helper-voice-error" : undefined}
                  className="min-h-[40px]"
                >
                  {voiceProps.status.state === "listening" ? "Stop listening" : "Use voice"}
                </Button>
              ) : (
                <p role="status" className="text-sm text-muted-foreground">
                  {VOICE_UNSUPPORTED_MESSAGE}
                </p>
              )}
              <Button
                type="submit"
                disabled={phase === "thinking" || !transcript.trim()}
                className="min-h-[40px]"
              >
                {phase === "thinking" ? "Thinking…" : "Turn this into a plan"}
              </Button>
              {statusFailed && (
                <p className="text-xs text-muted-foreground">
                  The assistant&apos;s status could not be checked.
                </p>
              )}
            </form>
          )}
        </>
      )}
    </div>
  );
}
