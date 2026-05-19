import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { Download } from "lucide-react";
import { api, downloadFile } from "@/api/client";
import { money, num } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { RiskBadge } from "@/components/RiskBadge";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";
import { Button } from "@/components/ui/button";
import type { StockoutRow } from "@/api/types";

interface StockoutsResponse {
  summary: {
    sku_count: number;
    lost_sales_per_week: number;
    open_po_covered: number;
    suppliers_affected: number;
  };
  by_risk: Array<{ Risk: string; Skus: number; LostSalesPerWeek: number }>;
  by_supplier: Array<{ SupplierName: string; Skus: number; LostSalesPerWeek: number }>;
  rows: StockoutRow[];
}

export function Stockouts() {
  const [params] = useSearchParams();
  const q = useQuery<StockoutsResponse>({
    queryKey: ["stockouts", params.toString()],
    queryFn: () => api.get("/api/stockouts", Object.fromEntries(params)),
  });

  const cols: ColumnDef<StockoutRow, any>[] = [
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "Department", header: "Department" },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "AvgMonthlySales", header: "Avg/Mo", cell: c => num(c.getValue<number>(), 2), meta: { align: "right" } },
    { accessorKey: "EstLostSalesPerWeek", header: "Lost $/wk", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "OpenPOQty", header: "Open PO", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "DaysSinceLastSale", header: "Days idle", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Risk", header: "Risk", cell: c => <RiskBadge risk={c.getValue<string>()}/> },
    { accessorKey: "Action", header: "Action", cell: c => <span className="text-xs">{c.getValue<string>()}</span> },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Stockouts — Lost Sales & Replenishment Priority</h1>
      <p className="text-sm text-muted mb-4">Items recently sold but on-hand ≤ 0 — ranked by lost-sales impact.</p>

      <FilterBar
        fields={[
          { name: "velocity_months", label: "Velocity (mo)", type: "number", defaultValue: 6, width: "80px" },
          { name: "supplier", label: "Supplier", type: "text", placeholder: "any", width: "200px" },
          { name: "dept",     label: "Department", type: "text", width: "150px" },
          { name: "min_lost", label: "Min $/wk lost", type: "number", defaultValue: 0, width: "100px" },
          { name: "with_open_po", label: "PO coverage", type: "select", defaultValue: "",
            options: [{label:"Any",value:""},{label:"Has open PO",value:"yes"},{label:"No open PO",value:"no"}] },
          { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
        ]}
        rightSlot={
          <Button
            type="button" variant="outline" size="sm"
            onClick={() => downloadFile(`/api/stockouts/export.xlsx?${params.toString()}`, "stockouts.xlsx")}
          >
            <Download className="h-4 w-4 mr-1"/> Export Excel
          </Button>
        }
      />

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Failed to load.</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiTile label="Stockout SKUs"       value={num(q.data.summary.sku_count)}            variant="bad"/>
            <KpiTile label="Est lost / week"     value={money(q.data.summary.lost_sales_per_week)} variant="bad"/>
            <KpiTile label="Has open PO"         value={num(q.data.summary.open_po_covered)}      variant="good"/>
            <KpiTile label="Suppliers affected"  value={num(q.data.summary.suppliers_affected)}   variant="info"/>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <h2 className="text-lg font-semibold mb-2">By risk</h2>
              <div className="overflow-x-auto rounded border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface/60"><tr>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Risk</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">SKUs</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Lost $/wk</th>
                  </tr></thead>
                  <tbody>
                    {q.data.by_risk.map(r => (
                      <tr key={r.Risk} className="border-t border-border/60">
                        <td className="px-3 py-2"><RiskBadge risk={r.Risk}/></td>
                        <td className="num px-3 py-2">{num(r.Skus)}</td>
                        <td className="num px-3 py-2">{money(r.LostSalesPerWeek)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-2">Top suppliers by lost sales</h2>
              <div className="overflow-x-auto rounded border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface/60"><tr>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Supplier</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">SKUs</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Lost $/wk</th>
                  </tr></thead>
                  <tbody>
                    {q.data.by_supplier.slice(0, 10).map(r => (
                      <tr key={r.SupplierName} className="border-t border-border/60">
                        <td className="px-3 py-2">{r.SupplierName}</td>
                        <td className="num px-3 py-2">{num(r.Skus)}</td>
                        <td className="num px-3 py-2">{money(r.LostSalesPerWeek)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <h2 className="text-lg font-semibold mb-2">Line detail</h2>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}
