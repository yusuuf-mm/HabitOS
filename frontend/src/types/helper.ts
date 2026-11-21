export interface HelperDraftItem {
  kind: "commitment" | "deadline" | "habit" | string;
  title: string;
  startDate?: string;
  startTime?: string;
  durationMinutes?: number;
  recurrence?: string;
  runDays?: number;
  dueOn?: string;
  isPrivate?: boolean;
  [key: string]: unknown;
}

export interface HelperRejectedItem {
  item?: unknown;
  reason?: string;
  title?: string;
  [key: string]: unknown;
}

export interface HelperUnsupportedItem {
  item?: unknown;
  reason?: string;
  title?: string;
  [key: string]: unknown;
}

export interface HelperDisplacedItem {
  behaviorId: string;
  behaviorName: string;
  minutes: number;
}

export interface HelperDraftResponse {
  draftId: string;
  items: HelperDraftItem[];
  assumptions: string[];
  rejected: HelperRejectedItem[];
  unsupported: HelperUnsupportedItem[];
  warnings: string[];
  displaced: HelperDisplacedItem[];
  dropped: HelperDisplacedItem[];
  clarify: string | null;
}

export interface HelperConfirmResponse {
  confirmationId: string;
  itemIds: string[];
  idempotent?: boolean;
  [key: string]: unknown;
}

export interface HelperDayItem {
  itemId: string;
  kind: "commitment" | "deadline" | string;
  title: string;
  isPrivate: boolean;
  startTime?: string;
  endTime?: string;
  dueOn?: string;
  date?: string;
}

export interface HelperStatus {
  configured: boolean;
  fastModel: string;
  strongModel: string;
}
