// apps/web/src/components/dashboard/metric-card.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({
  title,
  value,
  description,
  trend,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        {description && (
          <p
            className={cn(
              "mt-1 text-xs",
              trend === "up" && "text-green-600",
              trend === "down" && "text-red-600",
              trend === "neutral" && "text-muted-foreground",
              !trend && "text-muted-foreground",
            )}
          >
            {description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
