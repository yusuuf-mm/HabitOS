import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HelperOrb } from "@/components/HelperOrb";
import type { HelperDraftItem, HelperDraftResponse } from "@/types/helper";

const { getStatus, draft, confirm } = vi.hoisted(() => ({
  getStatus: vi.fn(),
  draft: vi.fn(),
  confirm: vi.fn(),
}));

vi.mock("@/services/apiClient", () => ({
  apiClient: {
    helper: {
      getStatus: (...args: unknown[]) => getStatus(...args),
      draft: (...args: unknown[]) => draft(...args),
      confirm: (...args: unknown[]) => confirm(...args),
    },
  },
  helperApi: {
    getStatus: (...args: unknown[]) => getStatus(...args),
    draft: (...args: unknown[]) => draft(...args),
    confirm: (...args: unknown[]) => confirm(...args),
  },
}));

type SpeechWindow = Window & {
  SpeechRecognition?: unknown;
  webkitSpeechRecognition?: unknown;
};

const speechWindow = window as SpeechWindow;
let originalSpeechRecognition: unknown;
let originalWebkitSpeechRecognition: unknown;

type RecognitionBehavior =
  | { kind: "none" }
  | { kind: "transcript"; text: string }
  | { kind: "error"; code: string };

let behavior: RecognitionBehavior = { kind: "none" };

class MockSpeechRecognition {
  static instances: MockSpeechRecognition[] = [];
  lang = "en-GB";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;
  stopCalls = 0;
  onstart: (() => void) | null = null;
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onend: (() => void) | null = null;

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start() {
    this.onstart?.();
    if (behavior.kind === "transcript") this.emitTranscript(behavior.text);
    if (behavior.kind === "error") this.emitError(behavior.code);
  }

  stop() {
    this.stopCalls += 1;
    this.onend?.();
  }

  abort() {
    this.onend?.();
  }

  emitTranscript(text: string) {
    this.onresult?.({
      resultIndex: 0,
      results: {
        length: 1,
        0: {
          isFinal: true,
          length: 1,
          0: { transcript: text, confidence: 1 },
        },
      },
    });
  }

  emitError(code: string) {
    this.onerror?.({ error: code, message: "MOCKED recognition error" });
    this.onend?.();
  }
}

function installRecognition(next: RecognitionBehavior) {
  behavior = next;
  speechWindow.SpeechRecognition = MockSpeechRecognition;
}

function installUnsupported() {
  behavior = { kind: "none" };
  delete speechWindow.SpeechRecognition;
  delete speechWindow.webkitSpeechRecognition;
}

function configuredStatus() {
  return { configured: true, fastModel: "fast", strongModel: "strong" };
}

function tomorrow(): string {
  return new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
}

function draftResponse(): HelperDraftResponse {
  return {
    draftId: "draft-voice",
    items: [
      {
        kind: "commitment",
        title: "Dentist",
        startDate: tomorrow(),
        startTime: "09:30",
        durationMinutes: 45,
        recurrence: "once",
      } satisfies HelperDraftItem,
    ],
    assumptions: [],
    rejected: [],
    unsupported: [],
    warnings: [],
    displaced: [],
    dropped: [],
    clarify: null,
  };
}

function hasAudioPayload(value: unknown, depth = 0): boolean {
  if (depth > 6 || value === null || typeof value !== "object") return false;
  if (value instanceof Blob || value instanceof FormData) return true;
  return Object.entries(value as Record<string, unknown>).some(
    ([key, nested]) =>
      /audio|blob|media|record|file|recording/i.test(key) ||
      hasAudioPayload(nested, depth + 1),
  );
}

async function openConfiguredPanel() {
  getStatus.mockResolvedValue(configuredStatus());
  render(<HelperOrb />);
  await act(async () => {
    fireEvent.click(await screen.findByRole("button", { name: /plan assistant/i }));
  });
}

async function openAndStartVoice() {
  await openConfiguredPanel();
  await act(async () => {
    fireEvent.click(await screen.findByRole("button", { name: /^use voice$/i }));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  MockSpeechRecognition.instances = [];
  behavior = { kind: "none" };
  originalSpeechRecognition = speechWindow.SpeechRecognition;
  originalWebkitSpeechRecognition = speechWindow.webkitSpeechRecognition;
});

afterEach(() => {
  if (originalSpeechRecognition === undefined) delete speechWindow.SpeechRecognition;
  else speechWindow.SpeechRecognition = originalSpeechRecognition;
  if (originalWebkitSpeechRecognition === undefined) delete speechWindow.webkitSpeechRecognition;
  else speechWindow.webkitSpeechRecognition = originalWebkitSpeechRecognition;
});

describe("voice input (MOCKED recognition API)", () => {
  it("MOCKED: orb opens without starting; Use voice starts continuous listening and Done stops it", async () => {
    installRecognition({ kind: "none" });
    await openConfiguredPanel();

    expect(MockSpeechRecognition.instances).toHaveLength(0);
    expect(screen.queryByText("Listening…")).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(await screen.findByRole("button", { name: /^use voice$/i }));
    });

    expect(MockSpeechRecognition.instances).toHaveLength(1);
    expect(MockSpeechRecognition.instances[0].continuous).toBe(true);
    expect(screen.getByText("Listening…")).toBeInTheDocument();

    await act(async () => {
      MockSpeechRecognition.instances[0].emitTranscript("Dentist tomorrow at 9");
    });

    const input = screen.getByLabelText(/what would you like to plan/i);
    expect(input).toHaveValue("Dentist tomorrow at 9");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^done$/i }));
    });

    expect(MockSpeechRecognition.instances[0].stopCalls).toBe(1);
    expect(input).toHaveValue("Dentist tomorrow at 9");
    expect(screen.queryByText("Listening…")).not.toBeInTheDocument();
    expect(draft).not.toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("MOCKED: continuous final chunks accumulate until Done", async () => {
    installRecognition({ kind: "none" });
    await openAndStartVoice();
    const recognition = MockSpeechRecognition.instances[0];

    await act(async () => {
      recognition.emitTranscript("Dentist tomorrow at 9,");
    });
    await act(async () => {
      recognition.emitTranscript("then move it to 10.");
    });

    expect(screen.getByLabelText(/what would you like to plan/i)).toHaveValue(
      "Dentist tomorrow at 9, then move it to 10.",
    );
    expect(draft).not.toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("MOCKED: unsupported browser shows the exact fallback and typing still works", async () => {
    installUnsupported();
    draft.mockResolvedValue(draftResponse());
    await openConfiguredPanel();

    expect(
      screen.getByText("Voice isn't supported in this browser, type instead"),
    ).toBeInTheDocument();

    const input = screen.getByLabelText(/what would you like to plan/i);
    expect(input).toBeEnabled();
    fireEvent.change(input, { target: { value: "Typed instead" } });
    fireEvent.click(screen.getByRole("button", { name: /turn this into a plan/i }));

    await waitFor(() => expect(draft).toHaveBeenCalledWith("Typed instead"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("MOCKED: permission denied shows the error state and sends no request", async () => {
    installRecognition({ kind: "error", code: "not-allowed" });
    await openAndStartVoice();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /microphone permission was denied/i,
    );
    expect(screen.getByLabelText(/what would you like to plan/i)).toBeEnabled();
    expect(draft).not.toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("MOCKED: no-speech and network errors are distinct states", async () => {
    installRecognition({ kind: "error", code: "no-speech" });
    await openAndStartVoice();
    expect(await screen.findByRole("alert")).toHaveTextContent(/didn't hear anything/i);
    expect(draft).not.toHaveBeenCalled();
  });

  it("MOCKED: network error is distinct from no-speech", async () => {
    installRecognition({ kind: "error", code: "network" });
    await openAndStartVoice();
    expect(await screen.findByRole("alert")).toHaveTextContent(/needs a network connection/i);
    expect(draft).not.toHaveBeenCalled();
  });

  it("MOCKED: transcript is editable, undoable, and not sent or saved before explicit actions", async () => {
    installRecognition({ kind: "none" });
    draft.mockResolvedValue(draftResponse());
    confirm.mockResolvedValue({ confirmationId: "c-1", itemIds: ["i-1"] });
    await openAndStartVoice();

    expect(screen.getByText("Listening…")).toBeInTheDocument();

    await act(async () => {
      MockSpeechRecognition.instances[0].emitTranscript("Dentist tomorrow at 9");
    });

    const input = screen.getByLabelText(/what would you like to plan/i);
    expect(input).toHaveValue("Dentist tomorrow at 9");
    expect(draft).not.toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /undo voice input/i }));
    expect(input).toHaveValue("");

    await act(async () => {
      MockSpeechRecognition.instances[0].emitTranscript("Dentist tomorrow at 9:30");
    });
    fireEvent.change(input, { target: { value: "Dentist tomorrow at 10:00" } });
    expect(input).toHaveValue("Dentist tomorrow at 10:00");

    fireEvent.click(screen.getByRole("button", { name: /turn this into a plan/i }));
    await waitFor(() => expect(draft).toHaveBeenCalledWith("Dentist tomorrow at 10:00"));
    expect(confirm).not.toHaveBeenCalled();

    await screen.findByRole("button", { name: /approve selected/i });
    fireEvent.click(screen.getByRole("button", { name: /approve selected/i }));
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));

    for (const call of [...draft.mock.calls, ...confirm.mock.calls]) {
      expect(hasAudioPayload(call[0])).toBe(false);
    }
  });

  it("MOCKED: a plan change from voice reaches the confirm card before any write", async () => {
    installRecognition({ kind: "none" });
    draft.mockResolvedValue(draftResponse());
    await openAndStartVoice();

    await act(async () => {
      MockSpeechRecognition.instances[0].emitTranscript("Dentist tomorrow at 9:30");
    });
    fireEvent.click(screen.getByRole("button", { name: /turn this into a plan/i }));

    expect(await screen.findByRole("button", { name: /approve selected/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Dentist")).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });
});
