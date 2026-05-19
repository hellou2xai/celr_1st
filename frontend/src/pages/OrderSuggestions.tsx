import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/api/client";
import { money, num } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";
import { RiskBadge } from "@/components/RiskBadge";

interface Row {
  ItemCode: string; Description: string; Supplier: string; Department: string;
  QtyOnHand: number; AvgDailySales: number; DaysOfStock: number;
  SuggestedReorderQty: number; UnitCost: number; ReorderStatus: string;
}
interface Resp {
  summary: { lines: number; suggested_units: number; suggested_value: number };
  rows: Row[];
}

export function OrderSuggestions() {
  const [params] = useSearchParams();
  const q = useQuery<Resp>({
    queryKey: ["order-suggestions", params.toString()],
    queryFn: () => api.get("/api/order-suggestions", Object.fromEntries(params)),
  });
  const cols: ColumnDef<Row, any>[] = [
    { accessorKey: "ItemCode", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "Supplier", header: "Supplier" },
    { accessorKey: "Department", header: "Dept" },
    { accessorKey: "QtyOnHand", header: "OnHand", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "AvgDailySales", header: "Avg/day", cell: c => num(c.getValue<number>(), 2), meta: { align: "right" } },
    { accessorKey: "DaysOfStock", header: "Days cover", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "SuggestedReorderQty", header: "Buy qty", cell: c => <b>{num(c.getValue<number>())}</b>, meta: { align: "right" } },
    { accessorKey: "UnitCost", header: "Unit cost", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "ReorderStatus", header: "Status", cell: c => <RiskBadge risk={c.getValue<string>().includes("OUT") ? "Out of Stock" : c.getValue<string>().includes("NOW") ? "Critical" : "Moderate"}/> },
  ];
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Purchase Order Suggestions</h1>
      <p className="text-sm text-muted mb-4">Velocity-based reorder list. Configure target cover and history window.</p>
      <FilterBar fields={[
        { name: "weeks", label: "Target weeks", type: "number", defaultValue: 12, width: "100px",
          title: "How many weeks of cover the suggested qty should produce" },
        { name: "velocity_months", label: "History (mo)", type: "number", defaultValue: 18, width: "100px",
          title: "Lookback for avg-daily-sales calc" },
        { name: "supplier", label: "Supplier", type: "text", width: "180px" },
        { name: "dept", label: "Dept", type: "text", width: "150px" },
        { name: "min_velocity", label: "Min avg/day", type: "number", width: "100px" },
        { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
      ]}/>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="Lines to buy" value={num(q.data.summary.lines)} variant="info"/>
            <KpiTile label="Suggested units" value={num(q.data.summary.suggested_units)} variant="info"/>
            <KpiTile label="Suggested $" value={money(q.data.summary.suggested_value)} variant="warn"/>
          </div>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}
