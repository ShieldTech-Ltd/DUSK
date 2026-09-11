import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { User, UserManager, WebStorageStateStore } from "oidc-client-ts";
import { loadConfig } from "./config";

class MemoryStorage implements Storage {
  private values = new Map<string, string>();
  get length() {
    return this.values.size;
  }
  clear() {
    this.values.clear();
  }
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  key(index: number) {
    return [...this.values.keys()][index] ?? null;
  }
  removeItem(key: string) {
    this.values.delete(key);
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

let managerPromise: Promise<UserManager> | undefined;
const manager = () => {
  managerPromise ??= loadConfig().then(
    (config) =>
      new UserManager({
        authority: config.oidcAuthority,
        client_id: config.oidcClientId,
        redirect_uri: `${window.location.origin}/auth/callback`,
        post_logout_redirect_uri: `${window.location.origin}/login`,
        response_type: "code",
        scope: "openid profile",
        monitorSession: false,
        automaticSilentRenew: false,
        stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
        userStore: new WebStorageStateStore({ store: new MemoryStorage() }),
      }),
  );
  return managerPromise;
};

export interface Session {
  user: User | null;
  loading: boolean;
  roles: string[];
  tenant: string | null;
  token: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  completeSignIn: () => Promise<User>;
}

const AuthContext = createContext<Session | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let disposed = false;
    let cleanup = () => undefined;
    void manager()
      .then(async (value) => {
        const current = await value.getUser();
        if (disposed) return;
        setUser(current?.expired ? null : current);
        const loaded = (next: User) => setUser(next);
        const unloaded = () => setUser(null);
        value.events.addUserLoaded(loaded);
        value.events.addUserUnloaded(unloaded);
        value.events.addAccessTokenExpired(unloaded);
        setLoading(false);
        cleanup = () => {
          value.events.removeUserLoaded(loaded);
          value.events.removeUserUnloaded(unloaded);
          value.events.removeAccessTokenExpired(unloaded);
        };
      })
      .catch(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
      cleanup();
    };
  }, []);
  const signIn = useCallback(
    async () => manager().then((value) => value.signinRedirect()),
    [],
  );
  const signOut = useCallback(
    async () => manager().then((value) => value.signoutRedirect()),
    [],
  );
  const completeSignIn = useCallback(async () => {
    const next = await manager().then((value) =>
      value.signinRedirectCallback(),
    );
    setUser(next);
    return next;
  }, []);
  const rolesValue = user?.profile.dusk_roles;
  const roles = useMemo(
    () =>
      Array.isArray(rolesValue)
        ? rolesValue.filter((role): role is string => typeof role === "string")
        : typeof rolesValue === "string"
          ? [rolesValue]
          : [],
    [rolesValue],
  );
  const value = useMemo<Session>(
    () => ({
      user,
      loading,
      roles,
      tenant:
        typeof user?.profile.dusk_tenant_id === "string"
          ? user.profile.dusk_tenant_id
          : null,
      token: user?.expired ? null : (user?.access_token ?? null),
      signIn,
      signOut,
      completeSignIn,
    }),
    [user, loading, roles, signIn, signOut, completeSignIn],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}

export const capabilitiesFor = (roles: string[]) => ({
  dashboard: roles.some((role) =>
    ["viewer", "analyst", "operator"].includes(role),
  ),
  decisions: roles.some((role) =>
    ["viewer", "analyst", "operator"].includes(role),
  ),
  decisionDetail: roles.some((role) => ["analyst", "operator"].includes(role)),
  agents: roles.some((role) => ["analyst", "operator"].includes(role)),
  policies: roles.includes("auditor"),
  integrations: roles.includes("operator"),
  backend: roles.includes("operator"),
  audit: roles.some((role) =>
    ["analyst", "operator", "auditor"].includes(role),
  ),
});

export function landingFor(roles: string[]) {
  const capabilities = capabilitiesFor(roles);
  if (capabilities.dashboard) return "/overview" as const;
  if (capabilities.audit) return "/audit" as const;
  if (capabilities.policies) return "/policies" as const;
  return "/forbidden" as const;
}
