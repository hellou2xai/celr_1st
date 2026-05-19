import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { api } from "@/api/client";
import { money, num, pct, dt } from "@/lib/format";
import { LineChartC, moneyFmt } from "@/components/Chart";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { DrillIcon } from "@/components/DrillDown";

interface Resp {
  mode: "movers" | "item";
  rows?: Array<{ UPC: string; Description: string; Cost: number; LatestPaid: number; AvgPaid: number; DriftPct: number | null }>;
  series?: Array<{ Date: string; UnitCost: number }>;
  current?: { Cost: number; Price: number };
}

export function CostAnalysis() {
  const [params, setParams] = useSearchParams();
  const [upcInput, setUpcInput] = useState(params.get("upc") ?? "");
  const q = useQuery<Resp>({
    queryKey: ["cost", params.toString()],
    queryFn: () => api.get("/api/cost", Object.fromEntries(params)),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Cost Analysis</h1>
      <p className="text-sm text-muted mb-4">Purchase cost over time — vs current cost on file, vs historical average paid.</p>
      <form onSubmit={e => { e.preventDefault(); setParams({ upc: upcInput }); }}
            className="flex gap-2 items-end mb-4">
        <label className="text-xs text-muted">UPC <Input value={upcInput} onChange={e=>setUpcInput(e.target.value)} className="mt-1 w-56 font-mono" placeholder="empty = top movers"/></label>
        <Button type="submit">Load</Button>
      </form>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data?.mode === "movers" && q.data.rows && (
        <>
          <h2 className="text-lg font-semibold mb-2">Recent cost movers</h2>
          <div className="rounded border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Current</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Latest paid</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Avg paid</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Drift %</th>
              </tr></thead>
              <tbody>
                {q.data.rows.map((r, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                    <td className="px-3 py-1.5">{r.Description}</td>
                    <td className="num px-3 py-1.5">{money(r.Cost, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{money(r.LatestPaid, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{money(r.AvgPaid, { digits: 2 })}</td>
                    <td className={"num px-3 py-1.5 " + ((r.DriftPct ?? 0) > 0 ? "text-bad" : "text-good")}>{pct(r.DriftPct ?? 0, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {q.data?.mode === "item" && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-xs uppercase tracking-wider text-muted mb-2">
            Unit cost paid over time
            {q.data.current && <span className="ml-3 text-muted font-normal">current cost on file: {money(q.data.current.Cost, { digits: 2 })}</span>}
          </h3>
          {q.data.series?.length ? (
            <LineChartC data={q.data.series} xKey="Date" yKeys={["UnitCost"]} formatY={moneyFmt} height={300}/>
          ) : (
            <p className="text-sm text-muted">No PO history.</p>
          )}
        </div>
      )}
    </div>
  );
}
