import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { BehaviorForm } from "@/components/BehaviorForm";
import { BehaviorList } from "@/components/BehaviorList";
import { PageLoader } from "@/components/Loader";
import { apiClient } from "@/services/apiClient";
import { useToast } from "@/hooks/use-toast";
import type { Behavior, BehaviorFormData, Objective } from "@/types";

export default function Behaviors() {
  const { toast } = useToast();
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBehavior, setEditingBehavior] = useState<Behavior | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [behaviorsRes, objectivesRes] = await Promise.all([
        apiClient.behaviors.getBehaviors(),
        apiClient.behaviors.getObjectives(),
      ]);
      setBehaviors(behaviorsRes.data.data);
      setObjectives(objectivesRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast({
        title: "Error",
        description: "Failed to load behaviors",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async (data: BehaviorFormData) => {
    setIsSubmitting(true);
    try {
      const response = await apiClient.behaviors.createBehavior(data);
      setBehaviors((prev) => [response.data, ...prev]);
      setDialogOpen(false);
      toast({
        title: "Success",
        description: "Behavior created successfully",
      });
    } catch (error) {
      console.error("Failed to create behavior:", error);
      toast({
        title: "Error",
        description: "Failed to create behavior",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async (data: BehaviorFormData) => {
    if (!editingBehavior) return;

    setIsSubmitting(true);
    try {
      const response = await apiClient.behaviors.updateBehavior(
        editingBehavior.id,
        data
      );
      setBehaviors((prev) =>
        prev.map((b) => (b.id === editingBehavior.id ? response.data : b))
      );
      setEditingBehavior(null);
      setDialogOpen(false);
      toast({
        title: "Success",
        description: "Behavior updated successfully",
      });
    } catch (error) {
      console.error("Failed to update behavior:", error);
      toast({
        title: "Error",
        description: "Failed to update behavior",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.behaviors.deleteBehavior(id);
      setBehaviors((prev) => prev.filter((b) => b.id !== id));
      toast({
        title: "Success",
        description: "Behavior deleted successfully",
      });
    } catch (error) {
      console.error("Failed to delete behavior:", error);
      toast({
        title: "Error",
        description: "Failed to delete behavior",
        variant: "destructive",
      });
    }
  };

  const handleToggleActive = async (id: string, isActive: boolean) => {
    try {
      const response = await apiClient.behaviors.updateBehavior(id, { isActive });
      setBehaviors((prev) =>
        prev.map((b) => (b.id === id ? response.data : b))
      );
      toast({
        title: "Success",
        description: `Behavior ${isActive ? "activated" : "deactivated"}`,
      });
    } catch (error) {
      console.error("Failed to toggle behavior:", error);
      toast({
        title: "Error",
        description: "Failed to update behavior",
        variant: "destructive",
      });
    }
  };

  const handleEdit = (behavior: Behavior) => {
    setEditingBehavior(behavior);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingBehavior(null);
  };

  if (isLoading) {
    return <PageLoader text="Loading behaviors..." />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="page-header mb-0">
          <h1 className="page-title">Behaviors</h1>
          <p className="page-subtitle">
            Define and manage your daily behaviors for optimization
          </p>
        </div>
        <Button
          onClick={() => setDialogOpen(true)}
          className="gap-2 bg-accent text-accent-foreground hover:bg-accent/90"
        >
          <Plus className="h-4 w-4" />
          Add Behavior
        </Button>
      </div>

      {/* Stats Summary */}
      <div className="flex flex-wrap gap-4 rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Total:</span>
          <span className="font-medium text-foreground">{behaviors.length}</span>
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Active:</span>
          <span className="font-medium text-success">
            {behaviors.filter((b) => b.isActive).length}
          </span>
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Inactive:</span>
          <span className="font-medium text-warning">
            {behaviors.filter((b) => !b.isActive).length}
          </span>
        </div>
      </div>

      {/* Behavior List */}
      <BehaviorList
        behaviors={behaviors}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onToggleActive={handleToggleActive}
      />

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingBehavior ? "Edit Behavior" : "Create Behavior"}
            </DialogTitle>
          </DialogHeader>
          <BehaviorForm
            initialData={editingBehavior || undefined}
            objectives={objectives}
            onSubmit={editingBehavior ? handleUpdate : handleCreate}
            onCancel={handleCloseDialog}
            isLoading={isSubmitting}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
