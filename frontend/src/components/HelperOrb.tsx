import { useEffect, useRef, useState } from "react";
import { Mic, X } from "lucide-react";
import { HelperPanel, type HelperOrbState } from "@/components/HelperPanel";
import { apiClient } from "@/services/apiClient";
import { localISODate } from "@/lib/localDate";

type OrbState = HelperOrbState | "unavailable";

export function HelperOrb({ onChanged }: { onChanged?: () => void }) {
  const [state, setState] = useState<OrbState>("idle");
  const [open, setOpen] = useState(false);
  const [submitRequest, setSubmitRequest] = useState<{ text: string; nonce: number } | undefined>(
    undefined,
  );
  const doneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.helper
      .getStatus()
      .then((s) => {
        if (!cancelled && !s.configured) setState("unavailable");
      })
      .catch(() => {
        if (!cancelled) setState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (state === "done") {
      doneTimer.current = setTimeout(() => setState("idle"), 2500);
    }
    return () => {
      if (doneTimer.current) clearTimeout(doneTimer.current);
    };
  }, [state]);

  // Voice plugs in here later: pass a transcript in, get a draft back.
  const submitTranscript = (text: string) => {
    setOpen(true);
    setSubmitRequest({ text, nonce: Date.now() });
  };
  void submitTranscript;

  const handleState = (s: HelperOrbState) => {
    setState(s);
  };

  const stateLabel: Record<OrbState, string> = {
    idle: "",
    thinking: "thinking",
    needsYou: "needs your attention",
    done: "done",
    error: "needs a retry",
    unavailable: "unavailable",
  };

  return (
    <>
      <button
        type="button"
        aria-label={`Plan assistant${stateLabel[state] ? ` — ${stateLabel[state]}` : ""}`}
        onClick={() => setOpen(true)}
        className="fixed bottom-24 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card shadow-lg sm:bottom-6 sm:right-6"
      >
        <svg
          viewBox="0 0 40 40"
          className={`h-10 w-10 ${
            state === "thinking"
              ? "text-accent motion-safe:animate-spin"
              : state === "error"
              ? "text-destructive"
              : state === "unavailable"
              ? "text-zinc-400"
              : state === "done"
              ? "text-emerald-500"
              : "text-accent"
          }`}
          aria-hidden="true"
        >
          <circle
            cx="20"
            cy="20"
            r="16"
            fill={state === "needsYou" ? "currentColor" : "none"}
            fillOpacity={state === "needsYou" ? 0.18 : undefined}
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray={state === "thinking" ? "6 4" : undefined}
          />
          <circle cx="20" cy="20" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
          {state === "error" ? (
            <path d="M15 15 L25 25 M25 15 L15 25" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          ) : state === "done" ? (
            <path d="M15 20 L19 24 L26 16" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          ) : (
            <circle cx="20" cy="20" r="3" fill="currentColor" />
          )}
        </svg>
        {state === "needsYou" && (
          <span className="absolute right-0 top-0 h-3.5 w-3.5 rounded-full bg-accent motion-safe:animate-pulse" aria-hidden="true" />
        )}
      </button>

      {state === "error" && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-40 right-4 z-40 rounded-full bg-card px-3 py-1 text-xs shadow sm:bottom-24 sm:right-6"
          aria-label="Retry plan assistant"
        >
          Retry
        </button>
      )}

      {open && (
        <div
          role="dialog"
          aria-label="Plan assistant"
          className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-2xl border border-border bg-card p-4 shadow-lg sm:inset-x-auto sm:bottom-4 sm:right-4 sm:top-auto sm:max-h-[calc(100vh-2rem)] sm:w-[26rem] sm:max-w-[92vw] sm:rounded-xl"
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Plan assistant</h2>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled
                aria-disabled="true"
                aria-label="Voice is coming soon"
                title="Voice is coming soon"
                className="rounded p-1 text-muted-foreground opacity-60"
              >
                <Mic className="h-4 w-4" />
              </button>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close plan assistant" className="rounded p-1">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
          {state === "unavailable" ? (
            <p className="text-sm text-muted-foreground">
              The assistant isn&apos;t switched on for this workspace yet.
            </p>
          ) : (
            <HelperPanel
              date={localISODate(new Date())}
              onConfirmed={onChanged}
              onStateChange={handleState}
              submitRequest={submitRequest}
            />
          )}
        </div>
      )}
    </>
  );
}
