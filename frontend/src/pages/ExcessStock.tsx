import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/api/client";
import { money, num } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { RiskBadge } from "@/components/RiskBadge";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";

interface Row {
  UPC: string; Description: string; Department: string; Category: string;
  SupplierName: string; OnHand: number; Cost: number; InventoryValue: number;
  AvgMonthlySales: number; MoS: number | null; DaysSinceLastSale: number; Risk: string;
}
interface Resp {
  summary: { sku_count: number; total_capital: number; dead_capital: number; suppliers_affected: number };
  by_supplier: Array<{ SupplierName: string; Skus: number; Value: number }>;
  by_department: Array<{ Department: string; Skus: number; Value: number }>;
  rows: Row[];
}

export function ExcessStock() {
  const [params] = useSearchParams();
  const q = useQuery<Resp>({
    queryKey: ["excess-stock", params.toString()],
    queryFn: () => api.get("/api/excess-stock", Object.fromEntries(params)),
  });

  const cols: ColumnDef<Row, any>[] = [
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "Department", header: "Dept" },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "OnHand", header: "OnHand", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "InventoryValue", header: "Tied up $", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "AvgMonthlySales", header: "Avg/Mo", cell: c => num(c.getValue<number>(), 2), meta: { align: "right" } },
    { accessorKey: "MoS", header: "MoS",
      cell: c => { const v = c.getValue<number | null>(); return v == null ? "∞" : num(v, 1); }, meta: { align: "right" } },
    { accessorKey: "DaysSinceLastSale", header: "Idle days", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Risk", header: "Risk", cell: c => <RiskBadge risk={c.getValue<string>()}/> },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Excess Stock</h1>
      <p className="text-sm text-muted mb-4">Capital tied up in slow or dead inventory.</p>
      <FilterBar
        fields={[
          { name: "velocity_months", label: "Velocity (mo)", type: "number", defaultValue: 6, width: "80px" },
          { name: "min_mos", label: "Min MoS", type: "number", defaultValue: 6, width: "80px" },
          { name: "min_oh_value", label: "Min OH $", type: "number", defaultValue: 100, width: "90px" },
          { name: "supplier", label: "Supplier", type: "text", width: "180px" },
          { name: "dept", label: "Dept", type: "text", width: "150px" },
          { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
        ]}
      />
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiTile label="SKUs at risk" value={num(q.data.summary.sku_count)} variant="warn"/>
            <KpiTile label="Capital tied up" value={money(q.data.summary.total_capital)} variant="bad"/>
            <KpiTile label="Of which dead" value={money(q.data.summary.dead_capital)} variant="bad"/>
            <KpiTile label="Suppliers affected" value={num(q.data.summary.suppliers_affected)} variant="info"/>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <RollupTable title="Top suppliers by excess capital" rows={q.data.by_supplier.map(r => ({ name: r.SupplierName, skus: r.Skus, value: r.Value }))}/>
            <RollupTable title="By department" rows={q.data.by_department.map(r => ({ name: r.Department, skus: r.Skus, value: r.Value }))}/>
          </div>
          <h2 className="text-lg font-semibold mb-2">Item detail</h2>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}

function RollupTable({ title, rows }: { title: string; rows: Array<{ name: string; skus: number; value: number }> }) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-sm">
          <thead className="bg-surface/60"><tr>
            <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Name</th>
            <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">SKUs</th>
            <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Value</th>
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.name} className="border-t border-border/60">
                <td className="px-3 py-2">{r.name}</td>
                <td className="num px-3 py-2">{num(r.skus)}</td>
                <td className="num px-3 py-2">{money(r.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
