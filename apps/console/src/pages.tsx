import { Link, useNavigate, useParams } from "@tanstack/react-router";
import type { EChartsCoreOption } from "echarts/core";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { backendSurfaces } from "./backend-surfaces";
import { DuskMark } from "./brand";
import {
  AgentIdentity,
  Badge,
  Chart,
  DataTable,
  Metric,
  Panel,
  State,
  formatTime,
  json,
} from "./components";
export { OverviewPage } from "./overview";
import { landingFor, useAuth } from "./auth";
import { useApiQuery, useCursorPagination } from "./hooks";
import { useWindowRange, type WindowValue } from "./window";

const chartColours = {
  blue: "#3b82f6",
  green: "#22c55e",
  amber: "#eab308",
  red: "#ef4444",
  grid: "#16202b",
  text: "#93a0b4",
  panel: "#0a0e15",
} as const;

function shortUtc(value?: string | null) {
  if (!value) return "Unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  }).format(new Date(value));
}

function PageHeader({
  title,
  description,
  controls,
}: {
  title: string;
  description: string;
  controls?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {controls}
    </div>
  );
}

function useWindow() {
  const { range, setRange } = useWindowRange();
  return [range, setRange] as const;
}

function WindowControl({
  value,
  onChange,
  refreshing,
  refresh,
  updatedAt,
}: {
  value: string;
  onChange: (value: WindowValue) => void;
  refreshing: boolean;
  refresh: () => void;
  updatedAt?: number;
}) {
  return (
    <div className="controls">
      <label>
        UTC window
        <select
          value={value}
          onChange={(event) => onChange(event.target.value as WindowValue)}
        >
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
        </select>
      </label>
      <button onClick={refresh} disabled={refreshing}>
        <RefreshCw className={refreshing ? "spin" : ""} />
        Refresh
      </button>
      <span className="freshness" role="status">
        {updatedAt
          ? `Updated ${formatTime(new Date(updatedAt).toISOString())}`
          : "Awaiting data"}
      </span>
    </div>
  );
}

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [signInError, setSignInError] = useState(false);
  useEffect(() => {
    if (auth.user) void navigate({ to: landingFor(auth.roles) });
  }, [auth.user, auth.roles, navigate]);
  return (
    <main className="login">
      <section className="login-context" aria-labelledby="login-heading">
        <div className="login-brand">
          <span className="login-logo-crop" aria-hidden="true">
            <DuskMark />
          </span>
          <span>Security Operations</span>
        </div>
        <div className="login-message">
          <div className="login-kicker">
            <span className="dot dot-good" />
            Policy enforcement and investigation
          </div>
          <h1 id="login-heading">
            Control agent actions before they become incidents.
          </h1>
          <p>
            Inspect policy decisions, behavioral risk, evidence quality, and
            cryptographic audit continuity from one tenant-isolated console.
          </p>
        </div>
        <div className="login-capabilities" aria-label="Platform safeguards">
          <div>
            <ShieldCheck aria-hidden="true" />
            <span>
              <strong>Read-only console</strong>
              <small>No production mutation controls</small>
            </span>
          </div>
          <div>
            <KeyRound aria-hidden="true" />
            <span>
              <strong>Claim-bound access</strong>
              <small>Tenant and role from validated identity</small>
            </span>
          </div>
          <div>
            <LockKeyhole aria-hidden="true" />
            <span>
              <strong>Protected session</strong>
              <small>Authorization Code with PKCE</small>
            </span>
          </div>
        </div>
        <footer>Decision intelligence for autonomous infrastructure</footer>
      </section>
      <section className="login-access" aria-label="Secure sign in">
        <div className="login-panel">
          <div className="login-panel-icon">
            <LockKeyhole aria-hidden="true" />
          </div>
          <span>Secure console access</span>
          <h2>Sign in to DUSK</h2>
          <p>
            Continue through your organization&apos;s identity provider. DUSK
            applies tenant and capability boundaries from validated claims.
          </p>
          {signInError && (
            <div className="login-error" role="alert">
              Sign-in could not start. Check the identity service and try again.
            </div>
          )}
          <button
            className="login-submit"
            disabled={submitting}
            onClick={() => {
              setSubmitting(true);
              setSignInError(false);
              void auth.signIn().catch(() => {
                setSubmitting(false);
                setSignInError(true);
              });
            }}
          >
            {submitting ? "Opening identity provider" : "Continue securely"}
            <ArrowRight aria-hidden="true" />
          </button>
          <div className="login-session-note">
            <CheckCircle2 aria-hidden="true" />
            <span>
              Access tokens remain in memory. Only transient authorization state
              is stored for this browser session.
            </span>
          </div>
        </div>
        <small className="login-access-footer">
          Authorized users only. Authentication events are auditable.
        </small>
      </section>
    </main>
  );
}

export function CallbackPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const completeSignIn = auth.completeSignIn;
  useEffect(() => {
    void completeSignIn().then((user) => {
      const raw = user.profile.dusk_roles;
      const roles = Array.isArray(raw)
        ? raw.filter((role): role is string => typeof role === "string")
        : typeof raw === "string"
          ? [raw]
          : [];
      return navigate({ to: landingFor(roles) });
    });
  }, [completeSignIn, navigate]);
  return (
    <main className="login">
      <div className="boot">Completing secure sign-in…</div>
    </main>
  );
}

function PageNavigation({
  query,
  previous,
  canPrevious,
  next,
}: {
  query: any;
  previous: () => void;
  canPrevious: boolean;
  next: () => void;
}) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <button disabled={!canPrevious || query.isFetching} onClick={previous}>
        Previous page
      </button>
      <button
        disabled={!query.data?.next_cursor || query.isFetching}
        onClick={next}
      >
        Next page
      </button>
    </nav>
  );
}

export function DecisionsPage() {
  const [windowValue, setWindow] = useWindow();
  const { cursor, setCursor, previous, canPrevious } = useCursorPagination();
  const [verdict, setVerdict] = useState(
    new URLSearchParams(location.search).get("verdict") ?? "",
  );
  const query = useApiQuery(["decisions", cursor, verdict], "/v2/decisions", {
    params: { query: { limit: 10, cursor, verdict: verdict || undefined } },
  });
  const summary = useApiQuery(
    ["decision-page-summary", windowValue],
    "/v2/dashboard/summary",
    { params: { query: { window: windowValue } } },
  );
  const volume = useApiQuery(
    ["decision-page-volume", windowValue],
    "/v2/dashboard/decision-volume",
    { params: { query: { window: windowValue } } },
  );
  const items = useMemo(() => (query.data as any)?.items ?? [], [query.data]);
  const summaryData = summary.data as any;
  const volumePoints = useMemo(
    () => (volume.data as any)?.points ?? [],
    [volume.data],
  );
  const volumeOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: {
        top: 8,
        right: 12,
        textStyle: { color: chartColours.text, fontSize: 10 },
      },
      grid: { left: 42, right: 18, top: 42, bottom: 30 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: volumePoints.map((point: any) => shortUtc(point.bucket_start)),
        axisLabel: { color: chartColours.text, fontSize: 9 },
        axisLine: { lineStyle: { color: "#1a2231" } },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: chartColours.text, fontSize: 9 },
        splitLine: {
          lineStyle: { color: chartColours.grid, type: "dashed", opacity: 0.7 },
        },
      },
      series: [
        {
          name: "Allowed",
          type: "line",
          smooth: 0.24,
          symbol: "none",
          lineStyle: { width: 2.2 },
          areaStyle: {
            opacity: 0.22,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(34, 197, 94, 0.52)" },
                { offset: 1, color: "rgba(34, 197, 94, 0.02)" },
              ],
            },
          },
          color: chartColours.green,
          data: volumePoints.map((point: any) => point.allow),
        },
        {
          name: "Would block",
          type: "line",
          smooth: 0.24,
          symbol: "none",
          lineStyle: { width: 2.2 },
          areaStyle: {
            opacity: 0.2,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(234, 179, 8, 0.5)" },
                { offset: 1, color: "rgba(234, 179, 8, 0.02)" },
              ],
            },
          },
          color: chartColours.amber,
          data: volumePoints.map((point: any) => point.would_block),
        },
        {
          name: "Blocked",
          type: "line",
          smooth: 0.24,
          symbol: "none",
          lineStyle: { width: 2.4 },
          areaStyle: {
            opacity: 0.25,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(239, 68, 68, 0.56)" },
                { offset: 1, color: "rgba(239, 68, 68, 0.025)" },
              ],
            },
          },
          color: chartColours.red,
          data: volumePoints.map((point: any) => point.block),
        },
      ],
    }),
    [volumePoints],
  );
  const verdictOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "item" },
      legend: {
        orient: "vertical",
        right: 18,
        top: "middle",
        textStyle: { color: "#93a0b4", fontSize: 10 },
      },
      series: [
        {
          type: "pie",
          radius: ["48%", "72%"],
          center: ["34%", "50%"],
          label: { show: false },
          itemStyle: { borderColor: chartColours.panel, borderWidth: 2 },
          data: [
            {
              name: "Allowed",
              value: summaryData?.allowed?.value ?? 0,
              itemStyle: { color: chartColours.green },
            },
            {
              name: "Would block",
              value: summaryData?.would_block?.value ?? 0,
              itemStyle: { color: chartColours.amber },
            },
            {
              name: "Blocked",
              value: summaryData?.blocked?.value ?? 0,
              itemStyle: { color: chartColours.red },
            },
          ],
        },
      ],
    }),
    [summaryData],
  );
  const applyVerdict = (value: string) => {
    setCursor(undefined);
    setVerdict(value);
    const search = new URLSearchParams();
    if (value) search.set("verdict", value);
    history.replaceState(null, "", `${location.pathname}?${search}`);
  };
  return (
    <>
      <PageHeader
        title="Decisions"
        description="Tenant-scoped decision summaries from a fixed pagination snapshot."
        controls={
          <div className="controls">
            <label>
              UTC window
              <select
                value={windowValue}
                onChange={(event) =>
                  setWindow(event.target.value as WindowValue)
                }
              >
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
            </label>
            <label>
              Verdict
              <select
                value={verdict}
                onChange={(event) => applyVerdict(event.target.value)}
              >
                <option value="">All verdicts</option>
                <option>ALLOW</option>
                <option>WOULD-BLOCK</option>
                <option>BLOCK</option>
              </select>
            </label>
            <button
              onClick={() =>
                void Promise.all([
                  query.refetch(),
                  summary.refetch(),
                  volume.refetch(),
                ])
              }
              disabled={
                query.isFetching || summary.isFetching || volume.isFetching
              }
            >
              <RefreshCw
                className={
                  query.isFetching || summary.isFetching || volume.isFetching
                    ? "spin"
                    : ""
                }
              />
              Refresh
            </button>
          </div>
        }
      />
      <State query={summary}>
        <div className="metrics route-metrics">
          <Metric
            label="Total decisions"
            value={summaryData?.decisions?.value}
            note={`Last ${windowValue === "24h" ? "24 hours" : windowValue === "7d" ? "7 days" : "30 days"}`}
            tone="blue"
            series={volumePoints.map((point: any) => point.total)}
          />
          <Metric
            label="Blocked"
            value={summaryData?.blocked?.value}
            note="Enforced denials"
            tone="bad"
            series={volumePoints.map((point: any) => point.block)}
          />
          <Metric
            label="Would block"
            value={summaryData?.would_block?.value}
            note="Watch-mode findings"
            tone="warn"
            series={volumePoints.map((point: any) => point.would_block)}
          />
          <Metric
            label="Allowed"
            value={summaryData?.allowed?.value}
            note="Policy-approved actions"
            tone="good"
            series={volumePoints.map((point: any) => point.allow)}
          />
          <Metric
            label="P95 latency"
            value={summaryData?.evaluation_latency?.p95_ms}
            unit=" ms"
            note="Evaluation gate"
            tone="blue"
          />
        </div>
      </State>
      <div className="route-grid route-grid-telemetry">
        <Panel title="Decision volume over time">
          <State query={volume} empty={!volumePoints.length}>
            <Chart
              label="Decision volume over time"
              option={volumeOption}
              table={
                <DataTable
                  caption="Decision volume over time data"
                  columns={[
                    "UTC bucket",
                    "Allowed",
                    "Would block",
                    "Blocked",
                    "Total",
                  ]}
                  rows={volumePoints.map((point: any) => [
                    formatTime(point.bucket_start),
                    point.allow,
                    point.would_block,
                    point.block,
                    point.total,
                  ])}
                />
              }
            />
          </State>
        </Panel>
        <Panel title="Enforcement distribution">
          <State query={summary} empty={summaryData?.decisions?.value === 0}>
            <Chart
              label="Decision verdict distribution"
              option={verdictOption}
              table={
                <DataTable
                  caption="Decision verdict distribution data"
                  columns={["Verdict", "Decisions"]}
                  rows={[
                    ["Allowed", summaryData?.allowed?.value],
                    ["Would block", summaryData?.would_block?.value],
                    ["Blocked", summaryData?.blocked?.value],
                  ]}
                />
              }
            />
          </State>
        </Panel>
        <Panel title="Decision ledger" wide>
          <State query={query} empty={!items.length}>
            <DataTable
              caption="Persisted decisions"
              columns={[
                "UTC time",
                "Trace",
                "Agent",
                "Action",
                "Verdict",
                "Risk",
                "Evidence",
              ]}
              rows={items.map((item: any) => [
                formatTime(item.created_at),
                item.detail_available ? (
                  <Link
                    className="mono"
                    to="/decisions/$traceId"
                    params={{ traceId: item.trace_id }}
                  >
                    {item.trace_id}
                  </Link>
                ) : (
                  <span className="mono">{item.trace_id}</span>
                ),
                item.agent_id,
                item.action_type ?? "Unavailable",
                <Badge value={item.verdict} />,
                `${Math.round(item.behavioral_score * 100)}%`,
                item.evidence_degraded == null ? (
                  "Unavailable"
                ) : item.evidence_degraded ? (
                  <Badge value="DEGRADED" />
                ) : (
                  <Badge value="HEALTHY" />
                ),
              ])}
            />
          </State>
          <PageNavigation
            query={query}
            previous={previous}
            canPrevious={canPrevious}
            next={() => setCursor((query.data as any).next_cursor)}
          />
        </Panel>
      </div>
    </>
  );
}

export function DecisionDetailPage() {
  const { traceId } = useParams({ strict: false }) as { traceId: string };
  const query = useApiQuery(["decision", traceId], "/v2/decisions/{trace_id}", {
    params: { path: { trace_id: traceId } },
  });
  const item = query.data as any;
  const timingItems = Object.entries(item?.pipeline_timings ?? {}).filter(
    (entry): entry is [string, number] =>
      typeof entry[1] === "number" &&
      Number.isFinite(entry[1]) &&
      entry[1] >= 0,
  );
  const timingOption: EChartsCoreOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 110, right: 24, top: 16, bottom: 28 },
    xAxis: {
      type: "value",
      axisLabel: { color: chartColours.text, formatter: "{value} ms" },
      splitLine: { lineStyle: { color: chartColours.grid } },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: timingItems.map(([stage]) =>
        stage.replace(/_ms$/, "").replaceAll("_", " "),
      ),
      axisLabel: { color: chartColours.text },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 18,
        data: timingItems.map(([stage, value]) => ({
          value,
          itemStyle: {
            color:
              stage === "total_ms" ? chartColours.amber : chartColours.blue,
          },
        })),
      },
    ],
  };
  return (
    <>
      <PageHeader title="Decision investigation" description={traceId} />
      <State query={query}>
        <div
          className="backend-flow decision-evidence-flow"
          aria-label="Recorded agent action and verdict"
        >
          <div>
            <Bot aria-hidden="true" />
            <strong>Agent</strong>
            <span>{item?.action?.agent_id ?? "Unavailable"}</span>
          </div>
          <ArrowRight aria-hidden="true" />
          <div>
            <strong>Action</strong>
            <span>
              {item?.action?.action_type?.replaceAll("_", " ") ?? "Unavailable"}
            </span>
          </div>
          <ArrowRight aria-hidden="true" />
          <div>
            <strong>Target</strong>
            <span>{item?.action?.target ?? "Unavailable"}</span>
          </div>
          <ArrowRight aria-hidden="true" />
          <div>
            <ShieldCheck aria-hidden="true" />
            <strong>Recorded verdict</strong>
            <Badge value={item?.verdict ?? "Unavailable"} />
          </div>
        </div>
        <div className="metrics">
          <Metric
            label="Risk score"
            value={item ? Math.round(item.behavioral_score * 100) : null}
            unit="%"
          />
          <Metric label="Policy matches" value={item?.policy_matches?.length} />
          <Metric label="Audit sequence" value={item?.audit?.sequence} />
        </div>
        <div className="grid">
          <Panel title="Verdict and lifecycle">
            <dl>
              <dt>Verdict</dt>
              <dd>
                <Badge value={item?.verdict ?? "Unavailable"} />
              </dd>
              <dt>Response status</dt>
              <dd>
                <Badge value={item?.response_status ?? "Unavailable"} />
              </dd>
              <dt>Evidence</dt>
              <dd>
                {item?.evidence_degraded ? (
                  <Badge value="DEGRADED" />
                ) : (
                  <Badge value="HEALTHY" />
                )}
              </dd>
              <dt>Created</dt>
              <dd>{formatTime(item?.created_at)}</dd>
            </dl>
          </Panel>
          <Panel title="Safe canonical action">{json(item?.action)}</Panel>
          <Panel title="Reasons and MITRE mappings">
            {json({
              reasons: item?.reasons,
              mitre_mappings: item?.mitre_mappings,
            })}
          </Panel>
          <Panel title="Policy evidence">
            {json({
              pack: item?.policy_pack_version,
              matches: item?.policy_matches,
            })}
          </Panel>
          <Panel
            title="Decision pipeline"
            description="Recorded durations in milliseconds. Total is the overall duration, not an additional stage."
          >
            {timingItems.length ? (
              <Chart
                label="Decision pipeline timings"
                option={timingOption}
                table={
                  <DataTable
                    caption="Decision pipeline timing data"
                    columns={["Measurement", "Milliseconds"]}
                    rows={timingItems}
                  />
                }
              />
            ) : (
              <div className="state">
                <strong>Timing detail unavailable</strong>
              </div>
            )}
          </Panel>
          <Panel title="Audit continuity">
            <dl>
              <dt>Event</dt>
              <dd>{item?.audit?.event_type}</dd>
              <dt>Digest</dt>
              <dd className="mono wrap">{item?.audit?.digest}</dd>
              <dt>Previous</dt>
              <dd className="mono wrap">
                {item?.audit?.previous_digest ?? "Chain origin"}
              </dd>
            </dl>
          </Panel>
          <Panel title="Similar decisions">
            <DataTable
              caption="Similar decision traces"
              columns={["Trace", "Time UTC", "Verdict", "Action"]}
              rows={(item?.similar_decisions ?? []).map((decision: any) => [
                <Link
                  className="mono"
                  to="/decisions/$traceId"
                  params={{ traceId: decision.trace_id }}
                >
                  {decision.trace_id.slice(0, 12)}
                </Link>,
                formatTime(decision.created_at),
                <Badge value={decision.verdict} />,
                decision.action_type ?? "Unavailable",
              ])}
            />
          </Panel>
        </div>
      </State>
    </>
  );
}

function AgentActivityChart({ items }: { items: any[] }) {
  const visible = items.slice(0, 10);
  return (
    <Chart
      label="Agent activity comparison"
      option={{
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        legend: { top: 0, textStyle: { color: chartColours.text } },
        grid: { left: 120, right: 24, top: 40, bottom: 25 },
        xAxis: {
          type: "value",
          minInterval: 1,
          axisLabel: { color: chartColours.text },
          splitLine: { lineStyle: { color: chartColours.grid } },
        },
        yAxis: {
          type: "category",
          inverse: true,
          data: visible.map((item) => item.agent_id),
          axisLabel: { color: chartColours.text },
        },
        series: [
          { name: "Decisions", key: "decision_count", color: "#22d3ee" },
          { name: "High risk", key: "high_risk_count", color: "#a78bfa" },
          { name: "Blocked", key: "block_count", color: chartColours.red },
        ].map((series) => ({
          name: series.name,
          type: "bar",
          barMaxWidth: 9,
          itemStyle: { color: series.color },
          data: visible.map((item) => item[series.key]),
        })),
      }}
      table={
        <DataTable
          caption="Agent activity comparison data"
          columns={["Agent", "Decisions", "High risk", "Blocked"]}
          rows={visible.map((item) => [
            item.agent_id,
            item.decision_count,
            item.high_risk_count,
            item.block_count,
          ])}
        />
      }
    />
  );
}

export function AgentsPage() {
  const [windowValue, setWindow] = useWindow();
  const { cursor, setCursor, previous, canPrevious } =
    useCursorPagination(windowValue);
  const query = useApiQuery(
    ["agents", windowValue, cursor],
    "/v2/agents/risk",
    {
      params: { query: { window: windowValue, limit: 50, cursor } },
    },
  );
  const items = useMemo(() => (query.data as any)?.items ?? [], [query.data]);
  const riskOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 110, right: 24, top: 15, bottom: 25 },
      xAxis: {
        type: "value",
        max: 100,
        axisLabel: { color: "#64748b", formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#16202b" } },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: items.slice(0, 10).map((item: any) => item.agent_id),
        axisLabel: { color: "#93a0b4" },
      },
      series: [
        {
          type: "bar",
          barWidth: 13,
          data: items.slice(0, 10).map((item: any) => ({
            value: Math.round(item.risk_score * 100),
            itemStyle: {
              color:
                item.risk_score >= 0.7
                  ? "#ef4444"
                  : item.risk_score >= 0.4
                    ? "#eab308"
                    : "#22c55e",
            },
          })),
        },
      ],
    }),
    [items],
  );
  return (
    <>
      <PageHeader
        title="Agents"
        description="Server-calculated tenant risk rollups."
        controls={
          <WindowControl
            value={windowValue}
            onChange={setWindow}
            refreshing={query.isFetching}
            refresh={() => void query.refetch()}
            updatedAt={query.dataUpdatedAt}
          />
        }
      />
      <div className="route-grid route-grid-wide">
        <Panel title="Risk register">
          <State query={query} empty={!items.length}>
            <DataTable
              caption="Agent risk rollups"
              columns={[
                "Agent",
                "Risk",
                "Decisions",
                "High risk",
                "Blocked",
                "Last seen",
              ]}
              rows={items.map((item: any) => [
                <Link to="/agents/$agentId" params={{ agentId: item.agent_id }}>
                  <AgentIdentity id={item.agent_id} />
                </Link>,
                `${Math.round(item.risk_score * 100)}%`,
                item.decision_count,
                item.high_risk_count,
                item.block_count,
                formatTime(item.last_seen_at),
              ])}
            />
          </State>
          <PageNavigation
            query={query}
            previous={previous}
            canPrevious={canPrevious}
            next={() => setCursor((query.data as any).next_cursor)}
          />
        </Panel>
        <Panel
          title="Highest measured risk"
          description="Top 10 agents on this page, ordered by server-calculated risk."
        >
          <State query={query} empty={!items.length}>
            <Chart
              label="Agent risk ranking"
              option={riskOption}
              table={
                <DataTable
                  caption="Agent risk ranking data"
                  columns={["Agent", "Risk"]}
                  rows={items
                    .slice(0, 10)
                    .map((item: any) => [
                      item.agent_id,
                      `${Math.round(item.risk_score * 100)}%`,
                    ])}
                />
              }
            />
          </State>
        </Panel>
      </div>
      <Panel
        title="Agent activity comparison"
        description="First 10 agents on this page. High-risk and blocked counts can overlap; both are included in total decisions."
        wide
      >
        <State query={query} empty={!items.length}>
          <AgentActivityChart items={items} />
        </State>
      </Panel>
    </>
  );
}

export function AgentDetailPage() {
  const { agentId } = useParams({ strict: false }) as { agentId: string };
  const [windowValue, setWindow] = useWindow();
  const query = useApiQuery(
    ["agent", agentId, windowValue],
    "/v2/agents/{agent_id}",
    { params: { path: { agent_id: agentId }, query: { window: windowValue } } },
  );
  const item = query.data as any;
  const recentDecisions = useMemo(
    () => item?.recent_decisions ?? [],
    [item?.recent_decisions],
  );
  const riskHistoryOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { left: 42, right: 18, top: 24, bottom: 30 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: [...recentDecisions]
          .reverse()
          .map((decision: any) => shortUtc(decision.created_at)),
        axisLabel: { color: chartColours.text, fontSize: 9 },
        axisLine: { lineStyle: { color: "#1a2231" } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: {
          color: chartColours.text,
          fontSize: 9,
          formatter: "{value}%",
        },
        splitLine: { lineStyle: { color: chartColours.grid } },
      },
      series: [
        {
          name: "Behavioral risk",
          type: "line",
          smooth: 0.42,
          symbol: "none",
          lineStyle: { width: 2 },
          areaStyle: {
            opacity: 0.35,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(59, 130, 246, 0.6)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.02)" },
              ],
            },
          },
          color: chartColours.blue,
          data: [...recentDecisions].reverse().map((decision: any) => {
            const value = Math.round(decision.behavioral_score * 100);
            return {
              value,
              itemStyle: {
                color:
                  value >= 70
                    ? chartColours.red
                    : value >= 40
                      ? chartColours.amber
                      : chartColours.green,
              },
            };
          }),
        },
      ],
    }),
    [recentDecisions],
  );
  const activityOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "item" },
      legend: { bottom: 6, textStyle: { color: "#93a0b4", fontSize: 10 } },
      series: [
        {
          type: "pie",
          radius: ["42%", "68%"],
          center: ["50%", "43%"],
          label: { show: false },
          itemStyle: { borderColor: "#0a0e15", borderWidth: 2 },
          data: [
            {
              name: "Allowed",
              value: item?.allow_count ?? 0,
              itemStyle: { color: chartColours.green },
            },
            {
              name: "Would block",
              value: item?.would_block_count ?? 0,
              itemStyle: { color: chartColours.amber },
            },
            {
              name: "Blocked",
              value: item?.block_count ?? 0,
              itemStyle: { color: chartColours.red },
            },
          ],
        },
      ],
    }),
    [item],
  );
  return (
    <>
      <PageHeader
        title={agentId}
        description="Measured agent activity and recent decisions."
        controls={
          <WindowControl
            value={windowValue}
            onChange={setWindow}
            refreshing={query.isFetching}
            refresh={() => void query.refetch()}
            updatedAt={query.dataUpdatedAt}
          />
        }
      />
      <State query={query}>
        <div className="metrics">
          <Metric
            label="Risk"
            value={item ? Math.round(item.risk_score * 100) : null}
            unit="%"
            tone="bad"
          />
          <Metric label="Decisions" value={item?.decision_count} tone="blue" />
          <Metric label="Blocked" value={item?.block_count} tone="bad" />
          <Metric
            label="P95 latency"
            value={item?.evaluation_latency?.p95_ms}
            unit=" ms"
            tone="blue"
          />
        </div>
        <div className="route-chart-grid">
          <Panel title="Behavioral risk over recent decisions">
            <Chart
              label="Agent behavioral risk over recent decisions"
              option={riskHistoryOption}
              table={
                <DataTable
                  caption="Agent behavioral risk history data"
                  columns={["UTC time", "Trace", "Risk", "Verdict"]}
                  rows={[...recentDecisions]
                    .reverse()
                    .map((decision: any) => [
                      formatTime(decision.created_at),
                      decision.trace_id,
                      `${Math.round(decision.behavioral_score * 100)}%`,
                      decision.verdict,
                    ])}
                />
              }
            />
          </Panel>
          <Panel title="Verdict profile">
            <Chart
              label="Agent verdict profile"
              option={activityOption}
              table={
                <DataTable
                  caption="Agent verdict profile data"
                  columns={["Verdict", "Decisions"]}
                  rows={[
                    ["Allowed", item?.allow_count],
                    ["Would block", item?.would_block_count],
                    ["Blocked", item?.block_count],
                  ]}
                />
              }
            />
          </Panel>
        </div>
        <Panel title="Recent decisions" wide>
          <DataTable
            caption="Recent agent decisions"
            columns={["UTC time", "Trace", "Verdict", "Risk"]}
            rows={recentDecisions.map((decision: any) => [
              formatTime(decision.created_at),
              <Link
                className="mono"
                to="/decisions/$traceId"
                params={{ traceId: decision.trace_id }}
              >
                {decision.trace_id}
              </Link>,
              <Badge value={decision.verdict} />,
              `${Math.round(decision.behavioral_score * 100)}%`,
            ])}
          />
        </Panel>
      </State>
    </>
  );
}

export function PoliciesPage() {
  const initialSearch = new URLSearchParams(location.search);
  const [policySearch, setPolicySearch] = useState(
    initialSearch.get("policy") ?? "",
  );
  const [severity, setSeverity] = useState(initialSearch.get("severity") ?? "");
  const [showAllPolicies, setShowAllPolicies] = useState(false);
  const { cursor, setCursor, previous, canPrevious } = useCursorPagination();
  const summary = useApiQuery(["policy-summary"], "/v2/policies/summary");
  const query = useApiQuery(["policies", cursor, severity], "/v2/policies", {
    params: { query: { limit: 100, cursor, severity: severity || undefined } },
  });
  const items = useMemo(() => (query.data as any)?.items ?? [], [query.data]);
  const filteredPolicies = useMemo(
    () =>
      items.filter((item: any) => {
        const matchesSearch = `${item.id} ${item.title} ${item.category}`
          .toLowerCase()
          .includes(policySearch.toLowerCase());
        return matchesSearch && (!severity || item.severity === severity);
      }),
    [items, policySearch, severity],
  );
  const visiblePolicies = showAllPolicies
    ? filteredPolicies
    : filteredPolicies.slice(0, 24);
  const updatePolicyFilters = (nextSearch: string, nextSeverity: string) => {
    setPolicySearch(nextSearch);
    setSeverity(nextSeverity);
    if (nextSeverity !== severity) setCursor(undefined);
    setShowAllPolicies(false);
    const search = new URLSearchParams();
    if (nextSearch) search.set("policy", nextSearch);
    if (nextSeverity) search.set("severity", nextSeverity);
    history.replaceState(null, "", `${location.pathname}?${search}`);
  };
  const data = summary.data as any;
  const severityCounts = ["critical", "high", "medium", "low"].map(
    (name, index) => ({
      name,
      value: filteredPolicies.filter((item: any) => item.severity === name)
        .length,
      itemStyle: { color: ["#f472b6", "#fb923c", "#facc15", "#38bdf8"][index] },
    }),
  );
  const statusItems = useMemo(
    () => Object.entries(data?.counts_by_status ?? {}) as [string, number][],
    [data],
  );
  const statusOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 118, right: 30, top: 20, bottom: 28 },
      xAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: chartColours.text, fontSize: 9 },
        splitLine: { lineStyle: { color: chartColours.grid } },
      },
      yAxis: {
        type: "category",
        data: statusItems.map(([name]) => name.replaceAll("_", " ")),
        axisLabel: { color: chartColours.text, fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          barWidth: 18,
          data: statusItems.map(([, value], index) => ({
            value,
            itemStyle: {
              color: [
                chartColours.green,
                chartColours.amber,
                chartColours.blue,
                "#64748b",
              ][index % 4],
            },
          })),
          label: {
            show: true,
            position: "right",
            color: "#e7ecf3",
            fontSize: 10,
          },
        },
      ],
    }),
    [statusItems],
  );
  return (
    <>
      <PageHeader
        title="Policies"
        description="Read-only active policy pack, enforcement posture, and evidence prerequisites."
        controls={
          <div className="controls controls-wrap">
            <label>
              Find policy
              <input
                type="search"
                value={policySearch}
                placeholder="Rule, title, or category"
                onChange={(event) =>
                  updatePolicyFilters(event.target.value, severity)
                }
              />
            </label>
            <label>
              Severity
              <select
                value={severity}
                onChange={(event) =>
                  updatePolicyFilters(policySearch, event.target.value)
                }
              >
                <option value="">All severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <button
              onClick={() =>
                void Promise.all([summary.refetch(), query.refetch()])
              }
              disabled={summary.isFetching || query.isFetching}
            >
              <RefreshCw
                className={summary.isFetching || query.isFetching ? "spin" : ""}
              />
              Refresh
            </button>
          </div>
        }
      />
      <State query={summary}>
        <div className="metrics">
          <Metric label="Rules" value={data?.total_rules} tone="blue" />
          <Metric label="Enforced" value={data?.enforced_rules} tone="good" />
          <Metric label="Planned" value={data?.planned_rules} tone="warn" />
        </div>
      </State>
      <div className="route-grid route-grid-policy">
        <Panel
          description="Text search applies to this page. Severity filters the full catalogue."
          title={
            data ? `${data.pack_name} ${data.pack_version}` : "Policy catalogue"
          }
        >
          <State query={query} empty={!filteredPolicies.length}>
            <DataTable
              caption="Policy catalogue"
              columns={[
                "Rule",
                "Title",
                "Category",
                "Severity",
                "Decision",
                "Status",
              ]}
              rows={visiblePolicies.map((item: any) => [
                <span className="mono">{item.id}</span>,
                item.title,
                item.category,
                <Badge value={item.severity} />,
                <Badge value={item.decision} />,
                item.status,
              ])}
            />
          </State>
          {filteredPolicies.length > 24 && (
            <button onClick={() => setShowAllPolicies((current) => !current)}>
              {showAllPolicies
                ? "Show first 24 policies"
                : `Show all ${filteredPolicies.length} policies`}
            </button>
          )}
          <PageNavigation
            query={query}
            previous={previous}
            canPrevious={canPrevious}
            next={() => setCursor((query.data as any).next_cursor)}
          />
        </Panel>
        <Panel title="Rule lifecycle">
          <State query={summary} empty={!statusItems.length}>
            <Chart
              label="Policy rule lifecycle"
              option={statusOption}
              table={
                <DataTable
                  caption="Policy rule lifecycle data"
                  columns={["Status", "Rules"]}
                  rows={statusItems}
                />
              }
            />
          </State>
          <dl className="compact-details">
            <dt>Default decision</dt>
            <dd>
              <Badge value={data?.default_decision ?? "Unavailable"} />
            </dd>
            <dt>Pack version</dt>
            <dd className="mono">{data?.pack_version ?? "Unavailable"}</dd>
          </dl>
          <h3>Severity distribution</h3>
          <p className="source-note">Matching policies on the loaded page.</p>
          <State query={query} empty={!filteredPolicies.length}>
            <Chart
              label="Policy severity distribution"
              option={{
                tooltip: { trigger: "item" },
                legend: { bottom: 0, textStyle: { color: chartColours.text } },
                series: [
                  {
                    type: "pie",
                    radius: ["42%", "68%"],
                    center: ["50%", "43%"],
                    label: { show: false },
                    itemStyle: {
                      borderColor: chartColours.panel,
                      borderWidth: 3,
                    },
                    data: severityCounts,
                  },
                ],
              }}
              table={
                <DataTable
                  caption="Policy severity distribution data"
                  columns={["Severity", "Rules"]}
                  rows={severityCounts.map((item) => [item.name, item.value])}
                />
              }
            />
          </State>
        </Panel>
      </div>
    </>
  );
}

export function IntegrationsPage() {
  const { cursor, setCursor, previous, canPrevious } = useCursorPagination();
  const query = useApiQuery(
    ["integrations", cursor],
    "/v2/integrations/health",
    {
      params: { query: { limit: 100, cursor } },
    },
  );
  const items = useMemo(() => (query.data as any)?.items ?? [], [query.data]);
  const latencyItems = useMemo(
    () => items.filter((item: any) => item.latency_ms != null),
    [items],
  );
  const latencyOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 110, right: 28, top: 15, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: "#64748b", formatter: "{value} ms" },
        splitLine: { lineStyle: { color: "#16202b" } },
      },
      yAxis: {
        type: "category",
        data: latencyItems.map((item: any) => item.integration_key),
        axisLabel: { color: "#93a0b4" },
      },
      series: [
        {
          type: "bar",
          barWidth: 13,
          data: latencyItems.map((item: any) => ({
            value: item.latency_ms,
            itemStyle: {
              color:
                item.status === "HEALTHY"
                  ? "#22c55e"
                  : item.status === "DEGRADED"
                    ? "#eab308"
                    : "#ef4444",
            },
          })),
        },
      ],
    }),
    [latencyItems],
  );
  return (
    <>
      <PageHeader
        title="Integrations"
        description="Measured dependency checks, freshness, latency, and safe diagnostic state."
        controls={
          <button
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw className={query.isFetching ? "spin" : ""} />
            Refresh snapshot
          </button>
        }
      />
      <State query={query} empty={!items.length}>
        <div className="integration-cards">
          {items.map((item: any) => (
            <article key={item.integration_key} className="integration-card">
              <div>
                <span
                  className={`health-indicator health-${item.status.toLowerCase()}`}
                />
                <strong>{item.integration_key}</strong>
              </div>
              <Badge value={item.status} />
              <small>{item.integration_kind}</small>
              <b>
                {item.latency_ms == null
                  ? "Unmeasured"
                  : `${item.latency_ms} ms`}
              </b>
              <time>{formatTime(item.checked_at)}</time>
            </article>
          ))}
        </div>
      </State>
      <div className="route-grid">
        <Panel
          title="Integration health"
          description="Measured checks on this page."
        >
          <State query={query} empty={!items.length}>
            <DataTable
              caption="Measured integrations"
              columns={[
                "Integration",
                "Kind",
                "State",
                "Checked UTC",
                "Latency",
                "Diagnostic",
              ]}
              rows={items.map((item: any) => [
                item.integration_key,
                item.integration_kind,
                <Badge value={item.status} />,
                formatTime(item.checked_at),
                item.latency_ms == null
                  ? "Unmeasured"
                  : `${item.latency_ms} ms`,
                item.diagnostic_code ?? "None",
              ])}
            />
          </State>
          <PageNavigation
            query={query}
            previous={previous}
            canPrevious={canPrevious}
            next={() => setCursor((query.data as any).next_cursor)}
          />
        </Panel>
        <Panel title="Measured latency">
          <State query={query} empty={!latencyItems.length}>
            <Chart
              label="Integration latency"
              option={latencyOption}
              table={
                <DataTable
                  caption="Integration latency data"
                  columns={["Integration", "Latency", "State"]}
                  rows={latencyItems.map((item: any) => [
                    item.integration_key,
                    `${item.latency_ms} ms`,
                    item.status,
                  ])}
                />
              }
            />
          </State>
        </Panel>
      </div>
    </>
  );
}

export function BackendPage() {
  const service = useApiQuery(["backend-service"], "/v2/service/status");
  const data = service.data as any;
  const components = useMemo(() => data?.components ?? [], [data]);
  const latencyComponents = useMemo(
    () => components.filter((item: any) => item.latency_ms != null),
    [components],
  );
  const latencyOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 90, right: 30, top: 18, bottom: 28 },
      xAxis: {
        type: "value",
        axisLabel: { color: chartColours.text, formatter: "{value} ms" },
        splitLine: { lineStyle: { color: chartColours.grid } },
      },
      yAxis: {
        type: "category",
        data: latencyComponents.map((item: any) => item.name),
        axisLabel: { color: chartColours.text },
      },
      series: [
        {
          type: "bar",
          barWidth: 14,
          data: latencyComponents.map((item: any) => ({
            value: item.latency_ms,
            itemStyle: {
              color:
                item.status === "healthy"
                  ? chartColours.green
                  : item.status === "degraded"
                    ? chartColours.amber
                    : chartColours.red,
            },
          })),
        },
      ],
    }),
    [latencyComponents],
  );
  return (
    <>
      <PageHeader
        title="Backend"
        description="Production, legacy, edge, internal, and demonstration runtime boundaries."
        controls={
          <button
            onClick={() => void service.refetch()}
            disabled={service.isFetching}
          >
            <RefreshCw className={service.isFetching ? "spin" : ""} />
            Refresh status
          </button>
        }
      />
      <div className="backend-flow" aria-label="DUSK backend request flow">
        <div>
          <strong>Workloads</strong>
          <code>/v1 and /v2 evaluation</code>
        </div>
        <span aria-hidden="true">›</span>
        <div>
          <strong>Gateways</strong>
          <code>OIDC or workload bearer</code>
        </div>
        <span aria-hidden="true">›</span>
        <div>
          <strong>Policy runtime</strong>
          <code>canonical evaluator</code>
        </div>
        <span aria-hidden="true">›</span>
        <div>
          <strong>Evidence</strong>
          <code>PostgreSQL and audit chain</code>
        </div>
        <span aria-hidden="true">›</span>
        <div>
          <strong>Console</strong>
          <code>read-only /v2 views</code>
        </div>
      </div>
      <div className="route-grid">
        <Panel title="Measured component state">
          <State query={service} empty={!components.length}>
            <DataTable
              caption="Measured backend components"
              columns={[
                "Component",
                "State",
                "Measured UTC",
                "Latency",
                "Diagnostic",
              ]}
              rows={components.map((item: any) => [
                item.name,
                <Badge value={item.status} />,
                formatTime(item.measured_at),
                item.latency_ms == null
                  ? "Unmeasured"
                  : `${item.latency_ms} ms`,
                item.diagnostic_code ?? "None",
              ])}
            />
          </State>
        </Panel>
        <Panel title="Component latency">
          <State query={service} empty={!latencyComponents.length}>
            <Chart
              label="Backend component latency"
              option={latencyOption}
              table={
                <DataTable
                  caption="Backend component latency data"
                  columns={["Component", "Latency", "State"]}
                  rows={latencyComponents.map((item: any) => [
                    item.name,
                    `${item.latency_ms} ms`,
                    item.status,
                  ])}
                />
              }
            />
          </State>
        </Panel>
      </div>
      <Panel
        title="Runtime interface inventory"
        description="Workload mutation interfaces are represented by their contracts and persisted evidence, never invoked from this console."
        wide
      >
        <DataTable
          caption="Backend interface coverage"
          columns={[
            "Boundary",
            "Surface",
            "Method",
            "Path",
            "Audience",
            "Evidence",
          ]}
          rows={backendSurfaces.map((item) => [
            <Badge value={item.boundary} />,
            item.surface,
            <code>{item.method}</code>,
            <code>{item.path}</code>,
            item.audience,
            item.evidence,
          ])}
        />
      </Panel>
    </>
  );
}

export function AuditPage() {
  const { cursor, setCursor, previous, canPrevious } = useCursorPagination();
  const query = useApiQuery(["audit", cursor], "/v2/audit-events", {
    params: { query: { limit: 10, cursor } },
  });
  const items = useMemo(() => (query.data as any)?.items ?? [], [query.data]);
  const chronologicalItems = useMemo(
    () =>
      [...items].sort(
        (left: any, right: any) =>
          new Date(left.occurred_at).getTime() -
          new Date(right.occurred_at).getTime(),
      ),
    [items],
  );
  const auditSequenceOption = useMemo<EChartsCoreOption>(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { left: 54, right: 18, top: 24, bottom: 32 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: chronologicalItems.map((item: any) => shortUtc(item.occurred_at)),
        axisLabel: { color: chartColours.text, fontSize: 9 },
        axisLine: { lineStyle: { color: "#1a2231" } },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: chartColours.text, fontSize: 9 },
        splitLine: { lineStyle: { color: chartColours.grid } },
      },
      series: [
        {
          name: "Audit sequence",
          type: "line",
          smooth: 0.32,
          symbol: "none",
          lineStyle: { width: 2, color: chartColours.blue },
          itemStyle: { color: chartColours.blue },
          areaStyle: {
            opacity: 0.32,
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(59, 130, 246, 0.55)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.02)" },
              ],
            },
          },
          data: chronologicalItems.map((item: any) => item.sequence),
        },
      ],
    }),
    [chronologicalItems],
  );
  return (
    <>
      <PageHeader
        title="Audit continuity"
        description="Safe chain metadata only. Signatures and sensitive event details are never returned."
        controls={
          <button
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw className={query.isFetching ? "spin" : ""} />
            Refresh snapshot
          </button>
        }
      />
      <div
        className="audit-chain"
        role="img"
        aria-label="Recent audit chain continuity"
      >
        {items
          .slice(0, 6)
          .reverse()
          .map((item: any) => (
            <div className="audit-node" key={item.event_id}>
              <span>
                {item.previous_digest == null
                  ? "Chain origin"
                  : "Previous digest recorded"}
              </span>
              <strong>Sequence {item.sequence}</strong>
              <small>{item.event_type.replaceAll("_", " ")}</small>
              <Badge value={item.signature_present ? "SIGNED" : "UNSIGNED"} />
            </div>
          ))}
      </div>
      <Panel title="Audit sequence over time" wide>
        <State query={query} empty={!items.length}>
          <Chart
            label="Audit sequence over time"
            option={auditSequenceOption}
            table={
              <DataTable
                caption="Audit sequence over time data"
                columns={["UTC time", "Sequence", "Event", "Signature"]}
                rows={chronologicalItems.map((item: any) => [
                  formatTime(item.occurred_at),
                  item.sequence,
                  item.event_type,
                  item.signature_present ? "Present" : "Absent",
                ])}
              />
            }
          />
        </State>
      </Panel>
      <Panel
        title={`Snapshot sequence ${(query.data as any)?.snapshot_sequence ?? "unavailable"}`}
        wide
      >
        <State query={query} empty={!items.length}>
          <DataTable
            caption="Tenant audit chain"
            columns={[
              "Sequence",
              "UTC time",
              "Event",
              "Trace",
              "Digest",
              "Previous",
              "Signed",
              "Detail",
            ]}
            rows={items.map((item: any) => [
              item.sequence,
              formatTime(item.occurred_at),
              item.event_type,
              item.trace_id ? (
                <Link
                  className="mono"
                  to="/decisions/$traceId"
                  params={{ traceId: item.trace_id }}
                >
                  {item.trace_id}
                </Link>
              ) : (
                "None"
              ),
              <span className="mono digest">{item.digest}</span>,
              <span className="mono digest">
                {item.previous_digest ?? "Chain origin"}
              </span>,
              item.signature_present ? "Yes" : "No",
              item.detail_retention_state,
            ])}
          />
        </State>
        <PageNavigation
          query={query}
          previous={previous}
          canPrevious={canPrevious}
          next={() => setCursor((query.data as any).next_cursor)}
        />
      </Panel>
    </>
  );
}

export function ForbiddenPage() {
  return (
    <div className="state state-error">
      <strong>Access forbidden</strong>
      <p>Your validated roles do not include this capability.</p>
      <Link to="/overview">Return to overview</Link>
    </div>
  );
}

const SettingsScreen = lazy(() => import("./settings"));
export function SettingsPage() {
  return (
    <Suspense fallback={<div className="state">Loading settings</div>}>
      <SettingsScreen />
    </Suspense>
  );
}
