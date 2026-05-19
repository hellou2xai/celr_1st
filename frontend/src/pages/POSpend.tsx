import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { money, num } from "@/lib/format";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LineChartC, BarChartC, DonutChartC, moneyFmt } from "@/components/Chart";
import { useState } from "react";
import { DrillIcon } from "@/components/DrillDown";

const STATUS_LABEL = ["Created","Processed","Placed","In transit","Received","Closed"];

export function POSpend() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">PO Spend Analysis</h1>
      <p className="text-sm text-muted mb-4">Where the buying budget goes.</p>
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="items">Items</TabsTrigger>
          <TabsTrigger value="variance">Variance</TabsTrigger>
        </TabsList>
        <TabsContent value="overview"><Overview/></TabsContent>
        <TabsContent value="categories"><Categories/></TabsContent>
        <TabsContent value="items"><Items/></TabsContent>
        <TabsContent value="variance"><Variance/></TabsContent>
      </Tabs>
    </div>
  );
}

function Overview() {
  const q = useQuery<{ by_month: any[]; by_status: any[]; top_suppliers: any[] }>({
    queryKey: ["po-spend-overview"],
    queryFn: () => api.get("/api/po-spend/overview", { months: 12 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 rounded-lg border border-border bg-card p-4">
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Spend by month</h3>
        <LineChartC data={q.data.by_month} xKey="Bucket" yKeys={["Spend"]} formatY={moneyFmt}/>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Status mix</h3>
        <DonutChartC data={q.data.by_status.map(s => ({ ...s, Status: STATUS_LABEL[Number(s.Status)] ?? s.Status }))} nameKey="Status" valueKey="Value"/>
      </div>
      <div className="lg:col-span-3 rounded-lg border border-border bg-card p-4">
        <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Top 10 suppliers</h3>
        <BarChartC data={q.data.top_suppliers} xKey="SupplierName" yKeys={["Spend"]} formatY={moneyFmt} horizontal height={300}/>
      </div>
    </div>
  );
}

function Categories() {
  const q = useQuery<{ rows: any[] }>({
    queryKey: ["po-spend-cat"],
    queryFn: () => api.get("/api/po-spend/categories", { months: 12 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  return (
    <div className="rounded border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-surface/60"><tr>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Department</th>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Category</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">SKUs</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Spend</th>
        </tr></thead>
        <tbody>
          {q.data.rows.map((r, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="px-3 py-1.5">{r.Department}</td>
              <td className="px-3 py-1.5">{r.Category}</td>
              <td className="num px-3 py-1.5">{num(r.Skus)}</td>
              <td className="num px-3 py-1.5">{money(r.Spend)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Items() {
  const q = useQuery<{ rows: any[] }>({
    queryKey: ["po-spend-items"],
    queryFn: () => api.get("/api/po-spend/items", { months: 12, top: 50 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  return (
    <div className="rounded border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-surface/60"><tr>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Supplier</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Units</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Spend</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Avg cost</th>
        </tr></thead>
        <tbody>
          {q.data.rows.map((r, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
              <td className="px-3 py-1.5">{r.Description}</td>
              <td className="px-3 py-1.5">{r.SupplierName}</td>
              <td className="num px-3 py-1.5">{num(r.Units)}</td>
              <td className="num px-3 py-1.5">{money(r.Spend)}</td>
              <td className="num px-3 py-1.5">{money(r.AvgCost, { digits: 2 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Variance() {
  const [upc, setUpc] = useState("");
  const q = useQuery<{ rows: any[]; upc: string }>({
    queryKey: ["po-spend-drift", upc],
    queryFn: () => api.get("/api/po-spend/item-price-drift", { upc }),
    enabled: !!upc,
  });
  return (
    <div>
      <input className="border border-border bg-surface text-sm h-9 px-3 rounded mr-2 font-mono w-56"
             placeholder="UPC to chart" value={upc} onChange={e => setUpc(e.target.value)}/>
      {q.data?.rows.length ? (
        <div className="rounded-lg border border-border bg-card p-4 mt-4">
          <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Price drift for {q.data.upc}</h3>
          <LineChartC data={q.data.rows} xKey="Date" yKeys={["UnitCost"]} formatY={moneyFmt}/>
        </div>
      ) : upc ? (
        <p className="text-sm text-muted mt-4">No PO history for {upc}.</p>
      ) : (
        <p className="text-sm text-muted mt-4">Enter a UPC above to see its price-paid history.</p>
      )}
    </div>
  );
}
