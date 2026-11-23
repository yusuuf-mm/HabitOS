import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/services/apiClient";
import type { SelectedBlock, ItemDetail, RangeEntry } from "@/types/dashboard";

interface DayDetailPanelProps {
  block: SelectedBlock;
  onClose: () => void;
  onChanged: () => void;
  onOpenBlock?: (block: SelectedBlock) => void;
}

export function DayDetailPanel({
  block,
  onClose,
  onChanged,
  onOpenBlock,
}: DayDetailPanelProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [active, setActive] = useState<SelectedBlock>(block);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [detail, setDetail] = useState<ItemDetail | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formStartTime, setFormStartTime] = useState("");
  const [formStartDate, setFormStartDate] = useState("");
  const [formDueOn, setFormDueOn] = useState("");

  // The panel owns its displayed state. The dashboard refetches after a change,
  // but the block prop is a snapshot, so without this the panel would keep
  // showing "Planned" after the user marked a session complete.
  useEffect(() => {
    setActive(block);
    setConfirmDelete(false);
    setEditing(false);
    setNotice(null);
  }, [block]);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const isItem = active.type === "commitment" || active.type === "deadline";
  const item: RangeEntry | null = isItem ? (active as { item: RangeEntry }).item : null;

  useEffect(() => {
    if (!item) return;
    let cancelled = false;
    apiClient.items
      .get(item.itemId)
      .then((d) => {
        if (!cancelled) {
          setDetail(d);
          setFormTitle(d.title ?? item.title);
          setFormStartTime(d.startTime ?? item.startTime ?? "");
          setFormStartDate(d.startDate ?? item.date ?? "");
          setFormDueOn(d.dueOn ?? item.dueOn ?? item.date ?? "");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFormTitle(item.title);
          setFormStartTime(item.startTime ?? "");
          setFormStartDate(item.date ?? "");
          setFormDueOn(item.dueOn ?? item.date ?? "");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [item]);

  const run = async (
    fn: () => Promise<unknown>,
    ok: string,
    apply?: () => void,
  ): Promise<boolean> => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      apply?.();
      setNotice(ok);
      onChanged();
      return true;
    } catch (e) {
      setNotice((e as { message?: string }).message ?? "That could not be saved.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const patchSession = (patch: Partial<Extract<SelectedBlock, { type: "session" }>["session"]>) => {
    setActive((prev) =>
      prev.type === "session" ? { ...prev, session: { ...prev.session, ...patch } } : prev,
    );
  };

  const patchItem = (patch: Partial<RangeEntry>) => {
    setActive((prev) =>
      prev.type === "commitment" || prev.type === "deadline"
        ? { ...prev, item: { ...prev.item, ...patch } }
        : prev,
    );
  };

  const handleSaveEdit = () => {
    if (!item) return;
    const changes: Record<string, unknown> = {};
    if (formTitle && formTitle !== (detail?.title ?? item.title)) changes.title = formTitle;
    if (item.kind === "commitment" && formStartTime && formStartTime !== (detail?.startTime ?? item.startTime))
      changes.startTime = formStartTime;
    if (item.kind === "commitment" && formStartDate && formStartDate !== (detail?.startDate ?? item.date))
      changes.startDate = formStartDate;
    if (item.kind === "deadline" && formDueOn && formDueOn !== (detail?.dueOn ?? item.dueOn ?? item.date))
      changes.dueOn = formDueOn;
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      return;
    }
    void run(
      () => apiClient.items.update(item.itemId, changes),
      "Saved.",
      () => {
        setDetail((prev) => (prev ? { ...prev, ...changes } : prev));
        patchItem(changes as Partial<RangeEntry>);
      },
    );
    setEditing(false);
  };

  const durationOf = (start?: string, end?: string): number | null => {
    if (!start || !end) return null;
    const [sh, sm] = start.split(":").map(Number);
    const [eh, em] = end.split(":").map(Number);
    return eh * 60 + em - (sh * 60 + sm);
  };

  let title = "";
  let content: React.ReactNode = null;

  if (active.type === "session") {
    const s = active.session;
    title = s.title;
    const released = Boolean(s.releasedAt);
    const meaning = s.objectiveName
      ? `${s.behaviorName}, ${s.duration} min. Counts toward ${s.objectiveName}.`
      : `${s.behaviorName}, ${s.duration} min.`;
    content = (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {s.startTime}–{s.endTime} · {s.duration} min
        </p>
        <p className="text-sm">{meaning}</p>
        <p className="text-sm">
          {released ? (
            <span className="status-badge status-badge-info">Released</span>
          ) : s.completed ? (
            <span className="status-badge status-badge-success">Completed</span>
          ) : (
            <span className="status-badge status-badge-info">Planned</span>
          )}
        </p>
        {released && (
          <p className="text-xs text-muted-foreground">
            Withdrawn before it started. It is not counted as missed.
          </p>
        )}
        {!released && (
          <div className="flex flex-wrap gap-2">
            {s.completed ? (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => apiClient.schedule.markBehaviorIncomplete(s.id),
                    "Marked incomplete.",
                    () => patchSession({ completed: false }),
                  )
                }
              >
                Mark incomplete
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => apiClient.schedule.markBehaviorComplete(s.id),
                    "Marked complete.",
                    () => patchSession({ completed: true }),
                  )
                }
              >
                Mark complete
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              disabled={busy || s.completed}
              onClick={() =>
                void run(
                  () => apiClient.schedule.releaseSession(s.id),
                  "Released.",
                  () => patchSession({ releasedAt: new Date().toISOString() }),
                )
              }
            >
              Release
            </Button>
          </div>
        )}
      </div>
    );
  } else if (isItem && item) {
    const isCommitment = item.kind === "commitment";
    title = detail?.title ?? item.title;
    const dur = isCommitment ? durationOf(item.startTime, item.endTime) : null;
    const recurrence = detail?.recurrence;
    const recurring = Boolean(recurrence && recurrence !== "once");
    content = (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {isCommitment
            ? `${item.startTime ?? ""}–${item.endTime ?? ""}${dur ? ` · ${dur} min` : ""} · ${item.date}`
            : `Due ${item.dueOn ?? item.date}`}
        </p>
        {recurring && (
          <p className="text-xs text-muted-foreground">Repeats: {recurrence}</p>
        )}
        {item.isPrivate && <p className="text-xs text-muted-foreground">Private</p>}
        {(item.warnings ?? []).length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800 dark:text-amber-200">
            {item.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
        {editing ? (
          <div className="space-y-2">
            <label className="block text-xs font-medium">
              Title
              <input
                type="text"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                className="mt-1 min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </label>
            {isCommitment && (
              <>
                <label className="block text-xs font-medium">
                  Start time
                  <input
                    type="time"
                    value={formStartTime}
                    onChange={(e) => setFormStartTime(e.target.value)}
                    className="mt-1 min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </label>
                <label className="block text-xs font-medium">
                  Start date
                  <input
                    type="date"
                    value={formStartDate}
                    onChange={(e) => setFormStartDate(e.target.value)}
                    className="mt-1 min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </label>
              </>
            )}
            {!isCommitment && (
              <label className="block text-xs font-medium">
                Deadline date
                <input
                  type="date"
                  value={formDueOn}
                  onChange={(e) => setFormDueOn(e.target.value)}
                  className="mt-1 min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </label>
            )}
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSaveEdit} disabled={busy}>
                Save
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() =>
                void run(
                  () => apiClient.items.update(item.itemId, { isPrivate: !item.isPrivate }),
                  item.isPrivate ? "Now public." : "Now private.",
                  () => {
                    const next = !item.isPrivate;
                    setDetail((prev) => (prev ? { ...prev, isPrivate: next } : prev));
                    patchItem({ isPrivate: next });
                  },
                )
              }
            >
              {item.isPrivate ? "Make public" : "Make private"}
            </Button>
            {confirmDelete ? (
              <>
                <span className="text-sm">
                  {recurring ? "Delete this whole series?" : "Are you sure?"}
                </span>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busy}
                  onClick={async () => {
                    // Close only when the delete actually succeeded.
                    const ok = await run(() => apiClient.items.remove(item.itemId), "Deleted.");
                    if (ok) onClose();
                  }}
                >
                  {recurring ? "Confirm delete series" : "Confirm delete"}
                </Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setConfirmDelete(true)}>
                {recurring ? "Delete series" : "Delete"}
              </Button>
            )}
          </div>
        )}
      </div>
    );
  } else if (active.type === "day") {
    const d = active.day;
    title = new Date(`${d.date}T00:00:00`).toLocaleDateString("en-US", {
      weekday: "long",
      month: "short",
      day: "numeric",
    });
    const openBlock = onOpenBlock ?? (() => undefined);
    const all = [
      ...d.sessions.map((s) => ({
        time: s.startTime,
        label: `${s.startTime}–${s.endTime} · ${s.title} (session)`,
        open: () => openBlock({ type: "session" as const, day: d, session: s }),
      })),
      ...d.commitments.map((c) => ({
        time: c.startTime ?? "99:99",
        label: `${c.startTime ?? ""}–${c.endTime ?? ""} · ${c.title} (fixed)`,
        open: () => openBlock({ type: "commitment" as const, day: d, item: c }),
      })),
      ...d.deadlines.map((dl) => ({
        time: "99:99",
        label: `Deadline · ${dl.title}`,
        open: () => openBlock({ type: "deadline" as const, day: d, item: dl }),
      })),
    ].sort((a, b) => a.time.localeCompare(b.time));
    content = (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {d.sessions.length} sessions, {d.commitments.length} commitments, {d.deadlines.length} deadline(s)
        </p>
        {all.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {d.unavailable ? "This day could not be loaded." : "Nothing planned"}
          </p>
        ) : (
          <ul className="space-y-1.5">
            {all.map((entry, i) => (
              <li key={i} className="text-sm">
                <button
                  type="button"
                  onClick={entry.open}
                  className="rounded text-left underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  {entry.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      role="dialog"
      aria-label={title || "Details"}
      className="fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-2xl border border-border bg-card p-5 shadow-lg sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-4 sm:max-h-[calc(100vh-2rem)] sm:w-80 sm:rounded-xl"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold">{title}</h2>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close details">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-3">{content}</div>
      {notice && <p className="mt-3 text-sm text-muted-foreground">{notice}</p>}
    </aside>
  );
}
