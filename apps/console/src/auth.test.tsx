import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider, capabilitiesFor, landingFor, useAuth } from "./auth";

describe("role capability projection", () => {
  it("keeps viewers in summary-only surfaces", () => {
    expect(capabilitiesFor(["viewer"])).toEqual({
      dashboard: true,
      decisions: true,
      decisionDetail: false,
      agents: false,
      policies: false,
      integrations: false,
      backend: false,
      audit: false,
    });
  });

  it("allows combined investigators without inventing admin powers", () => {
    const result = capabilitiesFor(["analyst", "operator", "auditor"]);
    expect(result).toEqual({
      dashboard: true,
      decisions: true,
      decisionDetail: true,
      agents: true,
      policies: true,
      integrations: true,
      backend: true,
      audit: true,
    });
  });

  it("lands each role on its first permitted read-only surface", () => {
    expect(landingFor(["viewer"])).toBe("/overview");
    expect(landingFor(["auditor"])).toBe("/audit");
    expect(landingFor([])).toBe("/forbidden");
  });
});

describe("anonymous public demo session", () => {
  it("creates only the fixed synthetic viewer without an access token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          apiBaseUrl: "https://api.demo.example.com",
          oidcAuthority: "https://auth.demo.example.com/realms/dusk-demo",
          oidcClientId: "dusk-console",
          environmentLabel: "Public Demo",
          accessMode: "anonymous-demo",
        }),
      ),
    );
    const wrapper = ({ children }: { children: ReactNode }) => (
      <AuthProvider>{children}</AuthProvider>
    );

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.accessMode).toBe("anonymous-demo");
    expect(result.current.roles).toEqual(["viewer"]);
    expect(result.current.tenant).toBe("11111111-1111-4111-8111-111111111111");
    expect(result.current.token).toBeNull();
    fetchMock.mockRestore();
  });
});
