import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { Download } from "lucide-react";
import { api, downloadFile } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";
import { Button } from "@/components/ui/button";
import type { RTVRow } from "@/api/types";

interface RTVResponse {
  summary: { line_count: number; total_value: number; in_window_value: number };
  rows: RTVRow[];
}

export function RTV() {
  const [params] = useSearchParams();
  const q = useQuery<RTVResponse>({
    queryKey: ["rtv", params.toString()],
    queryFn: () => api.get("/api/rtv", Object.fromEntries(params)),
  });

  const cols: ColumnDef<RTVRow, any>[] = [
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "OnHand", header: "OnHand", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Cost", header: "Unit Cost", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "InventoryValue", header: "Tied up $", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "LastReceived", header: "Last Received", cell: c => dt(c.getValue<string>()) },
    { accessorKey: "DaysInStore", header: "Days held", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "InReturnWindow", header: "In window?",
      cell: c => c.getValue<boolean>()
        ? <span className="text-good text-xs">✓ in window</span>
        : <span className="text-muted text-xs">expired</span> },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Return to Vendor</h1>
      <p className="text-sm text-muted mb-4">Items eligible for RTV — capital recoverable by returning unsold stock to suppliers.</p>

      <FilterBar
        fields={[
          { name: "in_window", label: "In window only", type: "select", defaultValue: "",
            options: [{ label: "Any", value: "" }, { label: "Yes", value: "1" }] },
          { name: "supplier", label: "Supplier", type: "text", placeholder: "any", width: "200px" },
          { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
        ]}
        rightSlot={
          <Button
            type="button" variant="outline" size="sm"
            onClick={() => downloadFile(`/api/rtv/export.csv?${params.toString()}`, "rtv.csv")}
          >
            <Download className="h-4 w-4 mr-1"/> Export CSV
          </Button>
        }
      />

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Failed to load.</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="RTV lines"        value={num(q.data.summary.line_count)} variant="info"/>
            <KpiTile label="Total tied up"    value={money(q.data.summary.total_value)} variant="warn"/>
            <KpiTile label="In return window" value={money(q.data.summary.in_window_value)} variant="bad"/>
          </div>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}
