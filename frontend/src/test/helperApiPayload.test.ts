import { beforeEach, describe, expect, it, vi } from "vitest";
import { helperApi } from "@/services/apiClient";

const { apiGet, apiPost, apiPut, apiDelete } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiPost: (...args: unknown[]) => apiPost(...args),
  apiPut: (...args: unknown[]) => apiPut(...args),
  apiDelete: (...args: unknown[]) => apiDelete(...args),
}));

function hasAudioPayload(value: unknown, depth = 0): boolean {
  if (depth > 6 || value === null || typeof value !== "object") return false;
  if (value instanceof Blob || value instanceof FormData) return true;
  return Object.entries(value as Record<string, unknown>).some(
    ([key, nested]) =>
      /audio|blob|media|record|file|recording/i.test(key) ||
      hasAudioPayload(nested, depth + 1),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  apiPost.mockResolvedValue({});
});

describe("helper API payloads (MOCKED transport)", () => {
  it("MOCKED: draft and confirm send text/items only, never audio", async () => {
    await helperApi.draft("Book the dentist");
    await helperApi.confirm({
      draftId: "draft-1",
      transcript: "Book the dentist",
      items: [
        {
          kind: "commitment",
          title: "Dentist",
          startDate: "2026-11-26",
          startTime: "09:30",
          durationMinutes: 45,
          recurrence: "once",
        },
      ],
    });

    expect(apiPost).toHaveBeenCalledTimes(2);
    expect(apiPost.mock.calls[0]).toEqual([
      "/helper/draft",
      { transcript: "Book the dentist" },
    ]);
    expect(Object.keys(apiPost.mock.calls[1][1] as object).sort()).toEqual([
      "draftId",
      "items",
      "transcript",
    ]);
    for (const call of apiPost.mock.calls) {
      expect(hasAudioPayload(call[1])).toBe(false);
    }
  });
});
