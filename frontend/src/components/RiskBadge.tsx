import { cn } from "@/lib/utils";
import { riskSlug } from "@/lib/format";

export function RiskBadge({ risk, className }: { risk?: string | null; className?: string }) {
  if (!risk) return null;
  const slug = riskSlug(risk);
  return <span className={cn("badge", `badge-${slug}`, className)}>{risk}</span>;
}
