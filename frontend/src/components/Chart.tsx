import * as React from "react";
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell,
} from "recharts";

const COLOURS = ["#d24a3b","#4ed28e","#f5b53d","#5a87f0","#a874f0",
                 "#3bd2c4","#e96aa3","#e8d44a","#7a8aa6","#bc6347"];

const GRID = "#2a2f3c";
const AXIS = "#8b93a6";

interface BaseProps {
  data: any[];
  xKey: string;
  yKeys: string[];
  height?: number;
  labels?: Record<string, string>;
  formatY?: (v: any) => string;
}

export function LineChartC({ data, xKey, yKeys, height = 240, labels, formatY }: BaseProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3"/>
        <XAxis dataKey={xKey} stroke={AXIS} tick={{ fontSize: 11 }}/>
        <YAxis stroke={AXIS} tick={{ fontSize: 11 }} tickFormatter={formatY}/>
        <Tooltip contentStyle={{ background: "#1b1f2b", border: "1px solid #2a2f3c", fontSize: 12 }}/>
        {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }}/>}
        {yKeys.map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} stroke={COLOURS[i % COLOURS.length]}
                strokeWidth={2} dot={false} name={labels?.[k] ?? k}/>
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function AreaChartC({ data, xKey, yKeys, height = 240, labels, formatY }: BaseProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3"/>
        <XAxis dataKey={xKey} stroke={AXIS} tick={{ fontSize: 11 }}/>
        <YAxis stroke={AXIS} tick={{ fontSize: 11 }} tickFormatter={formatY}/>
        <Tooltip contentStyle={{ background: "#1b1f2b", border: "1px solid #2a2f3c", fontSize: 12 }}/>
        {yKeys.map((k, i) => (
          <Area key={k} type="monotone" dataKey={k} stroke={COLOURS[i % COLOURS.length]}
                fill={COLOURS[i % COLOURS.length]} fillOpacity={0.2} name={labels?.[k] ?? k}/>
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function BarChartC({ data, xKey, yKeys, height = 240, labels, formatY, horizontal }:
  BaseProps & { horizontal?: boolean }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3"/>
        {horizontal ? (
          <>
            <XAxis type="number" stroke={AXIS} tick={{ fontSize: 11 }} tickFormatter={formatY}/>
            <YAxis type="category" dataKey={xKey} stroke={AXIS} tick={{ fontSize: 10 }} width={140}/>
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} stroke={AXIS} tick={{ fontSize: 11 }}/>
            <YAxis stroke={AXIS} tick={{ fontSize: 11 }} tickFormatter={formatY}/>
          </>
        )}
        <Tooltip contentStyle={{ background: "#1b1f2b", border: "1px solid #2a2f3c", fontSize: 12 }}/>
        {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }}/>}
        {yKeys.map((k, i) => (
          <Bar key={k} dataKey={k} fill={COLOURS[i % COLOURS.length]} name={labels?.[k] ?? k}/>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DonutChartC({ data, nameKey, valueKey, height = 240 }: {
  data: any[]; nameKey: string; valueKey: string; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey={valueKey} nameKey={nameKey}
             innerRadius="55%" outerRadius="85%" paddingAngle={1}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLOURS[i % COLOURS.length]} stroke="#1b1f2b"/>
          ))}
        </Pie>
        <Tooltip contentStyle={{ background: "#1b1f2b", border: "1px solid #2a2f3c", fontSize: 12 }}/>
        <Legend wrapperStyle={{ fontSize: 11 }} verticalAlign="middle" align="right" layout="vertical"/>
      </PieChart>
    </ResponsiveContainer>
  );
}

export function moneyFmt(v: number) {
  if (typeof v !== "number") return String(v);
  if (Math.abs(v) >= 1e6) return `$${(v/1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v/1e3).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}
