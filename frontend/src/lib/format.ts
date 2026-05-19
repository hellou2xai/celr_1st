// Ported from procurement_app/app.py: money/num/mos/dt/risk_class helpers.

export function money(v: number | string | null | undefined, opts: { digits?: number } = {}) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: opts.digits ?? 0,
    maximumFractionDigits: opts.digits ?? 0,
  });
}

export function num(v: number | string | null | undefined, digits = 0) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function pct(v: number | string | null | undefined, digits = 1) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  return `${n.toFixed(digits)}%`;
}

export function mos(v: number | string | null | undefined) {
  if (v == null || v === "") return "∞";
  const n = Number(v);
  if (!isFinite(n)) return String(v);
  return n.toFixed(1);
}

export function dt(v: string | Date | null | undefined) {
  if (!v) return "—";
  try {
    const d = typeof v === "string" ? new Date(v) : v;
    return d.toISOString().slice(0, 10);
  } catch {
    return String(v);
  }
}

export function dtTime(v: string | Date | null | undefined) {
  if (!v) return "—";
  try {
    const d = typeof v === "string" ? new Date(v) : v;
    return d.toISOString().slice(0, 16).replace("T", " ");
  } catch {
    return String(v);
  }
}

export type RiskTier =
  | "Critical"
  | "High"
  | "Moderate"
  | "Healthy"
  | "Excess"
  | "Dead"
  | "Out of Stock"
  | string;

export function riskSlug(risk: RiskTier | null | undefined): string {
  if (!risk) return "";
  return String(risk).toLowerCase().replace(/\s/g, "").replace("stock", "");
}
