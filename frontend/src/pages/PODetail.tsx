import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { DataTable } from "@/components/DataTable";
import { DrillIcon } from "@/components/DrillDown";

interface Line {
  UPC: string; Description: string; Department: string;
  QtyOrdered: number; QtyReceived: number; QtyOpen: number;
  UnitCost: number; LineTotal: number; LastReceivedDate: string;
}
interface Header {
  PONumber: string; Status: number; DateCreated: string;
  DatePlaced: string; RequiredDate: string; SupplierName: string;
}

const STATUS = ["Created","Processed","Placed","In transit","Received","Closed"];

export function PODetail() {
  const { po } = useParams();
  const q = useQuery<{ header: Header; lines: Line[]; totals: { line_count: number; units_ordered: number; units_received: number; value: number } }>({
    queryKey: ["po", po],
    queryFn: () => api.get(`/api/po/${encodeURIComponent(po!)}`),
  });

  const cols: ColumnDef<Line, any>[] = [
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "Department", header: "Dept" },
    { accessorKey: "QtyOrdered", header: "Ordered", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "QtyReceived", header: "Received", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "QtyOpen", header: "Open", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "UnitCost", header: "Unit Cost", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "LineTotal", header: "Line Total", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "LastReceivedDate", header: "Last recv", cell: c => dt(c.getValue<string>()) },
  ];

  return (
    <div>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">PO not found.</div>}
      {q.data && (
        <>
          <h1 className="text-2xl font-bold mb-1">PO <code className="text-accent">{q.data.header.PONumber}</code></h1>
          <p className="text-sm text-muted mb-4">{q.data.header.SupplierName} · {STATUS[q.data.header.Status]}</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiTile label="Line items" value={num(q.data.totals.line_count)}/>
            <KpiTile label="Units ordered" value={num(q.data.totals.units_ordered)}/>
            <KpiTile label="Units received" value={num(q.data.totals.units_received)}/>
            <KpiTile label="Value" value={money(q.data.totals.value)}/>
          </div>

          <h2 className="text-lg font-semibold mb-2">Header details</h2>
          <div className="overflow-x-auto rounded border border-border mb-6">
            <table className="w-full text-sm">
              <tbody>
                {[
                  ["PO Number", q.data.header.PONumber],
                  ["Supplier", q.data.header.SupplierName],
                  ["Status", STATUS[q.data.header.Status]],
                  ["Date created", dt(q.data.header.DateCreated)],
                  ["Date placed",  dt(q.data.header.DatePlaced)],
                  ["Required by", dt(q.data.header.RequiredDate)],
                ].map(([k, v]) => (
                  <tr key={k as string} className="border-b border-border/60">
                    <td className="px-3 py-2 text-muted w-40">{k}</td>
                    <td className="px-3 py-2">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="text-lg font-semibold mb-2">Line items</h2>
          <DataTable columns={cols} data={q.data.lines} dense/>
        </>
      )}
    </div>
  );
}
