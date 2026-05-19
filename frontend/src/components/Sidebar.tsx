import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Calculator, Package, Target, Coins, Gift,
  ClipboardList, Undo2, Archive, TriangleAlert,
  ChartBar, TrendingUp, DollarSign, Tags,
  ShoppingCart, FileText, Receipt,
  Brain, Database, Settings, ChevronLeft, ChevronRight
} from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const GROUPS: (NavGroup | NavItem)[] = [
  { to: "/", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4"/> },
  { label: "Buying", items: [
      { to: "/risk-calc",            label: "Pre-PO Risk Calc",      icon: <Calculator className="h-4 w-4"/> },
      { to: "/order-suggestions",    label: "PO Suggestions",         icon: <Package    className="h-4 w-4"/> },
      { to: "/rip-order-suggestions",label: "RIP Order Suggestions",  icon: <Target     className="h-4 w-4"/> },
      { to: "/optimizer",            label: "Buy Optimizer",          icon: <Coins      className="h-4 w-4"/> },
      { to: "/rip",                  label: "RIP Programs",           icon: <Gift       className="h-4 w-4"/> },
  ]},
  { label: "Review", items: [
      { to: "/open-pos",      label: "Open POs · Cancel/Reduce", icon: <ClipboardList className="h-4 w-4"/> },
      { to: "/rtv",           label: "Return to Vendor",         icon: <Undo2         className="h-4 w-4"/> },
      { to: "/excess-stock",  label: "Excess Stock",             icon: <Archive       className="h-4 w-4"/> },
      { to: "/stockouts",     label: "Stockouts",                icon: <TriangleAlert className="h-4 w-4"/> },
  ]},
  { label: "Analytics", items: [
      { to: "/analytics/item",     label: "Item Analytics",   icon: <ChartBar    className="h-4 w-4"/> },
      { to: "/sales-analysis",     label: "Sales Analytics",  icon: <TrendingUp  className="h-4 w-4"/> },
      { to: "/analytics/po-spend", label: "PO Spend Analysis",icon: <DollarSign  className="h-4 w-4"/> },
      { to: "/analytics/cost",     label: "Cost Analysis",    icon: <Coins       className="h-4 w-4"/> },
      { to: "/analytics/pricing",  label: "Pricing Analytics",icon: <Tags        className="h-4 w-4"/> },
  ]},
  { label: "Browse", items: [
      { to: "/items",       label: "Items",          icon: <ShoppingCart className="h-4 w-4"/> },
      { to: "/pos",         label: "Purchase Orders",icon: <FileText     className="h-4 w-4"/> },
      { to: "/invoices",    label: "Invoices",       icon: <Receipt      className="h-4 w-4"/> },
  ]},
  { label: "AI",    items: [{ to: "/advisor", label: "AI Advisor", icon: <Brain className="h-4 w-4"/> }]},
  { label: "Admin", items: [
      { to: "/data",   label: "Data files", icon: <Database className="h-4 w-4"/> },
      { to: "/config", label: "Config",     icon: <Settings className="h-4 w-4"/> },
  ]},
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem("sidebar_collapsed") === "1"
  );
  useEffect(() => {
    localStorage.setItem("sidebar_collapsed", collapsed ? "1" : "0");
  }, [collapsed]);

  return (
    <aside className={cn(
      "border-r border-border bg-surface/40 flex flex-col transition-all",
      collapsed ? "w-14" : "w-60"
    )}>
      <div className={cn("p-4 border-b border-border", collapsed && "px-2")}>
        <div className="flex items-center gap-2">
          <span className="text-accent font-bold tracking-widest text-sm">●●●</span>
          {!collapsed && <span className="font-mono text-sm">CELR <span className="text-accent">· AI</span></span>}
        </div>
        {!collapsed && <div className="text-[10px] text-muted mt-1 uppercase tracking-wider">Procurement</div>}
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {GROUPS.map((g, i) => {
          if ("to" in g) return <NavRow key={g.to} item={g} collapsed={collapsed}/>;
          return (
            <div key={i} className="mb-1">
              {!collapsed && (
                <div className="px-4 mt-3 mb-1 text-[10px] uppercase tracking-wider text-muted/70 font-semibold">
                  {g.label}
                </div>
              )}
              {g.items.map(it => <NavRow key={it.to} item={it} collapsed={collapsed}/>)}
            </div>
          );
        })}
      </nav>

      <div className="border-t border-border p-2 flex items-center justify-between gap-2">
        {!collapsed && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="h-2 w-2 rounded-full bg-good"/>
            <span>online</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="ml-auto text-muted hover:text-fg p-1"
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4"/> : <ChevronLeft className="h-4 w-4"/>}
        </button>
      </div>
    </aside>
  );
}

function NavRow({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      className={({ isActive }) => cn(
        "flex items-center gap-3 px-4 py-1.5 text-sm hover:bg-surface transition-colors",
        collapsed && "px-3 justify-center",
        isActive ? "text-fg bg-surface border-l-2 border-accent" : "text-muted border-l-2 border-transparent"
      )}
      title={collapsed ? item.label : undefined}
    >
      {item.icon}
      {!collapsed && <span className="truncate">{item.label}</span>}
    </NavLink>
  );
}
