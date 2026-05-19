import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { OpenPOs }   from "@/pages/OpenPOs";
import { RTV }       from "@/pages/RTV";
import { Stockouts } from "@/pages/Stockouts";
import { Placeholder } from "@/pages/Placeholder";
import { Login } from "@/pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login/>}/>

      <Route element={<Layout/>}>
        <Route path="/" element={<Dashboard/>}/>

        {/* Buying */}
        <Route path="/risk-calc"             element={<Placeholder title="Pre-PO Risk Calc"            plan="Paste UPC+qty → risk summary + line breakdown + alias save + Excel export. Mirrors procurement_app/templates/risk_calc.html."/>}/>
        <Route path="/risk-calc/aliases"     element={<Placeholder title="Risk Calc Aliases"          plan="Manage UPC↔ItemCode aliases used by Pre-PO Risk Calc."/>}/>
        <Route path="/order-suggestions"     element={<Placeholder title="Purchase Order Suggestions" plan="20+ filter form, RIP integration, action/wait-days filters, sortable table, Excel export."/>}/>
        <Route path="/rip-order-suggestions" element={<Placeholder title="RIP Order Suggestions"      plan="Filters by RIP month, tier flags, rebate-per-unit math, row → /rip-item/<id>."/>}/>
        <Route path="/optimizer"             element={<Placeholder title="Buy Optimizer"              plan="Basket workflow, vendor/combo cheapest-mix optimizer with current pricing + RIP combos."/>}/>
        <Route path="/rip"                   element={<Placeholder title="RIP Programs"               plan="Monthly RIP program list with tier rebates, filters by month/supplier/brand."/>}/>
        <Route path="/rip/programs"          element={<Placeholder title="RIP Programs"               plan="(Alias of /rip.)"/>}/>
        <Route path="/rip/optimize"          element={<Placeholder title="RIP Optimizer"              plan="Per-month combo + rebate optimization."/>}/>
        <Route path="/rip-item/:id"          element={<Placeholder title="RIP Item Detail"            plan="Per-item RIP detail + claim status (EXPECTED / RECEIVED / OVERDUE / DISPUTED / DECLINED)."/>}/>

        {/* Review */}
        <Route path="/open-pos"     element={<OpenPOs/>}/>
        <Route path="/rtv"          element={<RTV/>}/>
        <Route path="/excess-stock" element={<Placeholder title="Excess Stock"            plan="9-param filter, 6 tables incl. aging×risk grid, Excel export."/>}/>
        <Route path="/stockouts"    element={<Stockouts/>}/>

        {/* Analytics */}
        <Route path="/analytics/item"     element={<Placeholder title="Item Analytics"     plan="Single-item drill + compare mode. 6 KPI cards + 4 charts. Autocomplete pickers."/>}/>
        <Route path="/sales-analysis"     element={<Placeholder title="Sales Analytics"    plan="8 tabbed sub-views: Top sellers, Multi-year, Weekly YoY, Movers, Seasonality, Hierarchy, Transactions, ABC."/>}/>
        <Route path="/analytics/po-spend" element={<Placeholder title="PO Spend Analysis"  plan="5 tabs: Overview, Suppliers (Pareto), Categories, Time, Items + Variance."/>}/>
        <Route path="/analytics/cost"     element={<Placeholder title="Cost Analysis"      plan="4 charts: cost over time, % change, vs retail/margin, range. Summary + movers tables."/>}/>
        <Route path="/analytics/pricing"  element={<Placeholder title="Pricing Analytics"  plan="4 charts: price over time, current retail/sale/cost, promo activity, max discount."/>}/>

        {/* Browse */}
        <Route path="/items"     element={<Placeholder title="Items"            plan="Search + dept/cat/supplier filters, table with on-hand/cost/price/last sold."/>}/>
        <Route path="/pos"       element={<Placeholder title="Purchase Orders"  plan="PO list with filters + Excel export."/>}/>
        <Route path="/po/:po"    element={<Placeholder title="PO Detail"        plan="Header tiles, header details table, sortable line items with drill-down per UPC."/>}/>
        <Route path="/invoices"  element={<Placeholder title="Invoices"         plan="Upload PDF form, recent invoices list."/>}/>
        <Route path="/invoices/:id" element={<Placeholder title="Invoice Detail" plan="Per-line match status, supplier-code → ItemLookupCode mapping, delete, Excel export."/>}/>

        {/* AI / Admin */}
        <Route path="/advisor" element={<Placeholder title="AI Advisor" plan="Daily briefing card, ask form (/api/ask), explain endpoint, refresh. Requires LLM key."/>}/>
        <Route path="/data"    element={<Placeholder title="Data Files" plan="Browse + download local CSVs / Excel exports."/>}/>
        <Route path="/config"  element={<Placeholder title="Config"     plan="Read-only display of supplier policies, risk thresholds, env settings."/>}/>

        <Route path="*" element={<Navigate to="/" replace/>}/>
      </Route>
    </Routes>
  );
}
