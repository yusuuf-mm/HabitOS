import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HelperPanel } from "@/components/HelperPanel";
import type { HelperDraftItem, HelperDraftResponse } from "@/types/helper";

const getStatus = vi.fn();
const draft = vi.fn();
const confirm = vi.fn();
const getDay = vi.fn();

vi.mock("@/services/apiClient", () => ({
  apiClient: {
    helper: {
      getStatus: (...args: unknown[]) => getStatus(...args),
      draft: (...args: unknown[]) => draft(...args),
      confirm: (...args: unknown[]) => confirm(...args),
    },
    items: {
      getDay: (...args: unknown[]) => getDay(...args),
    },
  },
  helperApi: {
    getStatus: (...args: unknown[]) => getStatus(...args),
    draft: (...args: unknown[]) => draft(...args),
    confirm: (...args: unknown[]) => confirm(...args),
  },
  itemsApi: {
    getDay: (...args: unknown[]) => getDay(...args),
  },
}));

function tomorrow(): string {
  return new Date(Date.now() + 86400000).toISOString().slice(0, 10);
}

function commitment(overrides: Partial<HelperDraftItem> = {}): HelperDraftItem {
  return {
    kind: "commitment",
    title: "Hospital",
    startDate: tomorrow(),
    startTime: "08:00",
    durationMinutes: 60,
    recurrence: "daily",
    runDays: 3,
    ...overrides,
  };
}

function draftResponse(overrides: Partial<HelperDraftResponse> = {}): HelperDraftResponse {
  return {
    draftId: "draft-1",
    items: [commitment()],
    assumptions: ["Duration assumed 1 hour."],
    rejected: [],
    unsupported: [],
    warnings: ["Hospital falls in the sleep window (21:00-05:00)."],
    displaced: [{ behaviorId: "b-1", behaviorName: "Deep work", minutes: 45 }],
    dropped: [],
    clarify: null,
    ...overrides,
  };
}

function configuredStatus() {
  return { configured: true, fastModel: "fast", strongModel: "strong" };
}

async function submitTranscript(text: string) {
  const box = await screen.findByLabelText(/what would you like to plan/i);
  fireEvent.change(box, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: /turn this into a plan/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("HelperPanel", () => {
  it("shows the switched-off message and disables input when not configured", async () => {
    getStatus.mockResolvedValue({ configured: false, fastModel: "", strongModel: "" });
    render(<HelperPanel date="2026-11-21" />);

    expect(await screen.findByText(/isn't switched on/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/what would you like to plan/i)).toBeDisabled();
    expect(draft).not.toHaveBeenCalled();
  });

  it("reviews a draft with assumptions, displaced time and warnings", async () => {
    getStatus.mockResolvedValue(configuredStatus());
    draft.mockResolvedValue(draftResponse());
    render(<HelperPanel date="2026-11-21" />);

    await submitTranscript("I need to go to hospital tomorrow at 8am");

    expect(await screen.findByDisplayValue("Hospital")).toBeInTheDocument();
    expect(screen.getByText("Duration assumed 1 hour.")).toBeInTheDocument();
    expect(screen.getByText(/Deep work.*45/)).toBeInTheDocument();
    expect(screen.getByText(/falls in the sleep window \(21:00-05:00\)/)).toBeInTheDocument();
  });

  it("approves only the selected subset", async () => {
    getStatus.mockResolvedValue(configuredStatus());
    const first = commitment({ title: "First" });
    const second: HelperDraftItem = { kind: "deadline", title: "Second", dueOn: tomorrow() };
    draft.mockResolvedValue(draftResponse({ items: [first, second] }));
    confirm.mockResolvedValue({ confirmationId: "c-1", itemIds: ["i-2"] });
    render(<HelperPanel date="2026-11-21" />);

    await submitTranscript("plan two things");
    expect(await screen.findByDisplayValue("Second")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Include First"));
    fireEvent.click(screen.getByRole("button", { name: /approve selected/i }));

    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    const payload = confirm.mock.calls[0][0] as { items: HelperDraftItem[] };
    expect(payload.items).toHaveLength(1);
    expect(payload.items[0].title).toBe("Second");
    expect(await screen.findByText(/added to your plan/i)).toBeInTheDocument();
  });

  it("sends edited values in the confirm payload", async () => {
    getStatus.mockResolvedValue(configuredStatus());
    draft.mockResolvedValue(draftResponse());
    confirm.mockResolvedValue({ confirmationId: "c-1", itemIds: ["i-1"] });
    render(<HelperPanel date="2026-11-21" />);

    await submitTranscript("hospital tomorrow");
    expect(await screen.findByDisplayValue("Hospital")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Clinic" } });
    fireEvent.change(screen.getByLabelText("Start time"), { target: { value: "09:30" } });
    fireEvent.click(screen.getByRole("button", { name: /approve selected/i }));

    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    const payload = confirm.mock.calls[0][0] as { items: HelperDraftItem[] };
    expect(payload.items[0].title).toBe("Clinic");
    expect(payload.items[0].startTime).toBe("09:30");
  });

  it("rejects a draft and returns to the empty form without confirming", async () => {
    getStatus.mockResolvedValue(configuredStatus());
    draft.mockResolvedValue(draftResponse());
    render(<HelperPanel date="2026-11-21" />);

    await submitTranscript("hospital tomorrow");
    expect(await screen.findByDisplayValue("Hospital")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^reject$/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/what would you like to plan/i)).toBeEnabled(),
    );
    expect(screen.queryByDisplayValue("Hospital")).not.toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("shows the unavailable message when drafting fails with 503", async () => {
    getStatus.mockResolvedValue(configuredStatus());
    draft.mockRejectedValue({ status: 503 });
    render(<HelperPanel date="2026-11-21" />);

    await submitTranscript("hospital tomorrow");

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  });
});
