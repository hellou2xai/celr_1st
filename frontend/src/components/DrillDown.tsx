import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, X, Loader2 } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { RiskBadge } from "./RiskBadge";
import { cn } from "@/lib/utils";
import type { ItemDrillResponse, TxnDrillResponse } from "@/api/types";

/**
 * Stack-based drill-down modal. Ported from drilldown.js.
 *   - Right-click any element with [data-upc] opens an item view.
 *   - Inside the modal, clicking TXN# / ITL# refs pushes a transaction view.
 *   - Inside a transaction view, clicking a line UPC pushes another item view.
 *   - Backspace pops, Esc closes, "Reload" refreshes the current top entry.
 */

type StackEntry =
  | { kind: "item"; id: string; months?: number }
  | { kind: "txn";  id: string };

type Ctx = {
  openItem: (id: string) => void;
  openTxn:  (ref: string) => void;
  close: () => void;
};

const DrillCtx = React.createContext<Ctx | null>(null);

export const useDrill = () => {
  const c = React.useContext(DrillCtx);
  if (!c) throw new Error("DrillDownProvider missing");
  return c;
};

export function DrillDownProvider({ children }: { children: React.ReactNode }) {
  const [stack, setStack] = React.useState<StackEntry[]>([]);
  const [months, setMonths] = React.useState(24);
  const open = stack.length > 0;
  const top = stack[stack.length - 1];

  const openItem = React.useCallback((id: string) => setStack([{ kind: "item", id }]), []);
  const openTxn  = React.useCallback((ref: string) => setStack([{ kind: "txn", id: ref }]), []);
  const pushItem = React.useCallback((id: string) => setStack(s => [...s, { kind: "item", id }]), []);
  const pushTxn  = React.useCallback((ref: string) => setStack(s => [...s, { kind: "txn", id: ref }]), []);
  const pop = React.useCallback(() => setStack(s => (s.length > 1 ? s.slice(0, -1) : [])), []);
  const close = React.useCallback(() => setStack([]), []);

  // Global right-click handler — anything with [data-upc] opens item.
  React.useEffect(() => {
    const onContext = (e: MouseEvent) => {
      const el = (e.target as HTMLElement)?.closest?.("[data-upc]") as HTMLElement | null;
      if (!el) return;
      const upc = el.getAttribute("data-upc");
      if (!upc) return;
      e.preventDefault();
      openItem(upc);
    };
    document.addEventListener("contextmenu", onContext);
    return () => document.removeEventListener("contextmenu", onContext);
  }, [openItem]);

  // Esc / Backspace navigation.
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape") close();
      else if (e.key === "Backspace" && stack.length > 1) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") { e.preventDefault(); pop(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, stack.length, pop, close]);

  const ctx: Ctx = { openItem, openTxn, close };

  return (
    <DrillCtx.Provider value={ctx}>
      {children}
      <Dialog open={open} onOpenChange={v => !v && close()}>
        <DialogContent hideClose className="p-0">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/40">
            <div className="flex items-center gap-3">
              {stack.length > 1 && (
                <Button size="sm" variant="ghost" onClick={pop}>
                  <ChevronLeft className="h-4 w-4 mr-1"/> Back
                </Button>
              )}
              <div className="text-sm font-semibold">
                {top?.kind === "item" ? "Item drill-down" : "Transaction / ITL detail"}
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted">
              {top?.kind === "item" && (
                <label className="flex items-center gap-1">
                  Months
                  <input
                    type="number" min={0} max={120}
                    value={months}
                    onChange={e => setMonths(Math.max(0, Number(e.target.value) || 0))}
                    className="h-7 w-14 rounded border border-input bg-surface px-2 text-sm text-fg"
                  />
                </label>
              )}
              <Button size="icon" variant="ghost" onClick={close}>
                <X className="h-4 w-4"/>
              </Button>
            </div>
          </div>
          <div className="overflow-auto max-h-[80vh] p-4">
            {top?.kind === "item" && <ItemView id={top.id} months={months} pushItem={pushItem} pushTxn={pushTxn} />}
            {top?.kind === "txn"  && <TxnView ref_={top.id} pushItem={pushItem} />}
          </div>
        </DialogContent>
      </Dialog>
    </DrillCtx.Provider>
  );
}

function ItemView({ id, months, pushItem, pushTxn }: {
  id: string; months: number;
  pushItem: (id: string) => void;
  pushTxn: (ref: string) => void;
}) {
  const q = useQuery<ItemDrillResponse>({
    queryKey: ["drill-item", id, months],
    queryFn: () => api.get("/api/item", { id, months }),
  });
  if (q.isLoading) return <Loading/>;
  if (q.isError || !q.data) return <Err msg="Failed to load item."/>;
  const d = q.data;
  if (!d.found) return (
    <div className="text-sm text-muted">
      <b className="text-fg">No item found</b> for <code>{d.identifier}</code>. Tried: {d.resolved_by}.
    </div>
  );
  const it = d.item!;
  const s  = d.summary;
  return (
    <div>
      <div className="mb-2">
        <div className="text-lg font-semibold"><code className="text-accent">{it.UPC}</code> · {it.Description}</div>
        <div className="text-xs text-muted">{it.Department} › {it.Category}</div>
        {!!d.alt_matches?.length && (
          <div className="text-xs text-muted mt-1">
            Also matched:{" "}
            {d.alt_matches.map(m =>
              <button key={m.UPC} className="text-accent hover:underline mr-2"
                onClick={() => pushItem(m.UPC)}>
                <code>{m.UPC}</code> {m.Description?.slice(0, 40)}
              </button>
            )}
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 my-3">
        <MiniCard label="On Hand" value={num(it.OnHand)}/>
        <MiniCard label="Open PO" value={num(it.OpenPOQty)}/>
        <MiniCard label="Avg / Mo" value={num(it.AvgMonthlySales, 2)}/>
        <MiniCard label="Current MoS" value={it.CurrentMoS == null ? "∞" : num(it.CurrentMoS, 1)}/>
        <MiniCard label="Days → stockout" value={it.DaysToStockout == null ? "—" : num(it.DaysToStockout)}/>
        <MiniCard label="Unit Cost" value={money(it.Cost, { digits: 2 })}/>
        <MiniCard label="Retail" value={money(it.Price, { digits: 2 })}/>
        <MiniCard label="Risk" value={<RiskBadge risk={it.Risk}/>}/>
      </div>
      {s && (
        <div className="text-xs text-muted mb-3">
          Last {d.history_months} months: <b className="text-fg">{num(s.transaction_count)}</b> transactions ·
          sold <b className="text-fg">{num(s.units_sold_abs)}</b> units ·
          received <b className="text-fg">{num(s.units_received)}</b> units ·
          last sale: <b className="text-fg">{s.last_sale_in_window || "—"}</b> ·
          last receive: <b className="text-fg">{s.last_receive_in_window || "—"}</b>
        </div>
      )}

      {!!d.open_pos?.length && (
        <>
          <h4 className="text-xs uppercase tracking-wider text-muted font-semibold mt-4 mb-2">Open POs for this item</h4>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-xs">
              <thead className="bg-surface/60">
                <tr>
                  <th className="px-2 py-1 text-left">PO#</th>
                  <th className="px-2 py-1 text-left">Date</th>
                  <th className="px-2 py-1 text-left">Supplier</th>
                  <th className="px-2 py-1 text-right">Ordered</th>
                  <th className="px-2 py-1 text-right">Received</th>
                  <th className="px-2 py-1 text-right">Open</th>
                  <th className="px-2 py-1 text-right">Unit Cost</th>
                  <th className="px-2 py-1 text-right">Line Total</th>
                </tr>
              </thead>
              <tbody>
                {d.open_pos.map(p => (
                  <tr key={p.PONumber} className="border-t border-border/60">
                    <td className="px-2 py-1"><a className="text-accent hover:underline" href={`/po/${encodeURIComponent(p.PONumber)}`} target="_blank">{p.PONumber}</a></td>
                    <td className="px-2 py-1">{dt(p.PODate)}</td>
                    <td className="px-2 py-1">{p.SupplierName}</td>
                    <td className="num px-2 py-1">{num(p.QtyOrdered)}</td>
                    <td className="num px-2 py-1">{num(p.QtyReceived)}</td>
                    <td className="num px-2 py-1"><b>{num(p.QtyOpen)}</b></td>
                    <td className="num px-2 py-1">{money(p.UnitCost, { digits: 2 })}</td>
                    <td className="num px-2 py-1">{money(p.LineTotal, { digits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h4 className="text-xs uppercase tracking-wider text-muted font-semibold mt-4 mb-2">
        Transactions ({d.transactions?.length ?? 0}, newest first)
      </h4>
      {d.transactions?.length ? (
        <div className="overflow-x-auto rounded border border-border max-h-96">
          <table className="w-full text-xs">
            <thead className="bg-surface/60 sticky top-0">
              <tr>
                <th className="px-2 py-1 text-left">Date</th>
                <th className="px-2 py-1 text-left">Type</th>
                <th className="px-2 py-1 text-right">Qty</th>
                <th className="px-2 py-1 text-right">Unit Price</th>
                <th className="px-2 py-1 text-right">Line Total</th>
                <th className="px-2 py-1 text-right">Running</th>
                <th className="px-2 py-1 text-left">Reference</th>
              </tr>
            </thead>
            <tbody>
              {[...d.transactions].reverse().map((t, i) => {
                const neg = typeof t.RunningQty === "number" && t.RunningQty < 0;
                return (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-2 py-1">{t.TxnDate?.slice(0, 16)}</td>
                    <td className="px-2 py-1">{t.TxnType}</td>
                    <td className="num px-2 py-1">{num(t.QtyImpact, 2)}</td>
                    <td className="num px-2 py-1">{money(t.UnitPrice, { digits: 2 })}</td>
                    <td className="num px-2 py-1">{money(t.LineTotal, { digits: 2 })}</td>
                    <td className={cn("num px-2 py-1 font-semibold", neg && "text-bad")}>{num(t.RunningQty, 2)}</td>
                    <td className="px-2 py-1">
                      <button onClick={() => pushTxn(t.Reference)} className="text-accent hover:underline font-mono">
                        {t.Reference}
                      </button>
                      {t.PONumber && <div className="text-[10px] mt-0.5">PO {t.PONumber}{t.SupplierName ? ` · ${t.SupplierName}` : ""}</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-sm text-muted py-2">No transactions in the selected window.</div>
      )}
    </div>
  );
}

function TxnView({ ref_, pushItem }: { ref_: string; pushItem: (id: string) => void }) {
  const q = useQuery<TxnDrillResponse>({
    queryKey: ["drill-txn", ref_],
    queryFn: () => api.get("/api/transaction", { ref: ref_ }),
  });
  if (q.isLoading) return <Loading/>;
  if (q.isError || !q.data) return <Err msg="Failed to load transaction."/>;
  const d = q.data;
  if (!d.found) return <div className="text-sm text-muted">No details found for <code>{d.reference}</code>.</div>;
  const isSale = d.kind === "transaction";
  return (
    <div>
      <div className="text-lg font-semibold mb-1"><code className="text-accent">{d.reference}</code> · {d.type}</div>
      <div className="text-xs text-muted mb-3">
        {d.event_time && <>When: <b className="text-fg">{d.event_time}</b> · </>}
        Lines: <b className="text-fg">{d.lines?.length ?? 0}</b> ·
        Total qty: <b className="text-fg">{num(d.total_qty, 2)}</b> ·
        Total value: <b className="text-fg">{money(d.total_value, { digits: 2 })}</b>
      </div>
      {isSale && d.header && (
        <div className="text-xs text-muted mb-3">
          Txn# <b className="text-fg">{d.header.TransactionNumber}</b> ·
          Subtotal <b className="text-fg">{money(d.header.SubTotal, { digits: 2 })}</b> ·
          Tax <b className="text-fg">{money(d.header.SalesTax, { digits: 2 })}</b> ·
          Total <b className="text-fg">{money(d.header.Total, { digits: 2 })}</b>
        </div>
      )}
      {d.lines?.length ? (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-xs">
            <thead className="bg-surface/60">
              <tr>
                {!isSale && <th className="px-2 py-1 text-left">ITL ID</th>}
                <th className="px-2 py-1 text-left">UPC</th>
                <th className="px-2 py-1 text-left">Description</th>
                <th className="px-2 py-1 text-left">Dept</th>
                <th className="px-2 py-1 text-right">Qty</th>
                <th className="px-2 py-1 text-right">{isSale ? "Unit Price" : "Unit Cost"}</th>
                <th className="px-2 py-1 text-right">Line Total</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {d.lines.map((l, i) => {
                const isSrc = !isSale && d.source_id && l.ID === d.source_id;
                return (
                  <tr key={i} className={cn("border-t border-border/60", isSrc && "bg-warn/10")}>
                    {!isSale && <td className="px-2 py-1 font-mono">ITL#{l.ID}{isSrc && <b className="text-warn ml-1">(origin)</b>}</td>}
                    <td className="px-2 py-1"><button onClick={() => pushItem(l.UPC)} className="text-accent hover:underline font-mono">{l.UPC}</button></td>
                    <td className="px-2 py-1">{l.Description}</td>
                    <td className="px-2 py-1">{l.Department}</td>
                    <td className="num px-2 py-1">{num(l.Quantity, 2)}</td>
                    <td className="num px-2 py-1">{money(isSale ? l.Price : l.Cost, { digits: 2 })}</td>
                    <td className="num px-2 py-1">{money(l.LineTotal, { digits: 2 })}</td>
                    <td className="px-2 py-1"><button onClick={() => pushItem(l.UPC)} className="text-xs text-muted hover:text-accent">drill →</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-sm text-muted">No line items found.</div>
      )}
    </div>
  );
}

function MiniCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded border border-border bg-surface/40 p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="text-base font-semibold mt-0.5">{value}</div>
    </div>
  );
}
function Loading() { return <div className="flex items-center justify-center py-12 text-muted"><Loader2 className="h-4 w-4 animate-spin mr-2"/> Loading…</div>; }
function Err({ msg }: { msg: string }) { return <div className="text-sm text-bad py-4">{msg}</div>; }

/** Small clickable magnifying-glass icon to drop next to UPC cells. */
export function DrillIcon({ upc, className }: { upc: string; className?: string }) {
  const { openItem } = useDrill();
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); openItem(upc); }}
      className={cn("text-muted hover:text-accent text-xs", className)}
      title="Drill into item"
    >🔍</button>
  );
}
