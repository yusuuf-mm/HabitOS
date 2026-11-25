import { useCallback, useEffect, useRef, useState, type SetStateAction } from "react";
import {
  getSpeechRecognitionConstructor,
  type SpeechRecognitionErrorCode,
  type SpeechRecognitionLike,
} from "@/lib/speechRecognition";

export const VOICE_UNSUPPORTED_MESSAGE =
  "Voice isn't supported in this browser, type instead";

export const VOICE_ERROR_MESSAGES = {
  "permission-denied":
    "Microphone permission was denied. Type instead, or allow access and try again.",
  "no-speech": "I didn't hear anything. Try again or type instead.",
  network: "Voice input needs a network connection. Type instead.",
  unknown: "Voice input didn't work. Type instead.",
} as const;

export type VoiceErrorCode = keyof typeof VOICE_ERROR_MESSAGES;

export type VoiceStatus =
  | { state: "idle" }
  | { state: "listening" }
  | { state: "processing" }
  | { state: "error"; code: VoiceErrorCode; message: string };

interface UseSpeechRecognitionOptions {
  onFinalTranscript: (text: string) => void;
  lang?: string;
}

function mapRecognitionError(code: SpeechRecognitionErrorCode): VoiceErrorCode {
  if (code === "not-allowed" || code === "service-not-allowed" || code === "audio-capture") {
    return "permission-denied";
  }
  if (code === "no-speech") return "no-speech";
  if (code === "network") return "network";
  return "unknown";
}

export function useSpeechRecognition({
  onFinalTranscript,
  lang = "en-GB",
}: UseSpeechRecognitionOptions) {
  const [supported] = useState(() => Boolean(getSpeechRecognitionConstructor()));
  const [status, setStatus] = useState<VoiceStatus>({ state: "idle" });
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const callbackRef = useRef(onFinalTranscript);
  const mountedRef = useRef(true);
  const failedRef = useRef(false);

  useEffect(() => {
    callbackRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const setStatusSafe = useCallback((next: SetStateAction<VoiceStatus>) => {
    if (mountedRef.current) setStatus(next);
  }, []);

  const start = useCallback(() => {
    if (!supported) {
      setStatusSafe({
        state: "error",
        code: "unknown",
        message: VOICE_UNSUPPORTED_MESSAGE,
      });
      return;
    }
    if (recognitionRef.current) return;

    const Constructor = getSpeechRecognitionConstructor();
    if (!Constructor) {
      setStatusSafe({
        state: "error",
        code: "unknown",
        message: VOICE_UNSUPPORTED_MESSAGE,
      });
      return;
    }

    failedRef.current = false;
    const recognition = new Constructor();
    recognition.lang = lang;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setStatusSafe({ state: "listening" });

    recognition.onresult = (event) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result.isFinal) continue;
        for (let j = 0; j < result.length; j += 1) {
          finalTranscript += result[j].transcript;
        }
      }
      const text = finalTranscript.trim();
      if (!text) return;
      setStatusSafe({ state: "processing" });
      callbackRef.current(text);
    };

    recognition.onerror = (event) => {
      if (event.error === "aborted") {
        setStatusSafe({ state: "idle" });
        return;
      }
      failedRef.current = true;
      const code = mapRecognitionError(event.error);
      setStatusSafe({ state: "error", code, message: VOICE_ERROR_MESSAGES[code] });
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      if (failedRef.current) return;
      setStatusSafe((current) =>
        current.state === "listening" || current.state === "processing"
          ? { state: "idle" }
          : current,
      );
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      failedRef.current = true;
      recognitionRef.current = null;
      setStatusSafe({
        state: "error",
        code: "unknown",
        message: VOICE_ERROR_MESSAGES.unknown,
      });
    }
  }, [lang, setStatusSafe, supported]);

  const stop = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      recognition.stop();
    } catch {
      recognitionRef.current = null;
      setStatusSafe({ state: "idle" });
    }
  }, [setStatusSafe]);

  const reset = useCallback(() => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    failedRef.current = false;
    setStatusSafe({ state: "idle" });
  }, [setStatusSafe]);

  return { supported, status, start, stop, reset };
}
