/**
 * Execution state machine for the Trace security fix workflow.
 *
 * Valid transitions:
 *   detected → planned → approval_requested → approved → resource_allocated
 *              → executing → fixed | failed | needs_manual_review | rejected
 */

import type { ExecutionStatus } from './traceTypes'

const TRANSITIONS: Record<ExecutionStatus, ExecutionStatus[]> = {
  detected:             ['planned'],
  planned:              ['approval_requested', 'approved'],
  approval_requested:   ['approved', 'rejected', 'needs_manual_review'],
  approved:             ['resource_allocated'],
  resource_allocated:   ['executing'],
  executing:            ['fixed', 'failed', 'needs_manual_review'],
  fixed:                [],
  failed:               ['planned'],
  needs_manual_review:  ['planned', 'rejected'],
  rejected:             [],
}

export function canTransition(from: ExecutionStatus, to: ExecutionStatus): boolean {
  return TRANSITIONS[from]?.includes(to) ?? false
}

export function transition(
  current: ExecutionStatus,
  next: ExecutionStatus
): { ok: true; status: ExecutionStatus } | { ok: false; error: string } {
  if (canTransition(current, next)) {
    return { ok: true, status: next }
  }
  return {
    ok: false,
    error: `Cannot transition from '${current}' to '${next}'. Allowed: ${TRANSITIONS[current]?.join(', ') || 'none'}`,
  }
}
