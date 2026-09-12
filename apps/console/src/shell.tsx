import { Link, Outlet, useLocation, useNavigate } from "@tanstack/react-router";
import {
  Bell,
  BookOpenCheck,
  Bot,
  CalendarDays,
  CircleGauge,
  FileClock,
  LogOut,
  PlugZap,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Search,
  ServerCog,
  Settings,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { get } from "./api/client";
import { capabilitiesFor, landingFor, useAuth } from "./auth";
import { DuskMark } from "./brand";
import { loadConfig } from "./config";
import { useApiQuery } from "./hooks";
import { WINDOW_OPTIONS, useWindowRange, WindowProvider } from "./window";

const nav = [
  ["/overview", "Overview", CircleGauge, "dashboard"],
  ["/decisions", "Decisions", ScrollText, "decisions"],
  ["/agents", "Agents", Bot, "agents"],
  ["/policies", "Policies", BookOpenCheck, "policies"],
  ["/integrations", "Integrations", PlugZap, "integrations"],
  ["/backend", "Backend", ServerCog, "backend"],
  ["/audit", "Audit", FileClock, "audit"],
  ["/settings", "Settings", Settings, null],
] as const;

function shortTime(value?: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  }).format(new Date(value));
}

function ago(fromIso?: string | null) {
  if (!fromIso) return "";
  const elapsed = Date.now() - Date.parse(fromIso);
  if (!Number.isFinite(elapsed) || elapsed < 0) return "just now";
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.floor(minutes / 60)} h ago`;
}

function ShellInner() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { range, setRange } = useWindowRange();
  const searchRef = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState("");
  const [searching, setSearching] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [environment, setEnvironment] = useState("Detecting environment");
  const [, setTick] = useState(0);
  const capabilities = capabilitiesFor(auth.roles);
  const summary = useApiQuery(
    ["summary", range],
    "/v2/dashboard/summary",
    { params: { query: { window: range } } },
    Boolean(auth.user && capabilities.dashboard),
  );
  const audit = useApiQuery(
    ["ops-audit"],
    "/v2/audit-events",
    { params: { query: { limit: 6 } } },
    Boolean(auth.user && capabilities.audit),
  );
  const updatedAt = (summary.data as any)?.freshness?.source_last_updated_at as
    | string
    | undefined;
  const auditItems = ((audit.data as any)?.items ?? []) as any[];

  useEffect(() => {
    void loadConfig()
      .then((config) => setEnvironment(config.environmentLabel))
      .catch(() => setEnvironment("Configuration unavailable"));
  }, []);
  useEffect(() => {
    if (!auth.loading && !auth.user) void navigate({ to: "/login" });
  }, [auth.loading, auth.user, navigate]);
  useEffect(() => {
    const timer = setInterval(() => setTick((value) => value + 1), 30_000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const runSearch = async () => {
    const query = term.trim();
    if (!query || searching) return;
    setSearching(true);
    try {
      if (/^[0-9a-fA-F-]{24,}$/.test(query) && capabilities.decisionDetail) {
        void navigate({
          to: "/decisions/$traceId",
          params: { traceId: query },
        });
        return;
      }
      if (capabilities.agents) {
        const result = await get("/v2/agents/risk", {
          params: { query: { window: range, limit: 50 } },
        });
        const wanted = query.toLowerCase();
        const match = ((result as any)?.items ?? []).find(
          (item: any) =>
            typeof item.agent_id === "string" &&
            item.agent_id.toLowerCase().includes(wanted),
        );
        if (match) {
          void navigate({
            to: "/agents/$agentId",
            params: { agentId: match.agent_id },
          });
          return;
        }
      }
      if (capabilities.policies) {
        void navigate({
          to: "/policies",
          search: { policy: query } as never,
        });
        return;
      }
      void navigate({ to: landingFor(auth.roles) });
    } finally {
      setSearching(false);
      setTerm("");
    }
  };

  if (auth.loading || !auth.user)
    return <div className="boot">Establishing secure session…</div>;

  const username =
    typeof auth.user.profile.preferred_username === "string"
      ? auth.user.profile.preferred_username
      : "Authenticated user";
  const initials = username
    .split(/[^a-zA-Z0-9]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => (part[0] ?? "").toUpperCase())
    .join("");

  const routeCapability = location.pathname.startsWith("/overview")
    ? capabilities.dashboard
    : location.pathname.startsWith("/decisions/")
      ? capabilities.decisionDetail
      : location.pathname.startsWith("/agents")
        ? capabilities.agents
        : location.pathname.startsWith("/policies")
          ? capabilities.policies
          : location.pathname.startsWith("/integrations")
            ? capabilities.integrations
            : location.pathname.startsWith("/backend")
              ? capabilities.backend
              : location.pathname.startsWith("/audit")
                ? capabilities.audit
                : location.pathname.startsWith("/decisions")
                  ? capabilities.decisions
                  : true;

  return (
    <div className={`app${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="side-brand">
          <Link
            to={landingFor(auth.roles)}
            className="side-logo"
            aria-label="DUSK home"
          >
            <DuskMark />
          </Link>
          <button
            className="side-toggle"
            aria-label={
              sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
            }
            aria-expanded={!sidebarCollapsed}
            onClick={() => setSidebarCollapsed((value) => !value)}
          >
            {sidebarCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          </button>
        </div>
        <nav className="side-nav">
          {nav
            .filter(
              ([, , , capability]) => !capability || capabilities[capability],
            )
            .map(([to, label, Icon]) => (
              <Link
                key={to}
                to={to}
                aria-label={label}
                activeProps={{ "aria-current": "page" }}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </Link>
            ))}
        </nav>
        <div className="side-environment" title="Active environment">
          <span className="dot dot-good" aria-hidden="true" />
          <strong>{environment}</strong>
        </div>
        <div className="side-art" aria-hidden="true" />
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="search">
            <Search aria-hidden="true" />
            <input
              ref={searchRef}
              type="search"
              value={term}
              placeholder="Search decisions, agents, policies…"
              aria-label="Search the console"
              onChange={(event) => setTerm(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runSearch();
              }}
            />
            <kbd aria-hidden="true">⌘K</kbd>
          </div>
          <div className="top-spacer" />
          <span className="top-tz">UTC</span>
          <label className="top-window">
            <CalendarDays aria-hidden="true" />
            <select
              value={range}
              aria-label="UTC window"
              onChange={(event) =>
                setRange(
                  event.target.value as (typeof WINDOW_OPTIONS)[number][0],
                )
              }
            >
              {WINDOW_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <span className="top-fresh" role="status">
            <i className={`dot ${updatedAt ? "dot-good" : ""}`} />
            {updatedAt ? `Updated ${ago(updatedAt)}` : "Awaiting data"}
          </span>
          {capabilities.audit && (
            <div className="top-bell">
              <button
                aria-label="Recent audit activity"
                aria-expanded={bellOpen}
                onClick={() => setBellOpen((value) => !value)}
              >
                <Bell />
              </button>
              {bellOpen && (
                <div className="popover">
                  <header>
                    <span>Recent activity</span>
                    <Link to="/audit" onClick={() => setBellOpen(false)}>
                      Open audit
                    </Link>
                  </header>
                  {auditItems.length ? (
                    <ul>
                      {auditItems.map((item: any) => (
                        <li key={item.event_id}>
                          <Link to="/audit" onClick={() => setBellOpen(false)}>
                            <span>{item.event_type?.replaceAll("_", " ")}</span>
                            <small>{shortTime(item.occurred_at)} UTC</small>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mono">No audit events yet.</p>
                  )}
                </div>
              )}
            </div>
          )}
          <div className="top-user">
            <span className="avatar" aria-hidden="true">
              {initials || "DU"}
            </span>
            <div>
              <strong>{username}</strong>
              <small>Tenant {auth.tenant?.slice(-8) ?? "unavailable"}</small>
            </div>
            <button
              aria-label="Sign out"
              onClick={() => void auth.signOut()}
              style={{
                background: "transparent",
                border: 0,
                color: "var(--faint)",
              }}
            >
              <LogOut />
            </button>
          </div>
        </header>
        <main id="content" tabIndex={-1}>
          {routeCapability ? (
            <Outlet />
          ) : (
            <div className="state state-error">
              <strong>Access forbidden</strong>
              <p>Your validated roles do not include this capability.</p>
              <Link to="/overview">Return to overview</Link>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export function Shell() {
  return (
    <WindowProvider>
      <ShellInner />
    </WindowProvider>
  );
}
