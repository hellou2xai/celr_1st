import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

type Variant = "info" | "good" | "warn" | "bad" | "neutral";

const variantToClass: Record<Variant, string> = {
  info:    "border-info/40    hover:border-info",
  good:    "border-good/40    hover:border-good",
  warn:    "border-warn/40    hover:border-warn",
  bad:     "border-bad/40     hover:border-bad",
  neutral: "border-border     hover:border-muted",
};

export interface KpiTileProps {
  label: string;
  value: string | number;
  sub?: string;
  variant?: Variant;
  to?: string;
}

export function KpiTile({ label, value, sub, variant = "neutral", to }: KpiTileProps) {
  const inner = (
    <div className={cn(
      "flex flex-col gap-1 rounded-lg bg-card border p-4 transition-colors",
      "min-h-[100px]",
      variantToClass[variant]
    )}>
      <div className="text-[11px] uppercase tracking-wider text-muted font-semibold">{label}</div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
  return to ? <Link to={to} className="block">{inner}</Link> : inner;
}
