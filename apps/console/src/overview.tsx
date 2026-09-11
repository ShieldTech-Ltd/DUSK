import { Link } from "@tanstack/react-router";
import type { EChartsCoreOption } from "echarts/core";
import {
  Activity,
  Bot,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Hand,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { capabilitiesFor, useAuth } from "./auth";
import {
  AgentIdentity,
  Badge,
  Chart,
  DataTable,
  Delta,
  Sparkline,
  State,
} from "./components";
import { useApiQuery } from "./hooks";
import { loadConfig } from "./config";
import { useOverviewMasonry } from "./masonry";
import { useWindowRange } from "./window";

const verdictColour: Record<string, string> = {
  ALLOW: "#22c55e",
  "WOULD-BLOCK": "#eab308",
  BLOCK: "#ef4444",
};
const axisLabel = { color: "#64748b", fontSize: 10 };
const axisLine = { lineStyle: { color: "#1a2231" } };
const splitLine = { lineStyle: { color: "#16202b" } };

function compact(value: number | null | undefined) {
  if (value == null) return "Unavailable";
  return Intl.NumberFormat("en-GB", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function shortTime(value?: string | null) {
  if (!value) return "Unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
    hour12: false,
  }).format(new Date(value));
}

function bucketLabel(value?: string | null, granularity?: string) {
  if (!value) return "";
  return granularity === "day"
    ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        timeZone: "UTC",
      }).format(new Date(value))
    : shortTime(value).slice(0, 5);
}

function trend(value?: { change_percent?: number | null }) {
  const change = value?.change_percent;
  if (change == null) return "No comparison data";
  const direction =
    change > 0 ? "Increased" : change < 0 ? "Decreased" : "Unchanged";
  return change === 0
    ? `${direction} from previous window`
    : `${direction} ${Math.abs(change).toFixed(1)}% from previous window`;
}

function riskTone(score: number) {
  return score >= 70 ? "bad" : score >= 40 ? "warn" : "good";
}

function statusTone(status?: string) {
  return status === "healthy" || status === "ready"
    ? "good"
    : status === "degraded" || status === "stale"
      ? "warn"
      : status
        ? "bad"
        : "";
}

function RiskCell({ score }: { score: number }) {
  const tone = riskTone(score);
  return (
    <span>
      <span className={`risk-num tone-${tone}`}>{score}</span>
      <span className="riskbar" aria-hidden="true">
        <i
          style={{
            width: `${Math.min(100, Math.max(4, score))}%`,
            background: `var(--${tone === "bad" ? "red" : tone === "warn" ? "yellow" : "green"})`,
          }}
        />
      </span>
    </span>
  );
}

function Kpi({
  label,
  value,
  detail,
  colour,
  icon: Icon,
  series,
  sparkTone,
  change,
  goodWhenUp,
  neutralTone,
}: {
  label: string;
  value: string;
  detail: string;
  colour: "blue" | "green" | "yellow" | "red";
  icon: typeof Activity;
  series?: number[];
  sparkTone?: "good" | "warn" | "bad" | "blue";
  change?: number | null;
  goodWhenUp?: boolean;
  neutralTone?: "good" | "bad" | "warn";
}) {
  return (
    <article className={`kpi kpi-${colour}`}>
      <div className="kpi-top">
        <span className="kpi-ico">
          <Icon aria-hidden="true" />
        </span>
        <span className="kpi-label">{label}</span>
        <Delta
          change={change}
          goodWhenUp={goodWhenUp}
          neutralTone={neutralTone}
        />
      </div>
      <strong>{value}</strong>
      {series && series.length > 1 && (
        <Sparkline values={series} tone={sparkTone} label={`${label} trend`} />
      )}
      <small className="digest">{detail}</small>
    </article>
  );
}

export function OverviewPage() {
  useOverviewMasonry();
  const capabilities = capabilitiesFor(useAuth().roles);
  const [environment, setEnvironment] = useState("Environment unavailable");
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    void loadConfig().then((config) => setEnvironment(config.environmentLabel));
    const timer = setInterval(() => setNow(new Date()), 1_000);
    return () => clearInterval(timer);
  }, []);
  const { range } = useWindowRange();
  const windowOptions = { params: { query: { window: range } } };
  const summary = useApiQuery(
    ["summary", range],
    "/v2/dashboard/summary",
    windowOptions,
  );
  const volume = useApiQuery(
    ["volume", range],
    "/v2/dashboard/decision-volume",
    windowOptions,
  );
  const breakdown = useApiQuery(
    ["breakdown", range],
    "/v2/dashboard/action-breakdown",
    windowOptions,
  );
  const [feedVerdict, setFeedVerdict] = useState("");
  const decisions = useApiQuery(
    ["ops-decisions", feedVerdict],
    "/v2/decisions",
    {
      params: {
        query: {
          limit: 8,
          verdict: (feedVerdict || undefined) as
            | "ALLOW"
            | "WOULD-BLOCK"
            | "BLOCK"
            | undefined,
        },
      },
    },
  );
  const agents = useApiQuery(
    ["ops-agents", range],
    "/v2/agents/risk",
    { params: { query: { window: range, limit: 6 } } },
    capabilities.agents,
  );
  const service = useApiQuery(
    ["ops-service"],
    "/v2/service/status",
    undefined,
    capabilities.integrations,
  );
  const audit = useApiQuery(
    ["ops-audit"],
    "/v2/audit-events",
    { params: { query: { limit: 6 } } },
    capabilities.audit,
  );

  const data = summary.data as any;
  const volumeData = volume.data as any;
  const points = useMemo(() => volumeData?.points ?? [], [volumeData]);
  const granularity = volumeData?.bucket_granularity as string | undefined;
  const actionItems = useMemo(
    () => (breakdown.data as any)?.items ?? [],
    [breakdown.data],
  );
  const decisionItems = useMemo(
    () => ((decisions.data as any)?.items ?? []) as any[],
    [decisions.data],
  );
  const agentItems = ((agents.data as any)?.items ?? []) as any[];
  const serviceData = service.data as any;
  const components = useMemo(
    () => ((service.data as any)?.components ?? []) as any[],
    [service.data],
  );
  const auditItems = ((audit.data as any)?.items ?? []) as any[];
  const decisionsByTrace = useMemo(
    () => new Map(decisionItems.map((item) => [item.trace_id, item])),
    [decisionItems],
  );

  const flowOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: {
        top: 0,
        right: 4,
        itemWidth: 9,
        itemHeight: 9,
        textStyle: { color: "#93a0b4", fontSize: 10 },
      },
      grid: { left: 38, right: 10, top: 30, bottom: 24 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((point: any) =>
          bucketLabel(point.bucket_start, granularity),
        ),
        axisLabel,
        axisLine,
        axisTick: { show: false },
      },
      yAxis: { type: "value", minInterval: 1, axisLabel, splitLine },
      series: [
        {
          name: "Allowed",
          key: "allow",
          colors: ["#22d3ee", "#2dd4bf", "#22c55e"],
        },
        {
          name: "Would block",
          key: "would_block",
          colors: ["#fb923c", "#facc15", "#bef264"],
        },
        {
          name: "Blocked",
          key: "block",
          colors: ["#93c5fd", "#c084fc", "#f43f8e"],
        },
      ].map((series) => ({
        name: series.name,
        type: "line",
        smooth: 0.35,
        smoothMonotone: "x",
        showSymbol: points.length === 1,
        symbol: "circle",
        symbolSize: 6,
        itemStyle: { color: series.colors[2] },
        areaStyle: {
          opacity: 1,
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${series.colors[2]}80` },
              { offset: 0.55, color: `${series.colors[1]}28` },
              { offset: 1, color: `${series.colors[0]}00` },
            ],
          },
        },
        lineStyle: {
          width: 3,
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: series.colors.map((color, index) => ({
              offset: index / 2,
              color,
            })),
          },
        },
        emphasis: { focus: "series" },
        data: points.map((point: any) => point[series.key]),
      })),
    }),
    [points, granularity],
  );

  const distributionOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: {
        top: 0,
        right: 4,
        itemWidth: 9,
        itemHeight: 9,
        textStyle: { color: "#93a0b4", fontSize: 10 },
      },
      grid: { left: 34, right: 8, top: 30, bottom: 24 },
      xAxis: {
        type: "category",
        data: points.map((point: any) =>
          bucketLabel(point.bucket_start, granularity),
        ),
        axisLabel,
        axisLine,
        axisTick: { show: false },
      },
      yAxis: { type: "value", minInterval: 1, axisLabel, splitLine },
      series: [
        {
          name: "Allowed",
          type: "bar",
          stack: "verdicts",
          color: verdictColour.ALLOW,
          barMaxWidth: 15,
          data: points.map((point: any) => point.allow),
        },
        {
          name: "Would block",
          type: "bar",
          stack: "verdicts",
          color: verdictColour["WOULD-BLOCK"],
          barMaxWidth: 15,
          data: points.map((point: any) => point.would_block),
        },
        {
          name: "Blocked",
          type: "bar",
          stack: "verdicts",
          color: verdictColour.BLOCK,
          barMaxWidth: 15,
          data: points.map((point: any) => point.block),
        },
      ],
    }),
    [points, granularity],
  );

  const actionOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: any) => {
          const first = Array.isArray(params) ? params[0] : params;
          const item = actionItems[first.dataIndex];
          return `${first.name}: ${first.value} (${item?.share_percent ?? 0}%)`;
        },
      },
      grid: { left: 4, right: 34, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        inverse: true,
        data: actionItems.map((item: any) =>
          item.action_type.replaceAll("_", " "),
        ),
        axisLabel: {
          color: "#93a0b4",
          fontSize: 10,
          width: 96,
          overflow: "truncate",
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          barWidth: 9,
          data: actionItems.map((item: any, index: number) => ({
            value: item.decision_count,
            itemStyle: {
              color: [
                "#60a5fa",
                "#a78bfa",
                "#22d3ee",
                "#f472b6",
                "#fb923c",
                "#2dd4bf",
              ][index % 6],
            },
          })),
          itemStyle: { borderRadius: [0, 5, 5, 0] },
          label: {
            show: true,
            position: "right",
            color: "#93a0b4",
            fontSize: 10,
          },
        },
      ],
    }),
    [actionItems],
  );

  const latencyOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value: any) => `${value ?? 0} ms`,
      },
      grid: { left: 4, right: 40, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", show: false },
      yAxis: {
        type: "category",
        inverse: true,
        data: components.map((item: any) => item.name),
        axisLabel: { color: "#93a0b4", fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          barWidth: 8,
          data: components.map((item: any) => item.latency_ms ?? 0),
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: (params: any) =>
              components[params.dataIndex]?.status === "healthy"
                ? "#22c55e"
                : components[params.dataIndex]?.status === "degraded"
                  ? "#eab308"
                  : "#ef4444",
          },
          label: {
            show: true,
            position: "right",
            color: "#64748b",
            fontSize: 9.5,
            formatter: (params: any) =>
              components[params.dataIndex]?.latency_ms == null
                ? "unmeasured"
                : `${params.value} ms`,
          },
        },
      ],
    }),
    [components],
  );

  const policyOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 30, right: 8, top: 12, bottom: 22 },
      xAxis: {
        type: "category",
        data: points.map((point: any) =>
          bucketLabel(point.bucket_start, granularity),
        ),
        axisLabel: { ...axisLabel, fontSize: 9 },
        axisLine,
        axisTick: { show: false },
      },
      yAxis: { type: "value", minInterval: 1, axisLabel, splitLine },
      series: [
        {
          type: "bar",
          barMaxWidth: 12,
          data: points.map((point: any) => point.total),
          itemStyle: { color: "#f97316", borderRadius: [3, 3, 0, 0] },
        },
      ],
    }),
    [points, granularity],
  );

  const feedTabs = [
    ["", "All"],
    ["BLOCK", "Blocked"],
    ["WOULD-BLOCK", "Would block"],
    ["ALLOW", "Allowed"],
  ] as const;

  return (
    <div className="ops">
      <header className="overview-heading">
        <div>
          <h1>Security Operations</h1>
          <p>Monitor, evaluate, and control AI agent actions in real time.</p>
        </div>
      </header>

      <section className="status-strip" aria-label="Console status">
        <article>
          <span className="status-icon status-blue">
            <Activity />
          </span>
          <div>
            <small>Environment</small>
            <strong>{environment}</strong>
            <p>Tenant isolated</p>
          </div>
        </article>
        <article>
          <span className="status-icon status-blue">
            <BookOpen />
          </span>
          <div>
            <small>Console</small>
            <strong className="tone-warn">Read only</strong>
            <p>No mutation controls</p>
          </div>
        </article>
        <article>
          <span
            className={`status-icon status-${statusTone(serviceData?.status) || "blue"}`}
          >
            <CircleAlert />
          </span>
          <div>
            <small>Measured status</small>
            <strong className={`tone-${statusTone(serviceData?.status)}`}>
              {serviceData?.status
                ? serviceData.status[0].toUpperCase() +
                  serviceData.status.slice(1)
                : "Unavailable"}
            </strong>
            <p>{components.length} measured components</p>
          </div>
        </article>
        <article>
          <span className="status-icon status-blue">
            <Clock3 />
          </span>
          <div>
            <small>UTC</small>
            <strong>
              {new Intl.DateTimeFormat("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                timeZone: "UTC",
                hour12: false,
              }).format(now)}
            </strong>
            <p>
              {new Intl.DateTimeFormat("en-GB", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                timeZone: "UTC",
              }).format(now)}
            </p>
          </div>
        </article>
      </section>

      <State query={summary} empty={data?.decisions?.value === 0}>
        <div className="kpi-row">
          <Kpi
            icon={Activity}
            label="Total decisions"
            colour="blue"
            value={compact(data?.decisions?.value)}
            detail={trend(data?.decisions)}
            series={points.map((point: any) => point.total)}
            sparkTone="blue"
            change={data?.decisions?.change_percent}
            goodWhenUp
          />
          <Kpi
            icon={CheckCircle2}
            label="Allowed"
            colour="green"
            value={compact(data?.allowed?.value)}
            detail={trend(data?.allowed)}
            series={points.map((point: any) => point.allow)}
            sparkTone="good"
            change={data?.allowed?.change_percent}
            goodWhenUp
          />
          <Kpi
            icon={CircleAlert}
            label="Would block"
            colour="yellow"
            value={compact(data?.would_block?.value)}
            detail={trend(data?.would_block)}
            series={points.map((point: any) => point.would_block)}
            sparkTone="warn"
            change={data?.would_block?.change_percent}
            neutralTone="warn"
          />
          <Kpi
            icon={Hand}
            label="Blocked"
            colour="red"
            value={compact(data?.blocked?.value)}
            detail={trend(data?.blocked)}
            series={points.map((point: any) => point.block)}
            sparkTone="bad"
            change={data?.blocked?.change_percent}
            goodWhenUp={false}
          />
          <Kpi
            icon={Bot}
            label="High-risk decisions"
            colour="red"
            value={compact(data?.high_risk_decisions?.value)}
            detail={trend(data?.high_risk_decisions)}
            change={data?.high_risk_decisions?.change_percent}
            goodWhenUp={false}
          />
          <Kpi
            icon={Clock3}
            label="P95 gate latency"
            colour="blue"
            value={
              data?.evaluation_latency?.p95_ms == null
                ? "Unavailable"
                : `${Math.round(data.evaluation_latency.p95_ms)} ms`
            }
            detail={`${data?.evaluation_latency?.sample_count ?? 0} measured evaluations`}
          />
        </div>
      </State>

      <div className="dashboard-masonry">
        <section className="panel span-flow gradient-flow-panel">
          <header>
            <div>
              <h2>Decision flow over time</h2>
              <p>
                Verdict counts per UTC bucket. Curves connect recorded values.
              </p>
            </div>
          </header>
          <div className="panel-body">
            <State query={volume} empty={!points.length}>
              <Chart
                label="Decision flow over time"
                option={flowOption}
                table={
                  <DataTable
                    caption="Decision flow data"
                    columns={[
                      "UTC bucket",
                      "Allowed",
                      "Would block",
                      "Blocked",
                      "Total",
                    ]}
                    rows={points.map((point: any) => [
                      bucketLabel(point.bucket_start, granularity),
                      point.allow,
                      point.would_block,
                      point.block,
                      point.total,
                    ])}
                  />
                }
              />
            </State>
          </div>
        </section>
        <section className="panel span-dist">
          <header>
            <div>
              <h2>Decision distribution</h2>
              <p>Verdict mix in window</p>
            </div>
          </header>
          <div className="panel-body">
            <State query={volume} empty={!points.length}>
              <Chart
                label="Verdict distribution by UTC bucket"
                option={distributionOption}
                table={
                  <DataTable
                    caption="Decision distribution data"
                    columns={[
                      "UTC bucket",
                      "Allowed",
                      "Would block",
                      "Blocked",
                    ]}
                    rows={points.map((point: any) => [
                      bucketLabel(point.bucket_start, granularity),
                      point.allow,
                      point.would_block,
                      point.block,
                    ])}
                  />
                }
              />
            </State>
          </div>
        </section>
        <section className="panel span-actions">
          <header>
            <div>
              <h2>Action types</h2>
              <p>Decisions by canonical action</p>
            </div>
          </header>
          <div className="panel-body">
            <State query={breakdown} empty={!actionItems.length}>
              <Chart
                label="Decisions by action type"
                option={actionOption}
                table={
                  <DataTable
                    caption="Action breakdown data"
                    columns={["Action", "Decisions", "Share"]}
                    rows={actionItems.map((item: any) => [
                      item.action_type,
                      item.decision_count,
                      `${item.share_percent}%`,
                    ])}
                  />
                }
              />
            </State>
          </div>
        </section>
        <section className="panel span-feed">
          <header>
            <div>
              <h2>Live decision feed</h2>
              <p>Persisted evaluations, newest first</p>
            </div>
            <Link className="panel-link" to="/decisions">
              View all <ChevronRight aria-hidden="true" size={13} />
            </Link>
          </header>
          <div className="panel-body">
            <div
              className="tabs"
              role="group"
              aria-label="Filter feed by verdict"
            >
              {feedTabs.map(([value, label]) => (
                <button
                  key={value || "all"}
                  aria-pressed={feedVerdict === value}
                  onClick={() => setFeedVerdict(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <State query={decisions} empty={!decisionItems.length}>
              <DataTable
                caption="Live persisted decisions"
                columns={[
                  "Time (UTC)",
                  "Agent",
                  "Action",
                  "Risk",
                  "Blast radius",
                  "Verdict",
                  "",
                ]}
                rows={decisionItems.map((item: any) => [
                  <span className="mono">{shortTime(item.created_at)}</span>,
                  item.agent_id,
                  item.action_type?.replaceAll("_", " ") ?? "Unavailable",
                  <RiskCell score={Math.round(item.behavioral_score * 100)} />,
                  <Badge value={item.blast_radius} />,
                  <Badge value={item.verdict} />,
                  item.detail_available && capabilities.decisionDetail ? (
                    <span className="row-go">
                      <Link
                        to="/decisions/$traceId"
                        params={{ traceId: item.trace_id }}
                        aria-label={`Open decision ${item.trace_id}`}
                      >
                        <ChevronRight aria-hidden="true" size={14} />
                      </Link>
                    </span>
                  ) : (
                    <span className="row-go" aria-hidden="true">
                      –
                    </span>
                  ),
                ])}
              />
            </State>
          </div>
        </section>
        {capabilities.agents && (
          <section className="panel span-agents">
            <header>
              <div>
                <h2>High-risk agents</h2>
                <p>Ranked by behavioural risk score</p>
              </div>
              <Link className="panel-link" to="/agents">
                View all <ChevronRight aria-hidden="true" size={13} />
              </Link>
            </header>
            <div className="panel-body">
              <State query={agents} empty={!agentItems.length}>
                <DataTable
                  caption="High-risk agents"
                  columns={["Agent", "Risk", "Blocked", "Last seen", ""]}
                  rows={agentItems.map((item: any) => [
                    <Link
                      to="/agents/$agentId"
                      params={{ agentId: item.agent_id }}
                    >
                      <AgentIdentity id={item.agent_id} />
                    </Link>,
                    <RiskCell score={Math.round(item.risk_score * 100)} />,
                    item.block_count + item.would_block_count,
                    <span className="mono">
                      {shortTime(item.last_seen_at)}
                    </span>,
                    <span className="row-go">
                      <Link
                        to="/agents/$agentId"
                        params={{ agentId: item.agent_id }}
                        aria-label={`Open agent ${item.agent_id}`}
                      >
                        <ChevronRight aria-hidden="true" size={14} />
                      </Link>
                    </span>,
                  ])}
                />
              </State>
            </div>
          </section>
        )}
        {capabilities.agents && (
          <section className="panel span-geo">
            <header>
              <div>
                <h2>Source activity</h2>
                <p>Observed agents by decision volume</p>
              </div>
            </header>
            <div className="panel-body">
              <State query={agents} empty={!agentItems.length}>
                <ul className="source-list">
                  {agentItems.slice(0, 4).map((item: any) => (
                    <li key={item.agent_id}>
                      <span className="source-name mono">{item.agent_id}</span>
                      <span className="source-track" aria-hidden="true">
                        <i
                          style={{
                            width: `${Math.max(
                              8,
                              (item.decision_count /
                                Math.max(
                                  ...agentItems.map(
                                    (agent: any) => agent.decision_count,
                                  ),
                                  1,
                                )) *
                                100,
                            )}%`,
                          }}
                        />
                      </span>
                      <strong>{item.decision_count}</strong>
                    </li>
                  ))}
                </ul>
                <p className="source-note">
                  Location data is not collected by the current API.
                </p>
              </State>
            </div>
          </section>
        )}
        {capabilities.audit && (
          <section className="panel span-feed">
            <header>
              <div>
                <h2>Recent audit receipts</h2>
                <p>Hash-chained evidence of each decision</p>
              </div>
              <Link className="panel-link" to="/audit">
                View all <ChevronRight aria-hidden="true" size={13} />
              </Link>
            </header>
            <div className="panel-body">
              <State query={audit} empty={!auditItems.length}>
                <DataTable
                  caption="Recent audit receipts"
                  columns={[
                    "Time",
                    "Event",
                    "Agent",
                    "Verdict",
                    "Signature",
                    "Receipt ID",
                    "",
                  ]}
                  rows={auditItems.map((item: any) => {
                    const decision = item.trace_id
                      ? decisionsByTrace.get(item.trace_id)
                      : undefined;
                    return [
                      <span className="mono">
                        {shortTime(item.occurred_at)}
                      </span>,
                      item.event_type?.replaceAll("_", " ") ?? "Unavailable",
                      decision?.agent_id ?? "Unavailable",
                      decision ? (
                        <Badge value={decision.verdict} />
                      ) : (
                        "Unavailable"
                      ),
                      <Badge
                        value={item.signature_present ? "SIGNED" : "UNSIGNED"}
                      />,
                      item.digest ? (
                        <Link className="mono" to="/audit">
                          #rcpt_{item.digest.slice(0, 7)}
                        </Link>
                      ) : (
                        <span className="mono digest">No digest</span>
                      ),
                      <span className="row-go">
                        <Link to="/audit" aria-label="Open audit trail">
                          <ChevronRight aria-hidden="true" size={14} />
                        </Link>
                      </span>,
                    ];
                  })}
                />
              </State>
            </div>
          </section>
        )}
        {capabilities.integrations && (
          <section className="panel span-agents">
            <header>
              <div>
                <h2>Gate latency</h2>
                <p>Measured component response times</p>
              </div>
            </header>
            <div className="panel-body">
              <State query={service} empty={!components.length}>
                <div className="latency-grid">
                  <Chart
                    small
                    label="Measured latency by service component"
                    option={latencyOption}
                    table={
                      <DataTable
                        caption="Service component latency"
                        columns={["Component", "Status", "Latency"]}
                        rows={components.map((item: any) => [
                          item.name,
                          <Badge value={item.status} />,
                          item.latency_ms == null
                            ? "Unmeasured"
                            : `${item.latency_ms} ms`,
                        ])}
                      />
                    }
                  />
                  <div className="latency-stats">
                    <div>
                      <small>P95 GATE</small>
                      <strong>
                        {data?.evaluation_latency?.p95_ms == null
                          ? "–"
                          : `${Math.round(data.evaluation_latency.p95_ms)} ms`}
                      </strong>
                      <span>
                        {data?.evaluation_latency?.sample_count ?? 0} samples
                      </span>
                    </div>
                    <div>
                      <small>STATUS</small>
                      <strong>
                        <Badge value={serviceData?.status ?? "unavailable"} />
                      </strong>
                      <span>
                        Measured {shortTime(serviceData?.measured_at)} UTC
                      </span>
                    </div>
                  </div>
                </div>
              </State>
            </div>
          </section>
        )}
        <section className="panel span-geo">
          <header>
            <div>
              <h2>Policy activity</h2>
              <p>Decisions evaluated per bucket</p>
            </div>
          </header>
          <div className="panel-body">
            <State query={volume} empty={!points.length}>
              <Chart
                small
                label="Policy activity by bucket"
                option={policyOption}
                table={
                  <DataTable
                    caption="Policy activity data"
                    columns={["UTC bucket", "Total decisions"]}
                    rows={points.map((point: any) => [
                      bucketLabel(point.bucket_start, granularity),
                      point.total,
                    ])}
                  />
                }
              />
            </State>
          </div>
        </section>
      </div>

      <footer className="ops-footer">
        All times UTC | Read-only console | Evidence is labelled at source
      </footer>
    </div>
  );
}
