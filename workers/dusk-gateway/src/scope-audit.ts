interface AuditBindings {
  AUDIT_RECEIPTS: R2Bucket;
  DUSK_EVENTS: AnalyticsEngineDataset;
}

export async function scopeAudit(env: AuditBindings, phase: "preflight" | "execute", bytes: Uint8Array) {
  const traceId = crypto.randomUUID();
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  const requestHash = [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  async function write(decision: string, code: string, actionDigest?: string, upstreamStatus?: number) {
    const record = {
      trace_id: traceId, phase, request_hash: requestHash, decision, code,
      action_digest: actionDigest && /^[a-f0-9]{64}$/.test(actionDigest) ? actionDigest : null,
      upstream_status: upstreamStatus ?? null, timestamp_ms: Date.now(),
    };
    await env.AUDIT_RECEIPTS.put(`scope/${traceId}.json`, JSON.stringify(record), {
      httpMetadata: { contentType: "application/json" },
    });
    env.DUSK_EVENTS.writeDataPoint({ indexes: [traceId], blobs: [phase, decision, code, requestHash], doubles: [record.timestamp_ms] });
  }
  // A durable admission record must exist before any policy/permit/egress work.
  await write("PENDING", "admitted");
  return {
    traceId,
    async complete(result: { decision: string; code: string; action_digest?: string; upstream_status?: number }): Promise<boolean> {
      try {
        await write(result.decision, result.code, result.action_digest, result.upstream_status);
        return true;
      } catch {
        // The action may already have executed. Preserve its actual outcome.
        console.error(JSON.stringify({ event: "scope_audit_incomplete", trace_id: traceId }));
        return false;
      }
    },
  };
}
