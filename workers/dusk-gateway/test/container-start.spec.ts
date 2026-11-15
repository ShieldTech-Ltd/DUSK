import { describe, expect, it, vi } from "vitest";
import { startRuntimeContainer } from "../src/runtime-do";

describe("runtime Container configuration", () => {
  it.each([undefined, "", "   "])("refuses to start without a signing key (%j)", (key) => {
    const start = vi.fn();
    expect(() => startRuntimeContainer({ running: false, start }, key)).toThrow("runtime signing key not configured");
    expect(start).not.toHaveBeenCalled();
  });

  it("passes only the signing key and disables outbound Internet", () => {
    const start = vi.fn();
    startRuntimeContainer({ running: false, start }, "test-signing-key");
    expect(start).toHaveBeenCalledExactlyOnceWith({
      enableInternet: false,
      env: { DUSK_SIGNING_KEY: "test-signing-key" },
    });
  });

  it("does not start an already running Container", () => {
    const start = vi.fn();
    startRuntimeContainer({ running: true, start }, "test-signing-key");
    expect(start).not.toHaveBeenCalled();
  });

  it("rejects missing configuration even if the Container is already running", () => {
    expect(() => startRuntimeContainer({ running: true, start: vi.fn() }, undefined)).toThrow();
  });
});
