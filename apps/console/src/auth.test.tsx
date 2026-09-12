import { describe, expect, it } from "vitest";
import { capabilitiesFor, landingFor } from "./auth";

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
