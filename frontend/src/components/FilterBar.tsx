import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface FilterField {
  name: string;
  label: string;
  type?: "text" | "number" | "select";
  options?: Array<{ label: string; value: string }>;
  defaultValue?: string | number;
  width?: string;
  title?: string;
  placeholder?: string;
}

export interface FilterBarProps {
  fields: FilterField[];
  onSubmit?: (params: URLSearchParams) => void;
  rightSlot?: React.ReactNode;
}

export function FilterBar({ fields, onSubmit, rightSlot }: FilterBarProps) {
  const [searchParams, setSearchParams] = useSearchParams();

  const handle = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const next = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      const sv = String(v).trim();
      if (sv) next.set(k, sv);
    }
    setSearchParams(next);
    onSubmit?.(next);
  };

  return (
    <form onSubmit={handle} className="flex flex-wrap items-end gap-3 bg-surface/40 border border-border rounded-lg p-3 mb-4">
      {fields.map(f => {
        const cur = searchParams.get(f.name) ?? String(f.defaultValue ?? "");
        return (
          <label key={f.name} className="flex flex-col gap-1 text-xs text-muted" title={f.title}>
            <span>{f.label}</span>
            {f.type === "select" ? (
              <select
                name={f.name}
                defaultValue={cur}
                className="h-9 rounded-md border border-input bg-surface px-2 text-sm text-fg"
                style={f.width ? { width: f.width } : undefined}
              >
                {(f.options ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : (
              <Input
                name={f.name}
                type={f.type ?? "text"}
                defaultValue={cur}
                placeholder={f.placeholder}
                style={f.width ? { width: f.width } : undefined}
                className="text-sm"
              />
            )}
          </label>
        );
      })}
      <Button type="submit" size="sm">Apply</Button>
      {rightSlot}
    </form>
  );
}
