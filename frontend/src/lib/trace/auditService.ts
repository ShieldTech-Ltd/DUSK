import { randomUUID } from 'crypto'
import store from './traceStore'
import type { AuditEvent, AuditEventType } from './traceTypes'

export function writeAudit(
  event_type: AuditEventType,
  description: string,
  actor: string,
  opts: {
    issue_id?: string
    execution_id?: string
    metadata?: Record<string, string>
  } = {}
): AuditEvent {
  const event: AuditEvent = {
    id: `audit_${randomUUID()}`,
    timestamp: new Date().toISOString(),
    event_type,
    description,
    actor,
    ...opts,
  }
  store.addAudit(event)
  return event
}

export function getAudit(issueId?: string): AuditEvent[] {
  return store.getAudit(issueId)
}
