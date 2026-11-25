import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, X } from "lucide-react";
import {
  HelperPanel,
  type HelperOrbState,
  type HelperVoiceProps,
} from "@/components/HelperPanel";
import {
  useSpeechRecognition,
  VOICE_UNSUPPORTED_MESSAGE,
} from "@/hooks/useSpeechRecognition";
import { apiClient } from "@/services/apiClient";
import { localISODate } from "@/lib/localDate";

type OrbState = HelperOrbState | "unavailable";

export function HelperOrb({ onChanged }: { onChanged?: () => void }) {
  const [state, setState] = useState<OrbState>("idle");
  const [open, setOpen] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState<
    { text: string; nonce: number } | undefined
  >(undefined);
  const doneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptNonce = useRef(0);

  const handleFinalTranscript = useCallback((text: string) => {
    transcriptNonce.current += 1;
    setVoiceTranscript({ text, nonce: transcriptNonce.current });
  }, []);
  const voice = useSpeechRecognition({ onFinalTranscript: handleFinalTranscript });

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

  const unavailable = state === "unavailable";
  const displayState: OrbState =
    voice.status.state === "error"
      ? "error"
      : voice.status.state === "listening"
        ? "listening"
        : voice.status.state === "processing"
          ? "processing"
          : state;

  const handleState = (s: HelperOrbState) => setState(s);

  const openPanel = () => {
    setOpen(true);
    if (!unavailable && voice.supported) voice.start();
  };

  const closePanel = () => {
    if (voice.status.state === "listening" || voice.status.state === "processing") {
      voice.stop();
    }
    setOpen(false);
  };

  const voiceButtonLabel = !voice.supported
    ? VOICE_UNSUPPORTED_MESSAGE
    : voice.status.state === "listening"
      ? "Stop voice input"
      : "Start voice input";

  const voiceProps: HelperVoiceProps = {
    supported: voice.supported,
    status: voice.status,
    onStart: voice.start,
    onStop: voice.stop,
    onReset: voice.reset,
  };

  const stateLabel: Record<OrbState, string> = {
    idle: "",
    thinking: "thinking",
    needsYou: "needs your attention",
    done: "done",
    error: "needs a retry",
    listening: "listening",
    processing: "processing",
    unavailable: "unavailable",
  };

  return (
    <>
      <button
        type="button"
        aria-label={`Plan assistant${stateLabel[displayState] ? ` — ${stateLabel[displayState]}` : ""}`}
        onClick={openPanel}
        className="fixed bottom-24 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card shadow-lg sm:bottom-6 sm:right-6"
      >
        <svg
          viewBox="0 0 40 40"
          className={`h-10 w-10 ${
            displayState === "thinking" ||
            displayState === "listening" ||
            displayState === "processing"
              ? "text-accent motion-safe:animate-spin"
              : displayState === "error"
                ? "text-destructive"
                : displayState === "unavailable"
                  ? "text-zinc-400"
                  : displayState === "done"
                    ? "text-emerald-500"
                    : "text-accent"
          }`}
          aria-hidden="true"
        >
          <circle
            cx="20"
            cy="20"
            r="16"
            fill={displayState === "needsYou" ? "currentColor" : "none"}
            fillOpacity={displayState === "needsYou" ? 0.18 : undefined}
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray={
              displayState === "thinking" ||
              displayState === "listening" ||
              displayState === "processing"
                ? "6 4"
                : undefined
            }
          />
          <circle cx="20" cy="20" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
          {displayState === "error" ? (
            <path d="M15 15 L25 25 M25 15 L15 25" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          ) : displayState === "done" ? (
            <path d="M15 20 L19 24 L26 16" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          ) : (
            <circle cx="20" cy="20" r="3" fill="currentColor" />
          )}
        </svg>
        {displayState === "needsYou" && (
          <span className="absolute right-0 top-0 h-3.5 w-3.5 rounded-full bg-accent motion-safe:animate-pulse" aria-hidden="true" />
        )}
      </button>

      {displayState === "error" && !open && (
        <button
          type="button"
          onClick={openPanel}
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
                disabled={!voice.supported || unavailable}
                aria-disabled={!voice.supported || unavailable}
                aria-label={voiceButtonLabel}
                aria-pressed={voice.supported && voice.status.state === "listening"}
                title={voiceButtonLabel}
                onClick={() => {
                  if (voice.status.state === "listening") voice.stop();
                  else voice.start();
                }}
                className="rounded p-1 text-muted-foreground disabled:opacity-60"
              >
                <Mic className="h-4 w-4" aria-hidden="true" />
              </button>
              <button type="button" onClick={closePanel} aria-label="Close plan assistant" className="rounded p-1">
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
              voiceTranscript={voiceTranscript}
              voice={voiceProps}
            />
          )}
        </div>
      )}
    </>
  );
}
