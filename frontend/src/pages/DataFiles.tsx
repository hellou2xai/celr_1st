import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { num, dt } from "@/lib/format";

export function DataFiles() {
  const q = useQuery<{ path: string; files: Array<{ name: string; size: number; modified: string }> }>({
    queryKey: ["data-files"],
    queryFn: () => api.get("/api/data-files"),
  });
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Data Files</h1>
      <p className="text-sm text-muted mb-4">Catalog CSVs that feed the synthetic seed.</p>
      {q.data && (
        <>
          <p className="text-xs text-muted mb-2 font-mono">{q.data.path}</p>
          <div className="rounded border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface/60"><tr>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">File</th>
                <th className="px-3 py-2 text-right text-xs uppercase text-muted">Size</th>
                <th className="px-3 py-2 text-left text-xs uppercase text-muted">Modified</th>
              </tr></thead>
              <tbody>
                {q.data.files.map(f => (
                  <tr key={f.name} className="border-t border-border/60">
                    <td className="px-3 py-1.5 font-mono">{f.name}</td>
                    <td className="num px-3 py-1.5">{num(f.size)}</td>
                    <td className="px-3 py-1.5">{dt(f.modified)}</td>
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
