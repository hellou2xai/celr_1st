import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { OpenPOs }   from "@/pages/OpenPOs";
import { RTV }       from "@/pages/RTV";
import { Stockouts } from "@/pages/Stockouts";
import { ExcessStock } from "@/pages/ExcessStock";
import { ItemsBrowse } from "@/pages/ItemsBrowse";
import { POsBrowse } from "@/pages/POsBrowse";
import { PODetail } from "@/pages/PODetail";
import { Invoices, InvoiceDetail } from "@/pages/Invoices";
import { RiskCalc, RiskCalcAliases } from "@/pages/RiskCalc";
import { OrderSuggestions } from "@/pages/OrderSuggestions";
import { Optimizer } from "@/pages/Optimizer";
import { RIPPrograms, RIPOptimize, RIPOrderSuggestions, RIPItemDetail } from "@/pages/RIP";
import { ItemAnalytics } from "@/pages/ItemAnalytics";
import { SalesAnalysis } from "@/pages/SalesAnalysis";
import { POSpend } from "@/pages/POSpend";
import { CostAnalysis } from "@/pages/CostAnalysis";
import { PricingAnalysis } from "@/pages/PricingAnalysis";
import { Advisor } from "@/pages/Advisor";
import { DataFiles } from "@/pages/DataFiles";
import { Config } from "@/pages/Config";
import { Login } from "@/pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login/>}/>

      <Route element={<Layout/>}>
        <Route path="/" element={<Dashboard/>}/>

        {/* Buying */}
        <Route path="/risk-calc"             element={<RiskCalc/>}/>
        <Route path="/risk-calc/aliases"     element={<RiskCalcAliases/>}/>
        <Route path="/order-suggestions"     element={<OrderSuggestions/>}/>
        <Route path="/rip-order-suggestions" element={<RIPOrderSuggestions/>}/>
        <Route path="/optimizer"             element={<Optimizer/>}/>
        <Route path="/rip"                   element={<RIPPrograms/>}/>
        <Route path="/rip/programs"          element={<RIPPrograms/>}/>
        <Route path="/rip/optimize"          element={<RIPOptimize/>}/>
        <Route path="/rip-item/:id"          element={<RIPItemDetail/>}/>

        {/* Review */}
        <Route path="/open-pos"     element={<OpenPOs/>}/>
        <Route path="/rtv"          element={<RTV/>}/>
        <Route path="/excess-stock" element={<ExcessStock/>}/>
        <Route path="/stockouts"    element={<Stockouts/>}/>

        {/* Analytics */}
        <Route path="/analytics/item"     element={<ItemAnalytics/>}/>
        <Route path="/sales-analysis"     element={<SalesAnalysis/>}/>
        <Route path="/analytics/po-spend" element={<POSpend/>}/>
        <Route path="/analytics/cost"     element={<CostAnalysis/>}/>
        <Route path="/analytics/pricing"  element={<PricingAnalysis/>}/>

        {/* Browse */}
        <Route path="/items"     element={<ItemsBrowse/>}/>
        <Route path="/pos"       element={<POsBrowse/>}/>
        <Route path="/po/:po"    element={<PODetail/>}/>
        <Route path="/invoices"  element={<Invoices/>}/>
        <Route path="/invoices/:id" element={<InvoiceDetail/>}/>

        {/* AI / Admin */}
        <Route path="/advisor" element={<Advisor/>}/>
        <Route path="/data"    element={<DataFiles/>}/>
        <Route path="/config"  element={<Config/>}/>

        <Route path="*" element={<Navigate to="/" replace/>}/>
      </Route>
    </Routes>
  );
}
