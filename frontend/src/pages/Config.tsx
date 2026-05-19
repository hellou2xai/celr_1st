import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { num, dt } from "@/lib/format";

export function Config() {
  const q = useQuery<any>({
    queryKey: ["config"],
    queryFn: () => api.get("/api/config"),
  });
  if (!q.data) return <div className="text-muted">Loading…</div>;
  const c = q.data;
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Configuration</h1>
      <p className="text-sm text-muted mb-4">Runtime environment, dataset counts, and risk thresholds.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Section title="Environment" entries={c.env}/>
        <Section title="Dataset counts" entries={{
          "Active SKUs": num(c.counts.active_skus),
          "Transactions": num(c.counts.transactions),
          "Line items": num(c.counts.lines),
          "Customers": num(c.counts.customers),
          "POs": num(c.counts.pos),
          "Seeded at": c.counts.seeded_at ? dt(c.counts.seeded_at) : "—",
        }}/>
        <Section title="Risk thresholds & policies" entries={c.policies}/>
      </div>
    </div>
  );
}

function Section({ title, entries }: { title: string; entries: Record<string, any> }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-xs uppercase tracking-wider text-muted font-semibold mb-3">{title}</h3>
      <table className="w-full text-sm">
        <tbody>
          {Object.entries(entries).map(([k, v]) => (
            <tr key={k} className="border-b border-border/60">
              <td className="py-1.5 pr-3 text-muted text-xs">{k}</td>
              <td className="py-1.5 font-mono text-xs break-all">{String(v ?? "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
