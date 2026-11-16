import { useEffect, useState } from "react";
import { Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/services/apiClient";
import type { Objective } from "@/types";

interface ObjectiveWithWeight extends Objective {
  weight?: number;
}

export function WeightsEditor() {
  const [objectives, setObjectives] = useState<ObjectiveWithWeight[]>([]);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    apiClient.behaviors
      .getObjectives()
      .then((response) => {
        const items = response.data as ObjectiveWithWeight[];
        setObjectives(items);
        setDraft(
          Object.fromEntries(
            items.map((objective) => [objective.id, Math.round((objective.weight ?? 0) * 100)]),
          ),
        );
      })
      .catch(() => setMessage("Weights could not be loaded."));
  }, []);

  const handleSave = async (objectiveId: string) => {
    setSaving(objectiveId);
    try {
      const response = await apiClient.behaviors.updateObjectiveWeight(
        objectiveId,
        (draft[objectiveId] ?? 0) / 100,
      );
      const items = response.data as ObjectiveWithWeight[];
      setObjectives(items);
      setDraft(
        Object.fromEntries(
          items.map((objective) => [objective.id, Math.round((objective.weight ?? 0) * 100)]),
        ),
      );
      setMessage("Saved. The planner rescaled the rest so the weights still add up to 100%.");
    } catch {
      setMessage("That weight could not be saved; the old one still applies.");
    } finally {
      setSaving(null);
    }
  };

  const total = Object.values(draft).reduce((sum, value) => sum + value, 0);

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
      <div className="flex items-center gap-2">
        <Scale className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-medium text-foreground">What matters to you</h2>
      </div>
      <p className="text-xs text-muted-foreground">
        These weights decide what the planner favours. They are stored as a
        distribution: raising one lowers the others, and the sum is always 100%.
      </p>

      <ul className="space-y-2">
        {objectives.map((objective) => (
          <li key={objective.id} className="flex items-center gap-3">
            <label htmlFor={`weight-${objective.id}`} className="w-32 text-sm capitalize text-foreground">
              {objective.name}
            </label>
            <input
              id={`weight-${objective.id}`}
              type="range"
              min={0}
              max={100}
              value={draft[objective.id] ?? 0}
              onChange={(event) =>
                setDraft((previous) => ({
                  ...previous,
                  [objective.id]: Number(event.target.value),
                }))
              }
              className="h-2 flex-1 cursor-pointer accent-[hsl(var(--accent))]"
            />
            <span className="w-12 text-right text-sm tabular-nums text-muted-foreground">
              {draft[objective.id] ?? 0}%
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={saving !== null}
              onClick={() => handleSave(objective.id)}
            >
              Save
            </Button>
          </li>
        ))}
      </ul>

      <p className="text-xs text-muted-foreground">
        Current draft totals {total}%; saving asks the server to renormalise.
      </p>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
    </div>
  );
}
