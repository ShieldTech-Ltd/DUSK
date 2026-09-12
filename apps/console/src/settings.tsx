import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { capabilitiesFor, useAuth } from "./auth";
import { loadConfig, type PublicConfig } from "./config";
import { Panel, Badge, formatTime } from "./components";
import { useWindowRange, type WindowValue } from "./window";

export default function SettingsPage() {
  const auth = useAuth();
  const { range, setRange } = useWindowRange();
  const capabilities = capabilitiesFor(auth.roles);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [configError, setConfigError] = useState(false);
  const [feedback, setFeedback] = useState("");
  useEffect(() => {
    void loadConfig()
      .then(setConfig)
      .catch(() => setConfigError(true));
  }, []);
  const username =
    typeof auth.user?.profile.preferred_username === "string"
      ? auth.user.profile.preferred_username
      : "Authenticated user";
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p>
            Workspace preferences, deployment connections, and your current
            access.
          </p>
        </div>
      </div>
      {configError && (
        <div className="state state-error" role="alert">
          Deployment configuration could not be loaded. Reload the console or
          contact your deployment administrator.
        </div>
      )}
      <div className="settings-summary" aria-label="Deployment connection map">
        <div>
          <strong>Console</strong>
          <span className="mono wrap">{location.origin}</span>
          <small>
            {location.protocol === "https:" ? "HTTPS origin" : "HTTP origin"}
          </small>
        </div>
        <ArrowRight aria-hidden="true" />
        <div>
          <strong>Control plane</strong>
          <span className="mono wrap">
            {config?.apiBaseUrl ?? "Unavailable"}
          </span>
          <small>Authenticated read API</small>
        </div>
        <div>
          <strong>Identity provider</strong>
          <span className="mono wrap">
            {config?.oidcAuthority ?? "Unavailable"}
          </span>
          <small>Authorization Code with PKCE</small>
        </div>
      </div>
      <div className="settings-grid">
        <Panel
          title="Workspace preferences"
          description="Applies to your current console session."
        >
          <label className="settings-field">
            Dashboard time window
            <select
              value={range}
              onChange={(event) => setRange(event.target.value as WindowValue)}
            >
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
          </label>
          <dl>
            <dt>Time zone</dt>
            <dd>UTC across charts and audit records</dd>
            <dt>Data refresh</dt>
            <dd>Every 30 seconds while the tab is visible</dd>
            <dt>Chart accessibility</dt>
            <dd>Each chart includes a data-table alternative</dd>
            <dt>Motion</dt>
            <dd>Follows your system reduced-motion preference</dd>
          </dl>
        </Panel>
        <Panel title="Environment">
          <dl>
            <dt>Environment</dt>
            <dd>
              {config?.environmentLabel ??
                (configError ? "Unavailable" : "Loading")}
            </dd>
            <dt>Control plane API</dt>
            <dd className="mono wrap">{config?.apiBaseUrl ?? "Unavailable"}</dd>
            <dt>Identity authority</dt>
            <dd className="mono wrap">
              {config?.oidcAuthority ?? "Unavailable"}
            </dd>
            <dt>OIDC client</dt>
            <dd className="mono">{config?.oidcClientId ?? "Unavailable"}</dd>
            <dt>Console version</dt>
            <dd className="mono">v{__APP_VERSION__}</dd>
          </dl>
          <p className="source-note">
            Endpoints and client configuration are managed at deployment.
            Changing them requires an administrator to update the public
            configuration and matching CSP.
          </p>
          <button
            disabled={!config}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(
                  JSON.stringify(
                    {
                      consoleVersion: __APP_VERSION__,
                      consoleOrigin: location.origin,
                      apiBaseUrl: config?.apiBaseUrl,
                      oidcAuthority: config?.oidcAuthority,
                      oidcClientId: config?.oidcClientId,
                      environmentLabel: config?.environmentLabel,
                    },
                    null,
                    2,
                  ),
                );
                setFeedback(
                  "Public deployment configuration copied. No tokens or session details included.",
                );
              } catch {
                setFeedback(
                  "Clipboard access unavailable. Copy the displayed public values manually.",
                );
              }
            }}
          >
            Copy public configuration
          </button>
        </Panel>
        <Panel title="Session">
          <dl>
            <dt>Signed in as</dt>
            <dd>{username}</dd>
            <dt>Tenant</dt>
            <dd className="mono wrap">{auth.tenant ?? "Unavailable"}</dd>
            <dt>Validated roles</dt>
            <dd>{auth.roles.join(", ") || "None"}</dd>
            <dt>Access token storage</dt>
            <dd>In memory only</dd>
            <dt>Token expires at</dt>
            <dd>
              {auth.user?.expires_at
                ? formatTime(
                    new Date(auth.user.expires_at * 1000).toISOString(),
                  )
                : "Unavailable"}
            </dd>
            <dt>Session renewal</dt>
            <dd>Sign in again after expiration</dd>
          </dl>
          <button
            onClick={() => {
              void auth
                .signOut()
                .catch(() =>
                  setFeedback(
                    "Sign-out could not reach the identity provider. Try again.",
                  ),
                );
            }}
          >
            Sign out
          </button>
        </Panel>
        <Panel
          title="Your access"
          description="Navigation capabilities from your session roles. The API independently enforces every request."
        >
          <ul
            className="capability-grid"
            aria-label="Current session capabilities"
          >
            {Object.entries(capabilities).map(([name, allowed]) => (
              <li key={name}>
                <span>
                  {name === "decisionDetail"
                    ? "Decision investigation"
                    : name.charAt(0).toUpperCase() + name.slice(1)}
                </span>
                <Badge value={allowed ? "AVAILABLE" : "UNAVAILABLE"} />
              </li>
            ))}
          </ul>
          <p className="source-note">
            Tenant, role assignments, and policy enforcement cannot be changed
            from this console.
          </p>
        </Panel>
      </div>
      <p role="status">{feedback}</p>
    </>
  );
}
