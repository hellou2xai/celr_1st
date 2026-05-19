import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function Invoices() {
  const q = useQuery<{ rows: any[]; note?: string }>({
    queryKey: ["invoices"],
    queryFn: () => api.get("/api/invoices"),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Invoices</h1>
      <p className="text-sm text-muted mb-4">Vendor invoices parsed from PDFs.</p>
      {q.data?.note && (
        <div className="rounded-lg border border-warn/40 bg-warn/5 p-6 mb-6">
          <p className="text-sm">{q.data.note}</p>
          <p className="text-xs text-muted mt-2">
            The original Flask app uses <code>invoices/allied.py</code> and <code>invoices/fedway.py</code> to extract line items from supplier PDFs.
            That pipeline ships in <code>procurement_app/</code> but is not part of the Render demo seed.
            Wiring it here is a follow-up task.
          </p>
        </div>
      )}
      {!!q.data?.rows.length && (
        <div className="rounded border border-border">
          {q.data.rows.map((r, i) => <div key={i} className="px-3 py-2">{JSON.stringify(r)}</div>)}
        </div>
      )}
    </div>
  );
}

export function InvoiceDetail() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Invoice Detail</h1>
      <p className="text-sm text-muted">Invoice not available in the demo dataset.</p>
    </div>
  );
}
