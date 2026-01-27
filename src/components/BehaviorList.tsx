import {
  Edit2,
  Trash2,
  Clock,
  Zap,
  MoreVertical,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { Behavior, BehaviorCategory } from "@/types";

interface BehaviorListProps {
  behaviors: Behavior[];
  onEdit: (behavior: Behavior) => void;
  onDelete: (id: string) => void;
  onToggleActive?: (id: string, isActive: boolean) => void;
}

const categoryColors: Record<BehaviorCategory, string> = {
  health: "bg-success/10 text-success border-success/20",
  productivity: "bg-info/10 text-info border-info/20",
  learning: "bg-accent/10 text-accent border-accent/20",
  social: "bg-warning/10 text-warning border-warning/20",
  financial: "bg-foreground/10 text-foreground border-foreground/20",
  creativity: "bg-destructive/10 text-destructive border-destructive/20",
  mindfulness: "bg-purple-500/10 text-purple-600 border-purple-500/20",
};

const categoryLabels: Record<BehaviorCategory, string> = {
  health: "Health",
  productivity: "Productivity",
  learning: "Learning",
  social: "Social",
  financial: "Financial",
  creativity: "Creativity",
  mindfulness: "Mindfulness",
};

export function BehaviorList({
  behaviors,
  onEdit,
  onDelete,
  onToggleActive,
}: BehaviorListProps) {
  if (behaviors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
        <p className="text-muted-foreground">No behaviors created yet</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Create your first behavior to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {behaviors.map((behavior, index) => (
        <div
          key={behavior.id}
          className={cn(
            "group dashboard-card flex items-start justify-between gap-4 p-4 transition-all hover:shadow-md",
            !behavior.isActive && "opacity-60"
          )}
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div className="min-w-0 flex-1 space-y-2">
            {/* Header */}
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-foreground truncate">
                {behavior.name}
              </h3>
              {behavior.isActive ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
            </div>

            {/* Description */}
            {behavior.description && (
              <p className="text-sm text-muted-foreground line-clamp-1">
                {behavior.description}
              </p>
            )}

            {/* Meta */}
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <Badge
                variant="outline"
                className={cn("border", categoryColors[behavior.category])}
              >
                {categoryLabels[behavior.category]}
              </Badge>

              <div className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                <span>
                  {behavior.durationMin}-{behavior.durationMax} min
                </span>
              </div>

              <div className="flex items-center gap-1">
                <Zap className="h-3.5 w-3.5" />
                <span>Energy: {behavior.energyCost}/10</span>
              </div>

              <span className="capitalize">
                {behavior.frequency}
                {behavior.frequency === "weekly" && behavior.frequencyCount
                  ? ` (${behavior.frequencyCount}x)`
                  : ""}
              </span>
            </div>

            {/* Time Slots */}
            {behavior.preferredTimeSlots.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {behavior.preferredTimeSlots.map((slot) => (
                  <span
                    key={slot}
                    className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                  >
                    {slot.replace("_", " ")}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onEdit(behavior)}>
                <Edit2 className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              {onToggleActive && (
                <DropdownMenuItem
                  onClick={() => onToggleActive(behavior.id, !behavior.isActive)}
                >
                  {behavior.isActive ? (
                    <>
                      <XCircle className="mr-2 h-4 w-4" />
                      Deactivate
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Activate
                    </>
                  )}
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                onClick={() => onDelete(behavior.id)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ))}
    </div>
  );
}
