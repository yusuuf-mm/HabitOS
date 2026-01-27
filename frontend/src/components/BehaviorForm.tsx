import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import type { BehaviorFormData, BehaviorCategory, TimeSlot, Objective } from "@/types";

interface BehaviorFormProps {
  initialData?: Partial<BehaviorFormData>;
  objectives: Objective[];
  onSubmit: (data: BehaviorFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const CATEGORIES: { value: BehaviorCategory; label: string }[] = [
  { value: "health", label: "Health" },
  { value: "productivity", label: "Productivity" },
  { value: "learning", label: "Learning" },
  { value: "social", label: "Social" },
  { value: "financial", label: "Financial" },
  { value: "creativity", label: "Creativity" },
  { value: "mindfulness", label: "Mindfulness" },
];

const TIME_SLOTS: { value: TimeSlot; label: string }[] = [
  { value: "early_morning", label: "Early Morning (5-7am)" },
  { value: "morning", label: "Morning (7-12pm)" },
  { value: "midday", label: "Midday (12-2pm)" },
  { value: "afternoon", label: "Afternoon (2-5pm)" },
  { value: "evening", label: "Evening (5-9pm)" },
  { value: "night", label: "Night (9pm+)" },
];

export function BehaviorForm({
  initialData,
  objectives,
  onSubmit,
  onCancel,
  isLoading = false,
}: BehaviorFormProps) {
  const [formData, setFormData] = useState<BehaviorFormData>({
    name: initialData?.name || "",
    description: initialData?.description || "",
    category: initialData?.category || "productivity",
    energyCost: initialData?.energyCost || 5,
    durationMin: initialData?.durationMin || 15,
    durationMax: initialData?.durationMax || 30,
    preferredTimeSlots: initialData?.preferredTimeSlots || [],
    objectiveImpacts: initialData?.objectiveImpacts || [],
    isActive: initialData?.isActive ?? true,
    frequency: initialData?.frequency || "daily",
    frequencyCount: initialData?.frequencyCount,
  });

  const handleTimeSlotToggle = (slot: TimeSlot) => {
    setFormData((prev) => ({
      ...prev,
      preferredTimeSlots: prev.preferredTimeSlots.includes(slot)
        ? prev.preferredTimeSlots.filter((s) => s !== slot)
        : [...prev.preferredTimeSlots, slot],
    }));
  };

  const handleObjectiveAdd = (objectiveId: string) => {
    const objective = objectives.find((o) => o.id === objectiveId);
    if (objective && !formData.objectiveImpacts.find((oi) => oi.objectiveId === objectiveId)) {
      setFormData((prev) => ({
        ...prev,
        objectiveImpacts: [
          ...prev.objectiveImpacts,
          { objectiveId, objectiveName: objective.name, impactScore: 0.5 },
        ],
      }));
    }
  };

  const handleObjectiveRemove = (objectiveId: string) => {
    setFormData((prev) => ({
      ...prev,
      objectiveImpacts: prev.objectiveImpacts.filter((oi) => oi.objectiveId !== objectiveId),
    }));
  };

  const handleObjectiveImpactChange = (objectiveId: string, impactScore: number) => {
    setFormData((prev) => ({
      ...prev,
      objectiveImpacts: prev.objectiveImpacts.map((oi) =>
        oi.objectiveId === objectiveId ? { ...oi, impactScore } : oi
      ),
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const availableObjectives = objectives.filter(
    (o) => !formData.objectiveImpacts.find((oi) => oi.objectiveId === o.id)
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Info */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Behavior Name</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Morning Run"
            required
            className="input-focus"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
            placeholder="Brief description of this behavior..."
            rows={2}
            className="input-focus resize-none"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Category</Label>
            <Select
              value={formData.category}
              onValueChange={(value: BehaviorCategory) =>
                setFormData((prev) => ({ ...prev, category: value }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Frequency</Label>
            <Select
              value={formData.frequency}
              onValueChange={(value: "daily" | "weekly" | "custom") =>
                setFormData((prev) => ({ ...prev, frequency: value }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Energy & Duration */}
      <div className="space-y-4 rounded-lg border border-border p-4">
        <h3 className="font-medium text-foreground">Energy & Duration</h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Energy Cost</Label>
            <span className="text-sm font-medium text-accent">{formData.energyCost}/10</span>
          </div>
          <Slider
            value={[formData.energyCost]}
            onValueChange={(value) => setFormData((prev) => ({ ...prev, energyCost: value[0] }))}
            min={1}
            max={10}
            step={1}
            className="w-full"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="durationMin">Min Duration (mins)</Label>
            <Input
              id="durationMin"
              type="number"
              value={formData.durationMin}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, durationMin: parseInt(e.target.value) || 0 }))
              }
              min={5}
              className="input-focus"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="durationMax">Max Duration (mins)</Label>
            <Input
              id="durationMax"
              type="number"
              value={formData.durationMax}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, durationMax: parseInt(e.target.value) || 0 }))
              }
              min={5}
              className="input-focus"
            />
          </div>
        </div>
      </div>

      {/* Time Slots */}
      <div className="space-y-3">
        <Label>Preferred Time Slots</Label>
        <div className="flex flex-wrap gap-2">
          {TIME_SLOTS.map((slot) => (
            <Badge
              key={slot.value}
              variant={formData.preferredTimeSlots.includes(slot.value) ? "default" : "outline"}
              className="cursor-pointer transition-colors"
              onClick={() => handleTimeSlotToggle(slot.value)}
            >
              {slot.label}
            </Badge>
          ))}
        </div>
      </div>

      {/* Objective Impacts */}
      <div className="space-y-3">
        <Label>Objective Impacts</Label>
        
        {formData.objectiveImpacts.length > 0 && (
          <div className="space-y-3">
            {formData.objectiveImpacts.map((impact) => (
              <div
                key={impact.objectiveId}
                className="flex items-center gap-3 rounded-lg border border-border p-3"
              >
                <div className="flex-1 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{impact.objectiveName}</span>
                    <span className="text-xs text-muted-foreground">
                      {impact.impactScore > 0 ? "+" : ""}
                      {(impact.impactScore * 100).toFixed(0)}%
                    </span>
                  </div>
                  <Slider
                    value={[impact.impactScore]}
                    onValueChange={(value) =>
                      handleObjectiveImpactChange(impact.objectiveId, value[0])
                    }
                    min={-1}
                    max={1}
                    step={0.05}
                    className="w-full"
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => handleObjectiveRemove(impact.objectiveId)}
                  className="h-8 w-8 text-muted-foreground hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {availableObjectives.length > 0 && (
          <Select onValueChange={handleObjectiveAdd}>
            <SelectTrigger className="w-full">
              <div className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                <span>Add objective impact</span>
              </div>
            </SelectTrigger>
            <SelectContent>
              {availableObjectives.map((obj) => (
                <SelectItem key={obj.id} value={obj.id}>
                  {obj.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Active Toggle */}
      <div className="flex items-center justify-between rounded-lg border border-border p-4">
        <div className="space-y-0.5">
          <Label htmlFor="isActive" className="cursor-pointer">
            Active Behavior
          </Label>
          <p className="text-xs text-muted-foreground">
            Include in optimization runs
          </p>
        </div>
        <Switch
          id="isActive"
          checked={formData.isActive}
          onCheckedChange={(checked) => setFormData((prev) => ({ ...prev, isActive: checked }))}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} className="flex-1">
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={isLoading}
          className="flex-1 bg-accent text-accent-foreground hover:bg-accent/90"
        >
          {initialData ? "Update Behavior" : "Create Behavior"}
        </Button>
      </div>
    </form>
  );
}
