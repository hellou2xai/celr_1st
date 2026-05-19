import * as React from "react";
import {
  useReactTable, getCoreRowModel, getSortedRowModel, flexRender,
  type ColumnDef, type SortingState,
} from "@tanstack/react-table";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DataTableProps<T> {
  columns: ColumnDef<T, any>[];
  data: T[];
  className?: string;
  empty?: React.ReactNode;
  dense?: boolean;
}

export function DataTable<T>({ columns, data, className, empty, dense = false }: DataTableProps<T>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!data.length) {
    return (
      <div className={cn("rounded border border-border bg-card/50 p-6 text-center text-sm text-muted", className)}>
        {empty ?? "No results."}
      </div>
    );
  }

  return (
    <div className={cn("overflow-x-auto rounded border border-border", className)}>
      <table className={cn("w-full text-sm", dense && "text-xs")}>
        <thead className="bg-surface/60 sticky top-0">
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id}>
              {hg.headers.map(h => {
                const sorted = h.column.getIsSorted();
                const canSort = h.column.getCanSort();
                const meta = (h.column.columnDef.meta ?? {}) as { align?: "right" | "left" };
                return (
                  <th
                    key={h.id}
                    onClick={canSort ? h.column.getToggleSortingHandler() : undefined}
                    className={cn(
                      "px-3 py-2 text-[11px] uppercase tracking-wider text-muted font-semibold border-b border-border whitespace-nowrap",
                      meta.align === "right" ? "text-right" : "text-left",
                      canSort && "cursor-pointer select-none hover:text-fg",
                    )}
                  >
                    <span className="inline-flex items-center gap-1">
                      {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                      {canSort && (sorted === "asc" ? <ChevronUp className="h-3 w-3"/> :
                                   sorted === "desc" ? <ChevronDown className="h-3 w-3"/> :
                                   <ChevronsUpDown className="h-3 w-3 opacity-50"/>)}
                    </span>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="border-b border-border/60 hover:bg-surface/40">
              {row.getVisibleCells().map(cell => {
                const meta = (cell.column.columnDef.meta ?? {}) as { align?: "right" | "left" };
                return (
                  <td
                    key={cell.id}
                    className={cn(
                      "px-3 py-1.5 whitespace-nowrap",
                      meta.align === "right" && "text-right font-mono",
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
