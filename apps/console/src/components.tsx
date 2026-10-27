import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import type { EChartsCoreOption } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useId, useRef, useState } from "react";
import { ApiError } from "./api/client";

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  SVGRenderer,
]);

/** Decorative identity derived from the ID, never an agent capability or status. */
export function AgentIdentity({ id }: { id: string }) {
  let hash = 2166136261;
  for (const character of id) {
    hash = Math.imul(hash ^ character.charCodeAt(0), 16777619) >>> 0;
  }
  const cells = Array.from({ length: 15 }, (_, index) => {
    const x = index % 3;
    const y = Math.floor(index / 3);
    return (hash >>> index) & 1 ? (
      <g key={index}>
        <rect x={x * 4 + 3} y={y * 4 + 3} width="3" height="3" />
        {x < 2 && (
          <rect x={(4 - x) * 4 + 3} y={y * 4 + 3} width="3" height="3" />
        )}
      </g>
    ) : null;
  });
  return (
    <span className="agent-identity">
      <svg viewBox="0 0 25 25" aria-hidden="true" focusable="false">
        {cells}
      </svg>
      <span>{id}</span>
    </span>
  );
}

export function State({
  query,
  empty,
  children,
}: {
  query: any;
  empty?: boolean;
  children: React.ReactNode;
}) {
  if (query.isPending)
    return (
      <div className="skeleton" aria-label="Loading data">
        <span />
        <span />
        <span />
      </div>
    );
  if (query.error) {
    const error = query.error as ApiError;
    return (
      <div className="state state-error" role="alert">
        <strong>
          {error.status === 403 ? "Access forbidden" : "Data unavailable"}
        </strong>
        <p>{error.message}</p>
        {error.requestId && <code>Request {error.requestId}</code>}
        {error.retryable && (
          <button onClick={() => query.refetch()}>Retry</button>
        )}
      </div>
    );
  }
  if (empty)
    return (
      <div className="state">
        <strong>No records in this window</strong>
        <p>Change the UTC window or filters.</p>
      </div>
    );
  return <>{children}</>;
}

export function Badge({ value }: { value: string }) {
  const normalized = value.toUpperCase();
  const tones: Record<string, string> = {
    CRITICAL: "critical",
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
    ALLOW: "good",
    HEALTHY: "good",
    READY: "good",
    AVAILABLE: "good",
    SIGNED: "good",
    PRESENT: "good",
    BLOCK: "bad",
    DENY: "bad",
    FAILED: "bad",
    UNAVAILABLE: "bad",
    UNSIGNED: "bad",
    ABSENT: "bad",
    "WOULD-BLOCK": "warn",
    WOULD_BLOCK: "warn",
    REQUIRE_APPROVAL: "warn",
    DEGRADED: "warn",
    STALE: "warn",
    UNKNOWN: "warn",
  };
  const tone = tones[normalized] ?? "neutral";
  return (
    <span className={`badge badge-${tone}`}>{value.replaceAll("_", " ")}</span>
  );
}

export function Metric({
  label,
  value,
  unit,
  note,
  tone = "neutral",
  series,
}: {
  label: string;
  value?: number | null;
  unit?: string;
  note?: string;
  tone?: "neutral" | "good" | "warn" | "bad" | "blue";
  series?: number[];
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>
        {value == null
          ? "Unavailable"
          : `${value.toLocaleString()}${unit ?? ""}`}
      </strong>
      {note && <small>{note}</small>}
      {series && series.length > 1 && (
        <Sparkline values={series} tone={tone} label={`${label} trend`} />
      )}
    </div>
  );
}

export function Sparkline({
  values,
  tone = "blue",
  label,
}: {
  values: number[];
  tone?: "neutral" | "good" | "warn" | "bad" | "blue";
  label: string;
}) {
  const gradientId = useId().replaceAll(":", "");
  const width = 128;
  const height = 34;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - 3 - ((value - min) / range) * (height - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `0,${height} ${points} ${width},${height}`;
  return (
    <svg
      className={`sparkline sparkline-${tone}`}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.58" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.03" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gradientId})`} />
      <polyline points={points} />
    </svg>
  );
}

export function Delta({
  change,
  goodWhenUp = true,
  neutralTone,
}: {
  change?: number | null;
  goodWhenUp?: boolean;
  neutralTone?: "good" | "bad" | "warn";
}) {
  if (change == null || !Number.isFinite(change))
    return <span className="delta delta-neutral">No trend</span>;
  const rounded =
    Math.abs(change) >= 100 ? Math.round(change) : Math.round(change * 10) / 10;
  if (rounded === 0)
    return <span className="delta delta-neutral">No change</span>;
  const up = rounded > 0;
  const good = goodWhenUp ? up : !up;
  const tone = neutralTone ?? (good ? "good" : "bad");
  return (
    <span className={`delta delta-${tone}`}>
      {up ? "↑" : "↓"} {Math.abs(rounded).toLocaleString()}%
    </span>
  );
}

export function Panel({
  title,
  description,
  children,
  wide = false,
  tools,
  className = "",
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  wide?: boolean;
  tools?: React.ReactNode;
  className?: string;
}) {
  const classes = ["panel", wide && "panel-wide", className]
    .filter(Boolean)
    .join(" ");
  return (
    <section className={classes}>
      <header>
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {tools && <div className="panel-tools">{tools}</div>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function DataTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div
      className="table-scroll"
      role="region"
      aria-label={`${caption} scroll area`}
      tabIndex={0}
    >
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Chart({
  option,
  label,
  table,
  small = false,
}: {
  option: EChartsCoreOption;
  label: string;
  table: React.ReactNode;
  small?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [showTable, setShowTable] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption({
      backgroundColor: "transparent",
      color: ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#f97316"],
      textStyle: {
        color: "#93a0b4",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      ...option,
      tooltip: {
        backgroundColor: "#0d1219",
        borderColor: "#1a2231",
        textStyle: { color: "#e7ecf3", fontSize: 11 },
        ...((option as { tooltip?: object }).tooltip ?? {}),
      },
    });
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(ref.current);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  }, [option]);
  return (
    <div>
      <div
        ref={ref}
        className={`chart${small ? " chart-sm" : ""}`}
        role="img"
        aria-label={label}
      />
      <button
        className="table-toggle"
        aria-expanded={showTable}
        onClick={() => setShowTable((value) => !value)}
      >
        {showTable ? "Hide" : "Show"} data table
      </button>
      {showTable && table}
    </div>
  );
}

export const formatTime = (value?: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "UTC",
      }).format(new Date(value))
    : "Unavailable";
export const json = (value: unknown) => (
  <pre>{value == null ? "Unavailable" : JSON.stringify(value, null, 2)}</pre>
);
