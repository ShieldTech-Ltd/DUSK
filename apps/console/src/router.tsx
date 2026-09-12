import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { Shell } from "./shell";
import {
  AgentDetailPage,
  AgentsPage,
  AuditPage,
  BackendPage,
  CallbackPage,
  DecisionDetailPage,
  DecisionsPage,
  ForbiddenPage,
  IntegrationsPage,
  LoginPage,
  OverviewPage,
  PoliciesPage,
  SettingsPage,
} from "./pages";

const root = createRootRoute({ component: Outlet });
const login = createRoute({
  getParentRoute: () => root,
  path: "/login",
  component: LoginPage,
});
const callback = createRoute({
  getParentRoute: () => root,
  path: "/auth/callback",
  component: CallbackPage,
});
const app = createRoute({
  getParentRoute: () => root,
  id: "app",
  component: Shell,
});
const overview = createRoute({
  getParentRoute: () => app,
  path: "/overview",
  component: OverviewPage,
});
const decisions = createRoute({
  getParentRoute: () => app,
  path: "/decisions",
  component: DecisionsPage,
});
const decision = createRoute({
  getParentRoute: () => app,
  path: "/decisions/$traceId",
  component: DecisionDetailPage,
});
const agents = createRoute({
  getParentRoute: () => app,
  path: "/agents",
  component: AgentsPage,
});
const agent = createRoute({
  getParentRoute: () => app,
  path: "/agents/$agentId",
  component: AgentDetailPage,
});
const policies = createRoute({
  getParentRoute: () => app,
  path: "/policies",
  component: PoliciesPage,
});
const integrations = createRoute({
  getParentRoute: () => app,
  path: "/integrations",
  component: IntegrationsPage,
});
const backend = createRoute({
  getParentRoute: () => app,
  path: "/backend",
  component: BackendPage,
});
const audit = createRoute({
  getParentRoute: () => app,
  path: "/audit",
  component: AuditPage,
});
const settings = createRoute({
  getParentRoute: () => app,
  path: "/settings",
  component: SettingsPage,
});
const forbidden = createRoute({
  getParentRoute: () => app,
  path: "/forbidden",
  component: ForbiddenPage,
});
const index = createRoute({
  getParentRoute: () => root,
  path: "/",
  component: LoginPage,
});

const routeTree = root.addChildren([
  index,
  login,
  callback,
  app.addChildren([
    overview,
    decisions,
    decision,
    agents,
    agent,
    policies,
    integrations,
    backend,
    audit,
    settings,
    forbidden,
  ]),
]);
export const router = createRouter({ routeTree, defaultPreload: "intent" });
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
