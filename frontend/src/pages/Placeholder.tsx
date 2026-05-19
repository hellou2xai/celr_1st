import { Construction } from "lucide-react";
import { Link } from "react-router-dom";

export function Placeholder({ title, plan }: { title: string; plan?: string }) {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">{title}</h1>
      <div className="rounded-lg border border-warn/40 bg-warn/5 p-6 my-6">
        <div className="flex items-center gap-3 text-warn font-semibold">
          <Construction className="h-5 w-5"/> Page under construction
        </div>
        <p className="mt-2 text-sm text-muted">
          This page is part of the React port of <code>procurement_app/</code> and hasn't been built yet.
          See <code>render_demo/CURRENT_APP_AUDIT.md</code> for the full feature inventory.
        </p>
        {plan && (
          <p className="mt-2 text-sm text-muted">
            <span className="text-fg font-medium">Planned scope:</span> {plan}
          </p>
        )}
        <p className="mt-3 text-xs text-muted">
          <Link to="/" className="text-accent hover:underline">← Back to dashboard</Link>
        </p>
      </div>
    </div>
  );
}
