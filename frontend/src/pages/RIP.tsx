import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "@/api/client";
import { money, num } from "@/lib/format";

function RIPEmpty({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">{title}</h1>
      <p className="text-sm text-muted mb-4">{sub}</p>
      <div className="rounded-lg border border-warn/40 bg-warn/5 p-6">
        <p className="text-sm">RIP (Rebate Incentive Program) data is not part of the Render demo seed.</p>
        <p className="text-xs text-muted mt-2">
          The original Flask app ingests monthly distributor files (ABG) into a local SQLite store
          (<code>procurement_app/rip.db</code>) via <code>rip_ingest.py</code>. Wiring that pipeline
          into the Render Postgres is on the roadmap — see <code>CURRENT_APP_AUDIT.md</code>.
        </p>
        <ul className="mt-3 list-disc list-inside text-xs text-muted">
          <li>Monthly program tiers + rebate amounts</li>
          <li>Combo offers across SKUs</li>
          <li>UPC ↔ POS Item mapping</li>
          <li>Match history (EXPECTED / RECEIVED / OVERDUE / DISPUTED / DECLINED)</li>
        </ul>
      </div>
    </div>
  );
}

export function RIPPrograms() {
  return <RIPEmpty title="RIP Programs" sub="Monthly rebate / incentive programs from distributors."/>;
}
export function RIPOptimize() {
  return <RIPEmpty title="RIP Optimizer" sub="Combo + tier optimizer to maximize monthly rebates."/>;
}
export function RIPOrderSuggestions() {
  return <RIPEmpty title="RIP Order Suggestions" sub="Reorder list filtered to items with an active RIP program."/>;
}

export function RIPItemDetail() {
  const { id } = useParams();
  const q = useQuery<{ item: any; programs: any[]; claims: any[]; note?: string }>({
    queryKey: ["rip-item", id],
    queryFn: () => api.get(`/api/rip-item/${id}`),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">RIP Item Detail</h1>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && (
        <>
          <div className="text-sm text-muted mb-4">
            <code className="text-accent">{q.data.item?.item_lookup_code}</code> · {q.data.item?.description}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Mini label="OnHand" value={num(q.data.item?.quantity)}/>
            <Mini label="Cost" value={money(q.data.item?.cost, { digits: 2 })}/>
            <Mini label="Price" value={money(q.data.item?.price, { digits: 2 })}/>
            <Mini label="Supplier" value={q.data.item?.supplier || "—"}/>
          </div>
          <div className="rounded-lg border border-warn/40 bg-warn/5 p-6">
            <p className="text-sm">{q.data.note}</p>
          </div>
        </>
      )}
    </div>
  );
}

function Mini({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-[11px] uppercase text-muted tracking-wider">{label}</div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  );
}
