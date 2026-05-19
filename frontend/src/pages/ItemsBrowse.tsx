import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/api/client";
import { money, num, dt } from "@/lib/format";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DrillIcon } from "@/components/DrillDown";

interface ItemRow {
  ID: number; UPC: string; Description: string; Department: string;
  Category: string; SupplierName: string; OnHand: number;
  Cost: number; Price: number; LastSold: string;
}

export function ItemsBrowse() {
  const [params] = useSearchParams();
  const q = useQuery<{ count: number; rows: ItemRow[] }>({
    queryKey: ["items", params.toString()],
    queryFn: () => api.get("/api/items", Object.fromEntries(params)),
  });
  const cols: ColumnDef<ItemRow, any>[] = [
    { accessorKey: "UPC", header: "UPC",
      cell: c => <span data-upc={c.getValue<string>()} className="font-mono">{c.getValue<string>()} <DrillIcon upc={c.getValue<string>()}/></span> },
    { accessorKey: "Description", header: "Description" },
    { accessorKey: "Department", header: "Dept" },
    { accessorKey: "Category", header: "Cat" },
    { accessorKey: "SupplierName", header: "Supplier" },
    { accessorKey: "OnHand", header: "OnHand", cell: c => num(c.getValue<number>()), meta: { align: "right" } },
    { accessorKey: "Cost", header: "Cost", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "Price", header: "Price", cell: c => money(c.getValue<number>(), { digits: 2 }), meta: { align: "right" } },
    { accessorKey: "LastSold", header: "Last sold", cell: c => dt(c.getValue<string>()) },
  ];
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Items</h1>
      <p className="text-sm text-muted mb-4">Browse the active catalog. Right-click any UPC to drill in.</p>
      <FilterBar fields={[
        { name: "q", label: "Search", type: "text", placeholder: "UPC or description" },
        { name: "dept", label: "Dept", type: "text", width: "150px" },
        { name: "supplier", label: "Supplier", type: "text", width: "180px" },
        { name: "limit", label: "Limit", type: "number", defaultValue: 200, width: "90px" },
      ]}/>
      {q.isLoading && <div className="text-muted">Loading…</div>}
      {q.data && (
        <>
          <p className="text-xs text-muted mb-2">{num(q.data.count)} items</p>
          <DataTable columns={cols} data={q.data.rows} dense/>
        </>
      )}
    </div>
  );
}
