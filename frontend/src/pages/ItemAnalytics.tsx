import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { LineChartC, BarChartC, moneyFmt } from "@/components/Chart";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface Resp {
  mode: "item" | "top";
  item?: { UPC: string; Description: string; Department: string; Category: string; Supplier: string; OnHand: number; Cost: number; Price: number };
  series?: Array<{ Bucket: string; UnitsSold: number; UnitsReceived: number; Revenue: number; AvgSalePrice: number }>;
  purchase_history?: Array<{ Bucket: string; UnitCost: number }>;
  top_items?: Array<{ ID: number; UPC: string; Description: string; Revenue: number; Units: number }>;
}

export function ItemAnalytics() {
  const [params, setParams] = useSearchParams();
  const [upcInput, setUpcInput] = useState(params.get("upc") ?? "");
  const q = useQuery<Resp>({
    queryKey: ["item-analytics", params.toString()],
    queryFn: () => api.get("/api/analytics/item", Object.fromEntries(params)),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Item Analytics</h1>
      <p className="text-sm text-muted mb-4">Sales velocity, cost trend, and price elasticity for a single SKU.</p>

      <form onSubmit={e => { e.preventDefault(); setParams({ upc: upcInput, months: params.get("months") ?? "24" }); }}
            className="flex gap-2 items-end mb-4">
        <label className="text-xs text-muted">UPC <Input value={upcInput} onChange={e=>setUpcInput(e.target.value)} className="mt-1 w-56 font-mono"/></label>
        <label className="text-xs text-muted">Months <Input type="number" defaultValue={params.get("months") ?? "24"}
          onChange={e=>setParams({ upc: upcInput, months: e.target.value })} className="mt-1 w-24"/></label>
        <Button type="submit">Load</Button>
      </form>

      {q.isLoading && <div className="text-muted">Loading…</div>}

      {q.data?.mode === "top" && (
        <>
          <h2 className="text-lg font-semibold mb-2">Top items (last 180 days)</h2>
          <p className="text-xs text-muted mb-2">Pick one to drill in by entering its UPC above.</p>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Units</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Revenue</th>
              </tr></thead>
              <tbody>
                {q.data.top_items?.map(r => (
                  <tr key={r.ID} className="border-t border-border/60 hover:bg-surface/40 cursor-pointer"
                      onClick={() => { setUpcInput(r.UPC); setParams({ upc: r.UPC, months: "24" }); }}>
                    <td className="px-3 py-1.5 font-mono">{r.UPC}</td>
                    <td className="px-3 py-1.5">{r.Description}</td>
                    <td className="num px-3 py-1.5">{num(r.Units)}</td>
                    <td className="num px-3 py-1.5">{money(r.Revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {q.data?.mode === "item" && q.data.item && (
        <>
          <div className="rounded border border-border bg-card p-4 mb-4">
            <div className="text-lg font-semibold"><code className="text-accent">{q.data.item.UPC}</code> · {q.data.item.Description}</div>
            <div className="text-xs text-muted">{q.data.item.Department} › {q.data.item.Category} · supplier {q.data.item.Supplier}</div>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mt-3">
              <Mini label="OnHand" value={num(q.data.item.OnHand)}/>
              <Mini label="Cost"   value={money(q.data.item.Cost, { digits: 2 })}/>
              <Mini label="Price"  value={money(q.data.item.Price, { digits: 2 })}/>
              <Mini label="Margin" value={money(q.data.item.Price - q.data.item.Cost, { digits: 2 })}/>
            </div>
          </div>

          {!!q.data.series?.length && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <Chart title="Units sold over time">
                <BarChartC data={q.data.series} xKey="Bucket" yKeys={["UnitsSold"]} labels={{UnitsSold:"Units"}}/>
              </Chart>
              <Chart title="Revenue per bucket">
                <BarChartC data={q.data.series} xKey="Bucket" yKeys={["Revenue"]} labels={{Revenue:"Revenue"}} formatY={moneyFmt}/>
              </Chart>
              <Chart title="Avg sale price">
                <LineChartC data={q.data.series} xKey="Bucket" yKeys={["AvgSalePrice"]} labels={{AvgSalePrice:"Avg price"}} formatY={moneyFmt}/>
              </Chart>
              <Chart title="Purchase cost over time">
                <LineChartC data={q.data.purchase_history ?? []} xKey="Bucket" yKeys={["UnitCost"]} labels={{UnitCost:"Unit cost"}} formatY={moneyFmt}/>
              </Chart>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Chart({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-xs uppercase tracking-wider text-muted font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}
function Mini({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-muted tracking-wider">{label}</div>
      <div className="text-base font-semibold">{value}</div>
    </div>
  );
}
