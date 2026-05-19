import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { money, num, pct } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { RiskBadge } from "@/components/RiskBadge";
import type { DashboardSummary } from "@/api/types";

const RISK_ORDER = ["Critical", "High", "Moderate", "Healthy", "Excess", "Dead"];

export function Dashboard() {
  const q = useQuery<DashboardSummary>({
    queryKey: ["dashboard"],
    queryFn: () => api.get("/api/dashboard"),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold">Procurement Dashboard</h1>
      <p className="text-sm text-muted mb-6">Last 28 days of open POs · 6-month velocity window</p>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Failed to load dashboard.</div>}
      {q.data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <KpiTile
              label="Open POs"
              value={num(q.data.open_po_count)}
              sub={`${num(q.data.open_line_count)} line items · click to review`}
              variant="info"
              to="/open-pos"
            />
            <KpiTile
              label="Open PO Value"
              value={money(q.data.open_po_value)}
              sub="28-day window · click to review"
              variant="info"
              to="/open-pos"
            />
            <KpiTile
              label="Suggested Cancels / Reduces"
              value={money(q.data.cancel_value)}
              sub={`${num(q.data.cancel_lines)} lines recoverable · click to review`}
              variant="bad"
              to="/open-pos?action=NEEDS_ACTION"
            />
            <KpiTile
              label="RTV Candidates (Net)"
              value={money(q.data.rtv_value)}
              sub={`${money(q.data.rtv_in_window_value)} in return window`}
              variant="warn"
              to="/rtv?in_window=1"
            />
            <KpiTile
              label="Recent Stockouts"
              value={num(q.data.recent_stockouts)}
              sub="sold last month, now OnHand ≤ 0"
              variant="bad"
              to="/stockouts"
            />
          </div>

          <section className="mt-8">
            <h2 className="text-lg font-semibold mb-1">Open PO risk breakdown</h2>
            <p className="text-xs text-muted mb-3">Click any row to see the PO lines at that risk level.</p>
            <div className="overflow-x-auto rounded border border-border">
              <table className="w-full text-sm">
                <thead className="bg-surface/60">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Risk</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Lines</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Value</th>
                    <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">% of Value</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {RISK_ORDER.map(risk => {
                    const r = q.data.risk_rollup[risk];
                    if (!r) return null;
                    const total = q.data.open_po_value || 1;
                    return (
                      <tr key={risk} className="border-t border-border/60 hover:bg-surface/40">
                        <td className="px-3 py-2"><RiskBadge risk={risk}/></td>
                        <td className="num px-3 py-2">{num(r.lines)}</td>
                        <td className="num px-3 py-2">{money(r.value)}</td>
                        <td className="num px-3 py-2">{pct((100 * r.value) / total, 1)}</td>
                        <td className="px-3 py-2">
                          <Link to={`/open-pos?risk=${encodeURIComponent(risk)}`} className="text-accent hover:underline text-xs">
                            Review →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {!!q.data.top_cancel_suppliers?.length && (
            <section className="mt-8">
              <h2 className="text-lg font-semibold mb-3">Top suppliers with cancel/reduce opportunity</h2>
              <div className="overflow-x-auto rounded border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface/60">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted">Supplier</th>
                      <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Cancel Lines</th>
                      <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Reduce Lines</th>
                      <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted">Recoverable $</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.top_cancel_suppliers.map(g => (
                      <tr key={g.SupplierName} className="border-t border-border/60 hover:bg-surface/40">
                        <td className="px-3 py-2">{g.SupplierName}</td>
                        <td className="num px-3 py-2">{num(g.CancelLines)}</td>
                        <td className="num px-3 py-2">{num(g.ReduceLines)}</td>
                        <td className="num px-3 py-2">{money(g.RecoverableValue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <p className="text-xs text-muted mt-6">
            <Link to="/config" className="text-accent hover:underline">View thresholds and supplier policies →</Link>
          </p>
        </>
      )}
    </div>
  );
}
