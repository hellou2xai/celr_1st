import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api, downloadFile } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { RiskBadge } from "@/components/RiskBadge";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import type { OpenPOsResponse, OpenPOLine } from "@/api/types";

export function OpenPOs() {
  const [params] = useSearchParams();
  const queryKey = ["open-pos", params.toString()];
  const q = useQuery<OpenPOsResponse>({
    queryKey,
    queryFn: () => api.get("/api/open-pos", Object.fromEntries(params)),
  });

  const lineCols: ColumnDef<OpenPOLine, any>[] = [
    { accessorKey: "PONumber", header: "PO#",
      cell: (c) => <a className="text-accent hover:underline" href={`/po/${encodeURIComponent(c.getValue<string>())}`} target="_blank">{c.getValue<string>()}</a> },
    { accessorKey: "PODate", header: "Date", cell: c => dt(c.getValue<string>()) },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "QtyOrdered",  header: "Ordered",  cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "QtyOpen",     header: "Open",     cell: c => <b>{num(c.getValue<number>())}</b>, meta: { align: "right" } },
    { accessorKey: "OnHand",      header: "OnHand",   cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "AvgMonthlySales", header: "Avg/Mo", cell: c => num(c.getValue<number>(), 2), meta: { align: "right" } },
    { accessorKey: "ProjectedMoS", header: "Proj MoS",
      cell: c => { const v = c.getValue<number | null>(); return v == null ? "∞" : num(v, 1); }, meta: { align: "right" } },
    { accessorKey: "UnitCost", header: "Unit Cost", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "LineValue", header: "Line $", cell: c => money(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Risk",   header: "Risk",   cell: c => <RiskBadge risk={c.getValue<string>()}/> },
    { accessorKey: "Action", header: "Action",
      cell: c => {
        const a = c.getValue<string>();
        const cls = a === "CANCEL" ? "text-bad font-semibold" : a === "REDUCE" ? "text-warn font-semibold" : "text-muted";
        return <span className={cls}>{a}</span>;
      } },
    { accessorKey: "Reason", header: "Reason", cell: c => <span className="text-xs text-muted">{c.getValue<string>()}</span> },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Open POs · Cancel / Reduce Review</h1>
      <p className="text-sm text-muted mb-4">PO lines with action suggestions based on velocity and on-hand cover.</p>

      <FilterBar
        fields={[
          { name: "days",   label: "Days", type: "number", defaultValue: 28, width: "80px" },
          { name: "supplier", label: "Supplier", type: "text", placeholder: "any", width: "200px" },
          { name: "product", label: "Product", type: "text", placeholder: "UPC or description" },
          { name: "risk", label: "Risk", type: "select", defaultValue: "",
            options: [
              { label: "Any", value: "" },
              { label: "Critical", value: "Critical" },
              { label: "High", value: "High" },
              { label: "Moderate", value: "Moderate" },
              { label: "Healthy", value: "Healthy" },
              { label: "Excess", value: "Excess" },
              { label: "Dead", value: "Dead" },
            ] },
          { name: "action", label: "Action", type: "select", defaultValue: "",
            options: [
              { label: "Any", value: "" },
              { label: "Needs action", value: "NEEDS_ACTION" },
              { label: "Cancel", value: "CANCEL" },
              { label: "Reduce", value: "REDUCE" },
              { label: "Keep", value: "KEEP" },
            ] },
          { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
        ]}
        rightSlot={
          <Button
            type="button" variant="outline" size="sm"
            onClick={() => downloadFile(`/api/open-pos/export.csv?${params.toString()}`, "open-pos.csv")}
          >
            <Download className="h-4 w-4 mr-1"/> Export CSV
          </Button>
        }
      />

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Failed to load.</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <KpiTile label="Lines" value={num(q.data.summary.line_count)} variant="info"/>
            <KpiTile label="Total Open $" value={money(q.data.summary.total_value)} variant="info"/>
            <KpiTile label="Cancel $" value={money(q.data.summary.cancel_value)} variant="bad"/>
            <KpiTile label="Reduce $" value={money(q.data.summary.reduce_value)} variant="warn"/>
            <KpiTile label="Recoverable $" value={money(q.data.summary.recoverable)} variant="bad"/>
          </div>

          <h2 className="text-lg font-semibold mb-2">By supplier</h2>
          <div className="overflow-x-auto rounded border border-border mb-6">
            <table className="w-full text-sm">
              <thead className="bg-surface/60">
                <tr>
                  <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Supplier</th>
                  <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Lines</th>
                  <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Open $</th>
                  <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Cancel</th>
                  <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Reduce</th>
                  <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Recoverable $</th>
                </tr>
              </thead>
              <tbody>
                {q.data.by_supplier.map(s => (
                  <tr key={s.SupplierName} className="border-t border-border/60 hover:bg-surface/40">
                    <td className="px-3 py-2">{s.SupplierName}</td>
                    <td className="num px-3 py-2">{num(s.Lines)}</td>
                    <td className="num px-3 py-2">{money(s.Value)}</td>
                    <td className="num px-3 py-2">{num(s.CancelLines)}</td>
                    <td className="num px-3 py-2">{num(s.ReduceLines)}</td>
                    <td className="num px-3 py-2">{money(s.RecoverableValue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="text-lg font-semibold mb-2">Line detail ({num(q.data.lines.length)})</h2>
          <DataTable columns={lineCols} data={q.data.lines} dense/>
        </>
      )}
    </div>
  );
}
