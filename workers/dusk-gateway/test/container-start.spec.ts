import { describe, expect, it, vi } from "vitest";
import { runtimeForwarder, startRuntimeContainer } from "../src/runtime-do";

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

describe("runtime readiness and forwarding", () => {
  function setup(fetch: ReturnType<typeof vi.fn>) {
    return runtimeForwarder({ running: true, start: vi.fn(), getTcpPort: () => ({ fetch }) as unknown as Fetcher }, () => "test-key");
  }

  it("retries refused and unhealthy GET probes before sending the action once", async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error("refused"))
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(Response.json({ decision: "ALLOW" }));
    await setup(fetch)("action-body");
    expect(fetch.mock.calls.map((call) => call[1].method)).toEqual(["GET", "GET", "GET", "POST"]);
    expect(fetch.mock.calls.slice(0, 3).every((call) => call[1].body === undefined)).toBe(true);
    expect(fetch.mock.calls[3]![1].body).toBe("action-body");
  });

  it("sends no action when readiness never succeeds, and allows a later retry", async () => {
    vi.useFakeTimers();
    try {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
    const forward = setup(fetch);
    const failed = expect(forward("secret-action")).rejects.toThrow("runtime readiness timeout");
    await vi.runAllTimersAsync();
    await failed;
    expect(fetch).toHaveBeenCalledTimes(20);
    expect(fetch.mock.calls.every((call) => call[1].method === "GET")).toBe(true);
    fetch.mockReset().mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(Response.json({ decision: "ALLOW" }));
    await forward("new-action");
    expect(fetch).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("shares readiness for concurrent actions and never retries a failed action", async () => {
    let ready!: (response: Response) => void;
    const probe = new Promise<Response>((resolve) => { ready = resolve; });
    const fetch = vi.fn().mockReturnValueOnce(probe).mockRejectedValue(new Error("lost response"));
    const forward = setup(fetch);
    const first = expect(forward("first")).rejects.toThrow("lost response");
    const second = expect(forward("second")).rejects.toThrow("lost response");
    expect(fetch).toHaveBeenCalledTimes(1);
    ready(new Response(null, { status: 200 }));
    await Promise.all([first, second]);
    expect(fetch.mock.calls.map((call) => call[1].method)).toEqual(["GET", "POST", "POST"]);
  });
});
