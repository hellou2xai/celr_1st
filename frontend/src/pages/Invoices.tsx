import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { FilterBar } from "@/components/FilterBar";
import { KpiTile } from "@/components/KpiTile";

interface InvoiceRow {
  ID: number; Supplier: string; InvoiceNumber: string;
  InvoiceDate: string; GrossTotal: number; NetTotal: number;
  Lines: number; Mapped: number; Unmapped: number; SourceFile: string;
}

export function Invoices() {
  const [params] = useSearchParams();
  const q = useQuery<{ rows: InvoiceRow[]; count: number; note?: string }>({
    queryKey: ["invoices", params.toString()],
    queryFn: () => api.get("/api/invoices", Object.fromEntries(params)),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Invoices</h1>
      <p className="text-sm text-muted mb-4">Vendor invoices parsed from PDFs and matched to RMS items.</p>

      <FilterBar fields={[
        { name: "supplier", label: "Supplier", type: "text", width: "180px" },
        { name: "q", label: "Search", type: "text", placeholder: "invoice # or file" },
        { name: "limit", label: "Limit", type: "number", defaultValue: 200, width: "90px" },
      ]}/>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && !q.data.rows.length && (
        <p className="text-sm text-muted">No invoices loaded yet. Run <code>extract/extract_rip.py</code> and push <code>data/invoice_*.csv</code>.</p>
      )}
      {q.data && !!q.data.rows.length && (
        <>
          <p className="text-xs text-muted mb-2">{num(q.data.count)} invoices</p>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Invoice #</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Supplier</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Date</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Gross</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Net</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Lines</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Mapped</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Unmapped</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Source</th>
              </tr></thead>
              <tbody>
                {q.data.rows.map(r => (
                  <tr key={r.ID} className="border-t border-border/60 hover:bg-surface/40">
                    <td className="px-3 py-1.5">
                      <Link to={`/invoices/${r.ID}`} className="text-accent hover:underline font-mono">{r.InvoiceNumber}</Link>
                    </td>
                    <td className="px-3 py-1.5">{r.Supplier}</td>
                    <td className="px-3 py-1.5">{dt(r.InvoiceDate)}</td>
                    <td className="num px-3 py-1.5">{money(r.GrossTotal)}</td>
                    <td className="num px-3 py-1.5">{money(r.NetTotal)}</td>
                    <td className="num px-3 py-1.5">{num(r.Lines)}</td>
                    <td className="num px-3 py-1.5 text-good">{num(r.Mapped)}</td>
                    <td className="num px-3 py-1.5 text-warn">{num(r.Unmapped)}</td>
                    <td className="px-3 py-1.5 text-xs text-muted">{r.SourceFile}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

interface InvoiceDetailResp {
  header: {
    ID: number; Supplier: string; InvoiceNumber: string; InvoiceDate: string;
    GrossTotal: number; NetTotal: number; Lines: number;
    Mapped: number; Unmapped: number; Warnings?: string; SourceFile: string;
  };
  lines: Array<{
    ID: number; LineNumber: number; SupplierCode: string; RMSLookup: string;
    Description: string; Quantity: number; UnitPrice: number;
    LineTotal: number; MatchStatus: string; Notes?: string;
  }>;
}

const MATCH_COLOR: Record<string, string> = {
  mapped: "text-good", unmapped: "text-warn", manual: "text-info",
};

export function InvoiceDetail() {
  const { id } = useParams();
  const q = useQuery<InvoiceDetailResp>({
    queryKey: ["invoice", id],
    queryFn: () => api.get(`/api/invoices/${id}`),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Invoice Detail</h1>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Invoice not found.</div>}
      {q.data && (
        <>
          <p className="text-sm text-muted mb-4">
            <code className="text-accent">{q.data.header.InvoiceNumber}</code> · {q.data.header.Supplier} · {dt(q.data.header.InvoiceDate)}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiTile label="Gross" value={money(q.data.header.GrossTotal)}/>
            <KpiTile label="Net" value={money(q.data.header.NetTotal)}/>
            <KpiTile label="Lines" value={num(q.data.header.Lines)}/>
            <KpiTile label="Unmapped" value={num(q.data.header.Unmapped)} variant={q.data.header.Unmapped > 0 ? "warn" : "good"}/>
          </div>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">#</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Supplier code</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">RMS lookup</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Qty</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Unit</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Total</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Status</th>
              </tr></thead>
              <tbody>
                {q.data.lines.map(l => (
                  <tr key={l.ID} className="border-t border-border/60">
                    <td className="num px-3 py-1.5">{l.LineNumber}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{l.SupplierCode}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{l.RMSLookup}</td>
                    <td className="px-3 py-1.5">{l.Description}</td>
                    <td className="num px-3 py-1.5">{num(l.Quantity)}</td>
                    <td className="num px-3 py-1.5">{money(l.UnitPrice, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{money(l.LineTotal)}</td>
                    <td className={"px-3 py-1.5 text-xs font-semibold " + (MATCH_COLOR[l.MatchStatus] ?? "text-muted")}>{l.MatchStatus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
