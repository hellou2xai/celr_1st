import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useParams, Link } from "react-router-dom";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { KpiTile } from "@/components/KpiTile";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";

interface Month { Month: string; Label: string; Programs: number; Combos: number; }
interface Program {
  id: number;
  Month: string; UPC: string; Brand: string; Description: string;
  RipCode: string; Supplier: string;
  ValidFrom: string; ValidTo: string;
  Tier1Unit: string; Tier1Qty: number; Tier1Rebate: number;
  Tier2Unit?: string; Tier2Qty?: number; Tier2Rebate?: number;
  Comments?: string;
  ItemID?: number; OnHand?: number;
}
interface ProgramsResp {
  rows: Program[];
  summary: { programs: number; potential_rebate: number };
  months: Month[]; month: string;
  note?: string;
}

function MonthPicker({ months, value }: { months: Month[]; value: string }) {
  const [, setParams] = useSearchParams();
  return (
    <select
      value={value}
      onChange={e => setParams({ month: e.target.value })}
      className="h-9 rounded-md border border-input bg-surface px-2 text-sm text-fg"
    >
      {months.map(m => (
        <option key={m.Month} value={m.Month}>
          {m.Label} ({num(m.Programs)} programs)
        </option>
      ))}
    </select>
  );
}

function EmptyRipState({ note }: { note: string }) {
  return (
    <div className="rounded-lg border border-warn/40 bg-warn/5 p-6 mt-4">
      <p className="text-sm">{note}</p>
      <p className="text-xs text-muted mt-2">
        Run <code>extract/extract_rip.py</code> against the original SQLite store
        (<code>procurement_app/rip.db</code>), commit the resulting{" "}
        <code>data/rip_*.csv</code> files, push to GitHub, then on Render Shell:{" "}
        <code>FORCE_RIP_RELOAD=true python -m seed.seed</code>.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------- //
// RIP Programs (list)
// --------------------------------------------------------------------- //

export function RIPPrograms() {
  const [params] = useSearchParams();
  const q = useQuery<ProgramsResp>({
    queryKey: ["rip-programs", params.toString()],
    queryFn: () => api.get("/api/rip/programs", Object.fromEntries(params)),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">RIP Programs</h1>
      <p className="text-sm text-muted mb-4">Monthly rebate / incentive programs by distributor.</p>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data?.note && <EmptyRipState note={q.data.note}/>}
      {q.data && !q.data.note && (
        <>
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <label className="text-xs text-muted">Month
              <div className="mt-1">
                <MonthPicker months={q.data.months} value={q.data.month}/>
              </div>
            </label>
          </div>
          <FilterBar fields={[
            { name: "month", label: "Month (override)", type: "text", defaultValue: q.data.month, width: "100px" },
            { name: "brand", label: "Brand", type: "text", width: "150px" },
            { name: "supplier", label: "Supplier", type: "text", width: "180px" },
            { name: "q", label: "Search", type: "text", placeholder: "UPC or description" },
            { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
          ]}/>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="Programs" value={num(q.data.summary.programs)} variant="info"/>
            <KpiTile label="Potential rebate" value={money(q.data.summary.potential_rebate)} variant="good"/>
            <KpiTile label="Month" value={q.data.month} variant="neutral"/>
          </div>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Brand</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">RIP code</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1 rebate</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 2</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 2 rebate</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Valid</th>
                <th></th>
              </tr></thead>
              <tbody>
                {q.data.rows.map(r => (
                  <tr key={r.id} className="border-t border-border/60 hover:bg-surface/40">
                    <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                    <td className="px-3 py-1.5">{r.Brand}</td>
                    <td className="px-3 py-1.5">{r.Description}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.RipCode}</td>
                    <td className="num px-3 py-1.5">{num(r.Tier1Qty)} {r.Tier1Unit}</td>
                    <td className="num px-3 py-1.5">{money(r.Tier1Rebate, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5">{r.Tier2Qty ? `${num(r.Tier2Qty)} ${r.Tier2Unit}` : "—"}</td>
                    <td className="num px-3 py-1.5">{r.Tier2Rebate ? money(r.Tier2Rebate, { digits: 2 }) : "—"}</td>
                    <td className="px-3 py-1.5 text-xs text-muted">{dt(r.ValidFrom)} → {dt(r.ValidTo)}</td>
                    <td className="px-3 py-1.5">
                      {r.ItemID && (
                        <Link to={`/rip-item/${r.ItemID}`} className="text-xs text-accent hover:underline">detail →</Link>
                      )}
                    </td>
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

// --------------------------------------------------------------------- //
// RIP Order Suggestions
// --------------------------------------------------------------------- //

interface RipOrderRow {
  id: number; UPC: string; Brand: string; Description: string;
  RipCode: string; Supplier: string;
  Tier1Qty: number; Tier1Rebate: number; ExpectedRebate: number;
  ValidFrom: string; ValidTo: string;
  OnHand: number; DailyUnits: number; MoSNow: number | null;
  SuggestedQty: number;
  ItemID: number;
}

export function RIPOrderSuggestions() {
  const [params] = useSearchParams();
  const q = useQuery<{
    rows: RipOrderRow[];
    summary: { lines: number; potential_rebate: number };
    months: Month[]; month: string;
    note?: string;
  }>({
    queryKey: ["rip-order-sugg", params.toString()],
    queryFn: () => api.get("/api/rip-order-suggestions", Object.fromEntries(params)),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">RIP Order Suggestions</h1>
      <p className="text-sm text-muted mb-4">Reorder list filtered to items with an active RIP program — ordered to maximize rebates.</p>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data?.note && <EmptyRipState note={q.data.note}/>}
      {q.data && !q.data.note && (
        <>
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <label className="text-xs text-muted">Month
              <div className="mt-1">
                <MonthPicker months={q.data.months} value={q.data.month}/>
              </div>
            </label>
          </div>
          <FilterBar fields={[
            { name: "month", label: "Month (override)", type: "text", defaultValue: q.data.month, width: "100px" },
            { name: "supplier", label: "Supplier", type: "text", width: "180px" },
            { name: "limit", label: "Limit", type: "number", defaultValue: 500, width: "90px" },
          ]}/>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="Active programs" value={num(q.data.summary.lines)} variant="info"/>
            <KpiTile label="Potential rebate (tier 1)" value={money(q.data.summary.potential_rebate)} variant="good"/>
            <KpiTile label="Month" value={q.data.month} variant="neutral"/>
          </div>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Supplier</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">OnHand</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Avg / day</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">MoS now</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1 qty</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1 rebate</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Suggested buy</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Expected rebate</th>
              </tr></thead>
              <tbody>
                {q.data.rows.map(r => (
                  <tr key={r.id} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono" data-upc={r.UPC}>{r.UPC} <DrillIcon upc={r.UPC}/></td>
                    <td className="px-3 py-1.5">{r.Description}</td>
                    <td className="px-3 py-1.5">{r.Supplier}</td>
                    <td className="num px-3 py-1.5">{num(r.OnHand)}</td>
                    <td className="num px-3 py-1.5">{num(r.DailyUnits, 2)}</td>
                    <td className="num px-3 py-1.5">{r.MoSNow == null ? "∞" : num(r.MoSNow, 1)}</td>
                    <td className="num px-3 py-1.5">{num(r.Tier1Qty)}</td>
                    <td className="num px-3 py-1.5">{money(r.Tier1Rebate, { digits: 2 })}</td>
                    <td className="num px-3 py-1.5"><b>{num(r.SuggestedQty)}</b></td>
                    <td className="num px-3 py-1.5 text-good">{money(r.ExpectedRebate)}</td>
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

// --------------------------------------------------------------------- //
// RIP Optimize (combos)
// --------------------------------------------------------------------- //

interface ComboRow {
  id: number; ComboCode: string; UPC: string; Brand: string;
  Description: string; QtyItems: number; QtyUnit: string;
  FlinePrice: number; ComboPrice: number; Savings: number;
  ValidFrom: string; ValidTo: string; OnHand?: number;
}

export function RIPOptimize() {
  const [params] = useSearchParams();
  const q = useQuery<{ combos: ComboRow[]; summary: { combos: number; total_savings: number }; months: Month[]; month: string; note?: string }>({
    queryKey: ["rip-optimize", params.toString()],
    queryFn: () => api.get("/api/rip/optimize", Object.fromEntries(params)),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">RIP Optimizer</h1>
      <p className="text-sm text-muted mb-4">Combo offers across SKUs — buy together for bundled pricing + extra savings.</p>

      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data?.note && <EmptyRipState note={q.data.note}/>}
      {q.data && !q.data.note && (
        <>
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <label className="text-xs text-muted">Month
              <div className="mt-1">
                <MonthPicker months={q.data.months} value={q.data.month}/>
              </div>
            </label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <KpiTile label="Combo offers" value={num(q.data.summary.combos)} variant="info"/>
            <KpiTile label="Total potential savings" value={money(q.data.summary.total_savings)} variant="good"/>
            <KpiTile label="Month" value={q.data.month} variant="neutral"/>
          </div>
          <div className="overflow-x-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Combo</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">UPC</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Description</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Qty</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">List price</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Combo price</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Savings</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Valid</th>
              </tr></thead>
              <tbody>
                {q.data.combos.map(c => (
                  <tr key={c.id} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono text-xs">{c.ComboCode}</td>
                    <td className="px-3 py-1.5 font-mono" data-upc={c.UPC}>{c.UPC} <DrillIcon upc={c.UPC}/></td>
                    <td className="px-3 py-1.5">{c.Description}</td>
                    <td className="num px-3 py-1.5">{num(c.QtyItems)} {c.QtyUnit}</td>
                    <td className="num px-3 py-1.5">{money(c.FlinePrice)}</td>
                    <td className="num px-3 py-1.5">{money(c.ComboPrice)}</td>
                    <td className="num px-3 py-1.5 text-good">{money(c.Savings)}</td>
                    <td className="px-3 py-1.5 text-xs text-muted">{dt(c.ValidFrom)} → {dt(c.ValidTo)}</td>
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

// --------------------------------------------------------------------- //
// RIP Item Detail
// --------------------------------------------------------------------- //

interface ItemDetailResp {
  item: { id: number; item_lookup_code: string; description: string;
          quantity: number; cost: number; price: number; supplier: string; };
  programs: Array<{ id: number; Month: string; Brand: string; Description: string;
                    RipCode: string; Tier1Qty: number; Tier1Rebate: number;
                    Tier2Qty?: number; Tier2Rebate?: number;
                    ValidFrom: string; ValidTo: string; }>;
  combos: Array<{ id: number; Month: string; ComboCode: string; QtyItems: number;
                  QtyUnit: string; FlinePrice: number; ComboPrice: number;
                  Savings: number; ValidFrom: string; ValidTo: string; }>;
  claims: Array<{ id: number; PONumber: string; PODate: string; Month: string;
                  RipCode: string; Tier: number; Qty: number; Rebate: number;
                  Status: string; ReceivedOn?: string; ReceivedAmount?: number;
                  Notes?: string; DueBy?: string; }>;
  note?: string;
}

const STATUS_COLOR: Record<string, string> = {
  EXPECTED: "text-info", RECEIVED: "text-good",
  OVERDUE: "text-warn", DISPUTED: "text-bad", DECLINED: "text-muted",
};

export function RIPItemDetail() {
  const { id } = useParams();
  const q = useQuery<ItemDetailResp>({
    queryKey: ["rip-item", id],
    queryFn: () => api.get(`/api/rip-item/${id}`),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">RIP Item Detail</h1>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.isError && <div className="text-bad">Item not found.</div>}
      {q.data && (
        <>
          <div className="text-sm text-muted mb-4">
            <code className="text-accent">{q.data.item.item_lookup_code}</code> · {q.data.item.description}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiTile label="OnHand" value={num(q.data.item.quantity)}/>
            <KpiTile label="Cost" value={money(q.data.item.cost, { digits: 2 })}/>
            <KpiTile label="Price" value={money(q.data.item.price, { digits: 2 })}/>
            <KpiTile label="Supplier" value={q.data.item.supplier || "—"}/>
          </div>

          <h2 className="text-lg font-semibold mb-2">Programs ({q.data.programs.length})</h2>
          {q.data.programs.length ? (
            <div className="overflow-x-auto rounded border border-border mb-6">
              <table className="w-full text-sm">
                <thead className="bg-surface/60"><tr>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Month</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">RIP code</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 1 rebate</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 2</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Tier 2 rebate</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Valid</th>
                </tr></thead>
                <tbody>
                  {q.data.programs.map(p => (
                    <tr key={p.id} className="border-t border-border/60">
                      <td className="px-3 py-1.5">{p.Month}</td>
                      <td className="px-3 py-1.5 font-mono text-xs">{p.RipCode}</td>
                      <td className="num px-3 py-1.5">{num(p.Tier1Qty)}</td>
                      <td className="num px-3 py-1.5">{money(p.Tier1Rebate, { digits: 2 })}</td>
                      <td className="num px-3 py-1.5">{p.Tier2Qty ? num(p.Tier2Qty) : "—"}</td>
                      <td className="num px-3 py-1.5">{p.Tier2Rebate ? money(p.Tier2Rebate, { digits: 2 }) : "—"}</td>
                      <td className="px-3 py-1.5 text-xs text-muted">{dt(p.ValidFrom)} → {dt(p.ValidTo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-muted mb-6">No programs for this item.</p>}

          {!!q.data.combos.length && (
            <>
              <h2 className="text-lg font-semibold mb-2">Combos ({q.data.combos.length})</h2>
              <div className="overflow-x-auto rounded border border-border mb-6">
                <table className="w-full text-sm">
                  <thead className="bg-surface/60"><tr>
                    <th className="px-3 py-2 text-left text-xs uppercase text-muted">Month</th>
                    <th className="px-3 py-2 text-left text-xs uppercase text-muted">Combo</th>
                    <th className="px-3 py-2 text-right text-xs uppercase text-muted">Qty</th>
                    <th className="px-3 py-2 text-right text-xs uppercase text-muted">List</th>
                    <th className="px-3 py-2 text-right text-xs uppercase text-muted">Combo $</th>
                    <th className="px-3 py-2 text-right text-xs uppercase text-muted">Savings</th>
                  </tr></thead>
                  <tbody>
                    {q.data.combos.map(c => (
                      <tr key={c.id} className="border-t border-border/60">
                        <td className="px-3 py-1.5">{c.Month}</td>
                        <td className="px-3 py-1.5 font-mono text-xs">{c.ComboCode}</td>
                        <td className="num px-3 py-1.5">{num(c.QtyItems)} {c.QtyUnit}</td>
                        <td className="num px-3 py-1.5">{money(c.FlinePrice)}</td>
                        <td className="num px-3 py-1.5">{money(c.ComboPrice)}</td>
                        <td className="num px-3 py-1.5 text-good">{money(c.Savings)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <h2 className="text-lg font-semibold mb-2">Claim history ({q.data.claims.length})</h2>
          {q.data.claims.length ? (
            <div className="overflow-x-auto rounded border border-border">
              <table className="w-full text-sm">
                <thead className="bg-surface/60"><tr>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">PO</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Date</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Tier</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Qty</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Rebate</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Status</th>
                  <th className="px-3 py-2 text-left text-xs uppercase text-muted">Received on</th>
                  <th className="px-3 py-2 text-right text-xs uppercase text-muted">Received $</th>
                </tr></thead>
                <tbody>
                  {q.data.claims.map(cl => (
                    <tr key={cl.id} className="border-t border-border/60">
                      <td className="px-3 py-1.5">{cl.PONumber}</td>
                      <td className="px-3 py-1.5">{dt(cl.PODate)}</td>
                      <td className="px-3 py-1.5">{cl.Tier}</td>
                      <td className="num px-3 py-1.5">{num(cl.Qty)}</td>
                      <td className="num px-3 py-1.5">{money(cl.Rebate, { digits: 2 })}</td>
                      <td className={"px-3 py-1.5 font-semibold " + (STATUS_COLOR[cl.Status] ?? "")}>{cl.Status}</td>
                      <td className="px-3 py-1.5">{dt(cl.ReceivedOn) ?? "—"}</td>
                      <td className="num px-3 py-1.5">{cl.ReceivedAmount != null ? money(cl.ReceivedAmount, { digits: 2 }) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-muted">No claim history.</p>}
        </>
      )}
    </div>
  );
}
