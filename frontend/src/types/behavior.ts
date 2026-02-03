export type BehaviorCategory =
  | "health"
  | "productivity"
  | "learning"
  | "social"
  | "financial"
  | "creativity"
  | "mindfulness"
  | "wellness";

export type TimeSlot =
  | "early_morning"
  | "morning"
  | "midday"
  | "afternoon"
  | "evening"
  | "night"
  | "flexible";

export interface ObjectiveImpact {
  objectiveId: string;
  objectiveName: string;
  impactScore: number; // -1 to 1
}

export interface Behavior {
  id: string;
  userId: string;
  name: string;
  description: string;
  category: BehaviorCategory;
  energyCost: number; // 1-10
  durationMin: number; // minutes
  durationMax: number; // minutes
  preferredTimeSlots: TimeSlot[];
  objectiveImpacts: ObjectiveImpact[];
  isActive: boolean;
  frequency: "daily" | "weekly" | "custom";
  frequencyCount?: number; // times per frequency period
  createdAt: string;
  updatedAt: string;
}

export interface BehaviorFormData {
  name: string;
  description: string;
  category: BehaviorCategory;
  energyCost: number;
  durationMin: number;
  durationMax: number;
  preferredTimeSlots: TimeSlot[];
  objectiveImpacts: ObjectiveImpact[];
  isActive: boolean;
  frequency: "daily" | "weekly" | "custom";
  frequencyCount?: number;
}

export interface Objective {
  id: string;
  userId: string;
  name: string;
  description: string;
  priority: number; // 1-10
  createdAt: string;
}

export interface Constraint {
  id: string;
  userId: string;
  name: string;
  type: "time" | "energy" | "frequency";
  value: number;
  unit: string;
  createdAt: string;
}
