import { useQuery } from "@tanstack/react-query";
import { useSearchParams, Link } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";

interface PORow {
  PONumber: string; SupplierName: string; Status: number;
  DateCreated: string; DatePlaced: string; RequiredDate: string;
  UnitsOrdered: number; UnitsReceived: number; Value: number; Lines: number;
}

const STATUS = ["Created","Processed","Placed","In transit","Received","Closed"];

export function POsBrowse() {
  const [params] = useSearchParams();
  const q = useQuery<{ count: number; rows: PORow[] }>({
    queryKey: ["pos", params.toString()],
    queryFn: () => api.get("/api/pos", Object.fromEntries(params)),
  });
  const cols: ColumnDef<PORow, any>[] = [
    { accessorKey: "PONumber", header: "PO#",
      cell: c => <Link to={`/po/${encodeURIComponent(c.getValue<string>())}`} className="text-accent hover:underline">{c.getValue<string>()}</Link> },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "Status", header: "Status",
      cell: c => STATUS[c.getValue<number>()] ?? c.getValue<number>() },
    { accessorKey: "DateCreated", header: "Created", cell: c => dt(c.getValue<string>()) },
    { accessorKey: "RequiredDate", header: "Required", cell: c => dt(c.getValue<string>()) },
    { accessorKey: "Lines", header: "Lines", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "UnitsOrdered", header: "Ordered", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "UnitsReceived", header: "Received", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Value", header: "Value", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
  ];
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Purchase Orders</h1>
      <p className="text-sm text-muted mb-4">All POs in the lookback window.</p>
      <FilterBar fields={[
        { name: "days", label: "Days back", type: "number", defaultValue: 365, width: "90px" },
        { name: "supplier", label: "Supplier", type: "text", width: "180px" },
        { name: "status", label: "Status", type: "select", defaultValue: "",
          options: [{label:"Any",value:""},...STATUS.map((s,i)=>({label:s,value:String(i)}))] },
        { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
      ]}/>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && (
        <>
          <p className="text-xs text-muted mb-2">{num(q.data.count)} POs</p>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}
