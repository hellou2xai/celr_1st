import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, downloadFile } from "@/api/client";
import { Button } from "@/components/ui/button";
import { money, num, pct, dt } from "@/lib/format";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LineChartC, BarChartC, moneyFmt } from "@/components/Chart";
import { DrillIcon } from "@/components/DrillDown";

export function SalesAnalysis() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Sales Analytics</h1>
      <p className="text-sm text-muted mb-4">Multi-view sales explorer.</p>
      <Tabs defaultValue="top">
        <TabsList>
          <TabsTrigger value="top">Top sellers</TabsTrigger>
          <TabsTrigger value="yoy">Weekly YoY</TabsTrigger>
          <TabsTrigger value="movers">Movers</TabsTrigger>
          <TabsTrigger value="txns">Transactions</TabsTrigger>
        </TabsList>
        <TabsContent value="top"><TopSellers/></TabsContent>
        <TabsContent value="yoy"><WeeklyYoY/></TabsContent>
        <TabsContent value="movers"><Movers/></TabsContent>
        <TabsContent value="txns"><Transactions/></TabsContent>
      </Tabs>
    </div>
  );
}

function TopSellers() {
  const q = useQuery<{ rows: any[]; by_department: any[] }>({
    queryKey: ["sales-top"],
    queryFn: () => api.get("/api/sales/top-sellers", { months: 6, top: 25 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="md:col-span-2 rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-surface/60"><tr>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">Dept</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">Units</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">Revenue</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">GP</th>
          </tr></thead>
          <tbody>
            {q.data.rows.map((r, i) => (
              <tr key={i} className="border-t border-border/60">
                <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                <td className="px-3 py-1.5">{r.Description}</td>
                <td className="px-3 py-1.5">{r.Department}</td>
                <td className="num px-3 py-1.5">{num(r.Units)}</td>
                <td className="num px-3 py-1.5">{money(r.Revenue)}</td>
                <td className="num px-3 py-1.5">{money(r.GrossProfit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-xs uppercase tracking-wider text-muted font-semibold mb-2">Revenue by department</h3>
        <BarChartC data={q.data.by_department.slice(0, 12)} xKey="Department"
                    yKeys={["Revenue"]} formatY={moneyFmt} horizontal/>
      </div>
    </div>
  );
}

function WeeklyYoY() {
  const q = useQuery<{ rows: Array<{ Week: string; Year: number; NetRevenue: number; Transactions: number }>; weeks: number }>({
    queryKey: ["sales-yoy"],
    queryFn: () => api.get("/api/sales/weekly-yoy", { weeks: 26 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  const cur = q.data.rows.slice(-26);
  const total = cur.reduce((s, r) => s + Number(r.NetRevenue || 0), 0);
  const prev = q.data.rows.slice(-78, -52);
  const prevTotal = prev.reduce((s, r) => s + Number(r.NetRevenue || 0), 0);
  const yoyPct = prevTotal ? ((total - prevTotal) / prevTotal) * 100 : null;
  return (
    <>
      <div className="flex justify-end mb-2">
        <Button type="button" variant="outline" size="sm"
          onClick={() => downloadFile("/api/sales/weekly-yoy/export.xlsx?weeks=26", "weekly-yoy.xlsx")}>
          <Download className="h-4 w-4 mr-1"/> Export Excel
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <Mini title={`${cur.length}-week total`} value={money(total)}/>
        <Mini title="Same window last year" value={money(prevTotal)}/>
        <Mini title="YoY %" value={pct(yoyPct ?? 0, 1)}/>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-xs uppercase tracking-wider text-muted font-semibold mb-2">Net revenue by week</h3>
        <LineChartC data={q.data.rows} xKey="Week" yKeys={["NetRevenue"]} formatY={moneyFmt} height={300}/>
      </div>
    </>
  );
}

function Movers() {
  const q = useQuery<{ rows: any[]; weeks: number }>({
    queryKey: ["sales-movers"],
    queryFn: () => api.get("/api/sales/movers", { weeks: 12, top: 50 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  const counts: Record<string, number> = {};
  for (const r of q.data.rows) counts[r.Category] = (counts[r.Category] || 0) + 1;
  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        {["Growing","Stable","Slowing","Dying","New"].map(c => (
          <Mini key={c} title={c} value={num(counts[c] || 0)}/>
        ))}
      </div>
      <div className="rounded border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface/60"><tr>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">Cur units</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">Prev units</th>
            <th className="px-3 py-2 text-right text-xs uppercase text-muted">% chg</th>
            <th className="px-3 py-2 text-left text-xs uppercase text-muted">Category</th>
          </tr></thead>
          <tbody>
            {q.data.rows.map((r, i) => (
              <tr key={i} className="border-t border-border/60">
                <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                <td className="px-3 py-1.5">{r.Description}</td>
                <td className="num px-3 py-1.5">{num(r.UnitsCur)}</td>
                <td className="num px-3 py-1.5">{num(r.UnitsPrev)}</td>
                <td className="num px-3 py-1.5">{r.PctChange == null ? "—" : pct(r.PctChange, 1)}</td>
                <td className="px-3 py-1.5">{r.Category}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Transactions() {
  const q = useQuery<{ rows: any[] }>({
    queryKey: ["sales-txns"],
    queryFn: () => api.get("/api/sales/transactions", { days: 7, limit: 200 }),
  });
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!q.data) return null;
  return (
    <>
    <div className="flex justify-end mb-2">
      <Button type="button" variant="outline" size="sm"
        onClick={() => downloadFile("/api/sales/transactions/export.xlsx?days=30&limit=10000", "transactions.xlsx")}>
        <Download className="h-4 w-4 mr-1"/> Export Excel
      </Button>
    </div>
    <div className="rounded border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-surface/60"><tr>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Txn#</th>
          <th className="px-3 py-2 text-left text-xs uppercase text-muted">Time</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Lines</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Units</th>
          <th className="px-3 py-2 text-right text-xs uppercase text-muted">Total</th>
        </tr></thead>
        <tbody>
          {q.data.rows.map((r) => (
            <tr key={r.TransactionNumber} className="border-t border-border/60">
              <td className="px-3 py-1.5 font-mono">TXN#{r.TransactionNumber}</td>
              <td className="px-3 py-1.5">{dt(r.Time)}</td>
              <td className="num px-3 py-1.5">{num(r.Lines)}</td>
              <td className="num px-3 py-1.5">{num(r.Units)}</td>
              <td className="num px-3 py-1.5">{money(r.Total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </>
  );
}

function Mini({ title, value }: { title: string; value: any }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-[10px] uppercase text-muted tracking-wider">{title}</div>
      <div className="text-xl font-bold mt-1">{value}</div>
    </div>
  );
}
