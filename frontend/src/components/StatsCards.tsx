import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  accentColor?: "accent" | "success" | "warning" | "info" | "destructive";
}

const accentClasses = {
  accent: "before:bg-accent",
  success: "before:bg-success",
  warning: "before:bg-warning",
  info: "before:bg-info",
  destructive: "before:bg-destructive",
};

const iconBgClasses = {
  accent: "bg-accent/10 text-accent",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  info: "bg-info/10 text-info",
  destructive: "bg-destructive/10 text-destructive",
};

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  accentColor = "accent",
}: StatCardProps) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendClass =
    trend === "up"
      ? "text-success"
      : trend === "down"
      ? "text-destructive"
      : "text-muted-foreground";

  return (
    <div
      className={cn(
        "stat-card animate-fade-up",
        accentClasses[accentColor]
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg",
            iconBgClasses[accentColor]
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>

      {trend && trendValue && (
        <div className="mt-4 flex items-center gap-1.5 border-t border-border pt-3">
          <TrendIcon className={cn("h-4 w-4", trendClass)} />
          <span className={cn("text-sm font-medium", trendClass)}>
            {trendValue}
          </span>
          <span className="text-sm text-muted-foreground">vs last period</span>
        </div>
      )}
    </div>
  );
}

interface StatsCardsProps {
  stats: Array<StatCardProps>;
  className?: string;
}

export function StatsCards({ stats, className }: StatsCardsProps) {
  return (
    <div
      className={cn(
        "grid gap-4 sm:grid-cols-2 lg:grid-cols-4",
        className
      )}
    >
      {stats.map((stat, index) => (
        <StatCard key={index} {...stat} />
      ))}
    </div>
  );
}
