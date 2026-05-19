import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KpiTile } from "@/components/KpiTile";
import { money, num } from "@/lib/format";
import { Trash2 } from "lucide-react";

interface BasketItem { upc: string; qty: number; }
interface OptLine {
  UPC: string; Description: string; Supplier: string;
  Qty: number; UnitCost: number; AvgPaid: number;
  LineTotal: number; EstSavings: number;
}
interface OptResp {
  basket: OptLine[];
  totals: { line_count: number; total: number; savings: number };
}

export function Optimizer() {
  const stored = JSON.parse(localStorage.getItem("opt_basket") || "[]") as BasketItem[];
  const [basket, setBasket] = useState<BasketItem[]>(stored);
  const [upc, setUpc] = useState(""); const [qty, setQty] = useState(1);
  const [result, setResult] = useState<OptResp | null>(null);

  const save = (b: BasketItem[]) => {
    setBasket(b);
    localStorage.setItem("opt_basket", JSON.stringify(b));
  };

  const add = () => {
    if (!upc.trim()) return;
    save([...basket, { upc: upc.trim(), qty: qty || 1 }]);
    setUpc(""); setQty(1);
  };
  const remove = (i: number) => save(basket.filter((_, idx) => idx !== i));

  const optimize = async () => {
    const r = await api.post<OptResp>("/api/optimizer", { basket });
    setResult(r);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Buy Optimizer</h1>
      <p className="text-sm text-muted mb-4">Add SKUs to a basket and we'll compare current cost to your historical average paid — surfacing items where current pricing is below average.</p>

      <div className="rounded border border-border p-4 mb-4">
        <div className="flex gap-2 items-end">
          <label className="text-xs text-muted">UPC <Input value={upc} onChange={e=>setUpc(e.target.value)} className="mt-1 w-48 font-mono"/></label>
          <label className="text-xs text-muted">Qty <Input type="number" value={qty} onChange={e=>setQty(parseInt(e.target.value)||1)} className="mt-1 w-24"/></label>
          <Button onClick={add}>Add to basket</Button>
        </div>

        {!!basket.length && (
          <div className="mt-4">
            <h3 className="text-xs uppercase tracking-wider text-muted mb-2">Basket</h3>
            <table className="w-full text-sm">
              <tbody>
                {basket.map((b, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="py-1 font-mono">{b.upc}</td>
                    <td className="py-1 num">{num(b.qty)}</td>
                    <td className="py-1 text-right">
                      <button onClick={() => remove(i)} className="text-muted hover:text-bad"><Trash2 className="h-4 w-4"/></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button onClick={optimize} className="mt-4">Run optimizer</Button>
          </div>
        )}
      </div>

      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="Line items" value={num(result.totals.line_count)}/>
            <KpiTile label="Basket total" value={money(result.totals.total)} variant="info"/>
            <KpiTile label="Est savings vs avg paid" value={money(result.totals.savings)} variant="good"/>
          </div>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Supplier</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Qty</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Current</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Avg paid</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Total</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Est savings</th>
              </tr></thead>
              <tbody>
                {result.basket.map((l, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono">{l.UPC}</td>
                    <td className="px-3 py-1.5">{l.Description}</td>
                    <td className="px-3 py-1.5">{l.Supplier}</td>
                    <td className="num px-3 py-1.5">{num(l.Qty)}</td>
                    <td className="num px-3 py-1.5">{money(l.UnitCost, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{money(l.AvgPaid, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{money(l.LineTotal)}</td>
                    <td className="num px-3 py-1.5 text-good">{money(l.EstSavings)}</td>
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
