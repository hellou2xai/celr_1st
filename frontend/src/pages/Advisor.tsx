import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Brain, Sparkles } from "lucide-react";
import { money, num } from "@/lib/format";

export function Advisor() {
  const briefing = useQuery<any>({
    queryKey: ["advisor-briefing"],
    queryFn: () => api.get("/api/advisor/briefing"),
  });
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<{ answer: string; data?: any } | null>(null);
  const ask = async () => {
    if (!q.trim()) return;
    const r = await api.post<{ answer: string; data?: any }>("/api/advisor/ask", { question: q });
    setAnswer(r);
  };
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">AI Advisor</h1>
      <p className="text-sm text-muted mb-4">Ask procurement questions. Demo responses are rule-based; wire an LLM key (OpenAI/Anthropic) to get freeform answers.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3"><Sparkles className="h-4 w-4 text-accent"/><h2 className="font-semibold">Daily briefing</h2></div>
          {briefing.data?.kpis && (
            <ul className="text-sm space-y-1">
              <li>Net revenue last 30d: <b>{money(briefing.data.kpis.NetRev30d)}</b></li>
              <li>Gross profit 30d: <b>{money(briefing.data.kpis.GrossProfit30d)}</b></li>
              <li>Inventory at cost: <b>{money(briefing.data.kpis.InventoryAtCost)}</b></li>
              <li>Open POs: <b>{num(briefing.data.kpis.OpenPOs)}</b></li>
              <li>Stockouts: <b>{num(briefing.data.kpis.Stockouts)}</b></li>
            </ul>
          )}
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3"><Brain className="h-4 w-4 text-accent"/><h2 className="font-semibold">Ask</h2></div>
          <div className="flex gap-2">
            <Input value={q} onChange={e=>setQ(e.target.value)} placeholder="What should I reorder this week?"
                   onKeyDown={e => e.key === "Enter" && ask()}/>
            <Button onClick={ask}>Ask</Button>
          </div>
          {answer && (
            <div className="mt-4">
              <p className="text-sm">{answer.answer}</p>
              {Array.isArray(answer.data) && answer.data.length > 0 && (
                <div className="mt-3 rounded border border-border overflow-x-auto max-h-64">
                  <table className="w-full text-xs">
                    <thead className="bg-surface/60">
                      <tr>{Object.keys(answer.data[0]).slice(0, 6).map(k => <th key={k} className="px-2 py-1 text-left text-muted">{k}</th>)}</tr>
                    </thead>
                    <tbody>
                      {answer.data.slice(0, 10).map((row: any, i: number) => (
                        <tr key={i} className="border-t border-border/60">
                          {Object.keys(answer.data[0]).slice(0, 6).map(k => (
                            <td key={k} className="px-2 py-1">{String(row[k] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
