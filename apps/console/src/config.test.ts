import { describe, expect, it, vi } from "vitest";
import { validateConfig } from "./config";

const config = {
  apiBaseUrl: "https://api.example.com",
  oidcAuthority: "https://identity.example.com/realms/company",
  oidcClientId: "dusk-console",
  environmentLabel: "Company sandbox",
};

describe("deployment configuration", () => {
  it("accepts explicit HTTPS endpoints", () => {
    expect(validateConfig(config, "https://console.example.com")).toEqual(
      config,
    );
  });
  it.each([
    "http://api.example.com",
    "http://localhost:8080",
    "https://localhost:8080",
    "https://user:secret@api.example.com",
    "https://api.example.com?token=secret",
    "javascript:alert(1)",
  ])("rejects unsafe remote API endpoint %s", (apiBaseUrl) => {
    expect(() =>
      validateConfig({ ...config, apiBaseUrl }, "https://console.example.com"),
    ).toThrow();
  });
  it("permits loopback HTTP only on a local console", () => {
    expect(
      validateConfig(
        { ...config, apiBaseUrl: "http://localhost:8080" },
        "http://localhost:3000",
      ).apiBaseUrl,
    ).toBe("http://localhost:8080");
  });
  it.each([
    null,
    {},
    { ...config, oidcClientId: "" },
    { ...config, environmentLabel: "\n" },
    { ...config, environmentLabel: "x".repeat(129) },
    { ...config, clientSecret: "must-never-be-public" },
  ])("rejects malformed configuration", (value) => {
    expect(() =>
      validateConfig(value, "https://console.example.com"),
    ).toThrow();
  });

  it("loads configuration without following redirects or sending cross-origin credentials", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(config)));
    vi.resetModules();
    const { loadConfig } = await import("./config");
    await expect(loadConfig()).resolves.toEqual(config);
    expect(fetchMock).toHaveBeenCalledWith("/config.json", {
      cache: "no-store",
      credentials: "same-origin",
      redirect: "error",
    });
    fetchMock.mockRestore();
  });
});
