import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { KpiTile } from "@/components/KpiTile";
import { RiskBadge } from "@/components/RiskBadge";
import { money, num, dt } from "@/lib/format";
import { DrillIcon } from "@/components/DrillDown";

interface Line {
  UPC: string; Description: string; Supplier?: string; Department?: string;
  QtyToOrder: number; OnHand?: number; AvgMonthlySales?: number;
  MoSNow?: number | null; MoSAfterOrder?: number | null;
  UnitCost?: number; LineCost?: number; Risk: string;
}
interface Resp {
  lines: Line[];
  summary: Array<{ Risk: string; Lines: number; Value: number }>;
  raw: string;
}

const EXAMPLE = `# Paste UPC + qty per line, comma or space separated
8954044932 12
8954044899 6
8954046308 3`;

export function RiskCalc() {
  const [text, setText] = useState(EXAMPLE);
  const [months, setMonths] = useState(18);
  const [result, setResult] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setLoading(true); setErr(null);
    try {
      const r = await api.post<Resp>("/api/risk-calc", { lines: text, history_months: months });
      setResult(r);
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally { setLoading(false); }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Pre-PO Risk Calculator</h1>
      <p className="text-sm text-muted mb-4">Paste a list of UPCs + quantities you're about to order. We resolve them and grade the risk of overbuying or stockout.</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="md:col-span-2">
          <label className="block text-xs text-muted mb-1">Lines (UPC then qty)</label>
          <Textarea value={text} onChange={e => setText(e.target.value)} rows={10}/>
        </div>
        <div className="flex flex-col gap-3">
          <label className="block text-xs text-muted">History months
            <Input type="number" value={months} onChange={e => setMonths(parseInt(e.target.value) || 18)} className="mt-1"/>
          </label>
          <Button onClick={run} disabled={loading}>{loading ? "Calculating…" : "Calculate"}</Button>
          {err && <p className="text-xs text-bad">{err}</p>}
        </div>
      </div>

      {result && (
        <>
          <h2 className="text-lg font-semibold mb-2">Risk summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {result.summary.map(s => (
              <KpiTile key={s.Risk} label={s.Risk}
                value={num(s.Lines)} sub={money(s.Value)}
                variant={s.Risk === "Critical" || s.Risk === "Excess" ? "bad" : s.Risk === "High" ? "warn" : "info"}/>
            ))}
          </div>

          <h2 className="text-lg font-semibold mb-2">Line breakdown</h2>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Description</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Qty</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">OH</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Avg/Mo</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">MoS now</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">MoS after</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Line $</th>
                <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Risk</th>
              </tr></thead>
              <tbody>
                {result.lines.map((l, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-3 py-2 font-mono" data-upc={l.UPC}>{l.UPC} <DrillIcon upc={l.UPC}/></td>
                    <td className="px-3 py-2">{l.Description}</td>
                    <td className="num px-3 py-2">{num(l.QtyToOrder)}</td>
                    <td className="num px-3 py-2">{l.OnHand != null ? num(l.OnHand) : "—"}</td>
                    <td className="num px-3 py-2">{l.AvgMonthlySales != null ? num(l.AvgMonthlySales, 2) : "—"}</td>
                    <td className="num px-3 py-2">{l.MoSNow == null ? "∞" : num(l.MoSNow, 1)}</td>
                    <td className="num px-3 py-2">{l.MoSAfterOrder == null ? "∞" : num(l.MoSAfterOrder, 1)}</td>
                    <td className="num px-3 py-2">{l.LineCost != null ? money(l.LineCost, { digits: 2 }) : "—"}</td>
                    <td className="px-3 py-2"><RiskBadge risk={l.Risk}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

interface Alias {
  ID: number; Alias: string; RMSCode: string;
  Description: string; CreatedAt: string;
}

export function RiskCalcAliases() {
  const q = useQuery<{ rows: Alias[]; count: number }>({
    queryKey: ["risk-aliases"],
    queryFn: () => api.get("/api/risk-calc/aliases"),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Risk Calc Aliases</h1>
      <p className="text-sm text-muted mb-4">Maps supplier UPC variants to canonical RMS lookup codes. Used by the Pre-PO Risk Calculator.</p>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && !q.data.rows.length && (
        <p className="text-sm text-muted">No aliases yet.</p>
      )}
      {q.data && !!q.data.rows.length && (
        <>
          <p className="text-xs text-muted mb-2">{num(q.data.count)} aliases</p>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Alias</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">RMS code</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Created</th>
              </tr></thead>
              <tbody>
                {q.data.rows.map(r => (
                  <tr key={r.ID} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono">{r.Alias}</td>
                    <td className="px-3 py-1.5 font-mono">{r.RMSCode}</td>
                    <td className="px-3 py-1.5">{r.Description}</td>
                    <td className="px-3 py-1.5 text-xs text-muted">{dt(r.CreatedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
