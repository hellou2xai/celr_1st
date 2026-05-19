import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { api } from "@/api/client";
import { money, pct } from "@/lib/format";
import { LineChartC, moneyFmt } from "@/components/Chart";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { DrillIcon } from "@/components/DrillDown";

interface Resp {
  mode: "list" | "item";
  rows?: Array<{ UPC: string; Description: string; Cost: number; Price: number; AvgSold: number; MarginPct: number; PromoPct: number }>;
  series?: Array<{ Week: string; AvgSold: number; Txns: number }>;
  current?: { Cost: number; Price: number };
}

export function PricingAnalysis() {
  const [params, setParams] = useSearchParams();
  const [upcInput, setUpcInput] = useState(params.get("upc") ?? "");
  const q = useQuery<Resp>({
    queryKey: ["pricing", params.toString()],
    queryFn: () => api.get("/api/pricing", Object.fromEntries(params)),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Pricing Analytics</h1>
      <p className="text-sm text-muted mb-4">Retail vs cost vs avg-sold price. Tracks promo activity and margin.</p>
      <form onSubmit={e => { e.preventDefault(); setParams({ upc: upcInput }); }} className="flex gap-2 items-end mb-4">
        <label className="text-xs text-muted">UPC <Input value={upcInput} onChange={e=>setUpcInput(e.target.value)} className="mt-1 w-56 font-mono"/></label>
        <Button type="submit">Load</Button>
      </form>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data?.mode === "list" && q.data.rows && (
        <div className="rounded border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface/60"><tr>
              <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
              <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
              <th className="px-3 py-2 text-right text-xs uppercase text-muted">Cost</th>
              <th className="px-3 py-2 text-right text-xs uppercase text-muted">Retail</th>
              <th className="px-3 py-2 text-right text-xs uppercase text-muted">Avg sold</th>
              <th className="px-3 py-2 text-right text-xs uppercase text-muted">Margin %</th>
              <th className="px-3 py-2 text-right text-xs uppercase text-muted">Promo %</th>
            </tr></thead>
            <tbody>
              {q.data.rows.map((r, i) => (
                <tr key={i} className="border-t border-border/60">
                  <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                  <td className="px-3 py-1.5">{r.Description}</td>
                  <td className="num px-3 py-1.5">{money(r.Cost, { digits: 2 })}</td>
                  <td className="num px-3 py-1.5">{money(r.Price, { digits: 2 })}</td>
                  <td className="num px-3 py-1.5">{money(r.AvgSold, { digits: 2 })}</td>
                  <td className="num px-3 py-1.5">{pct(r.MarginPct, 1)}</td>
                  <td className="num px-3 py-1.5">{pct(r.PromoPct, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {q.data?.mode === "item" && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-xs uppercase tracking-wider text-muted mb-2">
            Avg sale price by week
            {q.data.current && <span className="ml-3 text-muted font-normal">retail: {money(q.data.current.Price, { digits: 2 })} · cost: {money(q.data.current.Cost, { digits: 2 })}</span>}
          </h3>
          {q.data.series?.length ? (
            <LineChartC data={q.data.series} xKey="Week" yKeys={["AvgSold"]} formatY={moneyFmt} height={300}/>
          ) : <p className="text-sm text-muted">No sales history.</p>}
        </div>
      )}
    </div>
  );
}
