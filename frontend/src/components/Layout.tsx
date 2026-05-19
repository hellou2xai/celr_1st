import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { DrillDownProvider } from "./DrillDown";

export function Layout() {
  return (
    <DrillDownProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar/>
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-[1700px] mx-auto">
            <Outlet/>
          </div>
        </main>
      </div>
      <div className="fixed bottom-3 right-4 text-xs text-muted/70 pointer-events-none bg-card/80 border border-border rounded px-2 py-1">
        💡 Right-click any UPC for full item drill-down
      </div>
    </DrillDownProvider>
  );
}
