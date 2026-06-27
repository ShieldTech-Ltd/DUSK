/**
 * In-memory store for the Trace execution layer.
 *
 * Uses a module-level singleton that persists for the lifetime of the
 * Next.js server process. Resets on server restart — documented behavior
 * for the hackathon MVP.
 *
 * Production upgrade: swap this module for a Redis/Postgres adapter
 * without changing any of the service or route files.
 */

import type {
  TraceIssue,
  ExecutionPlan,
  Approval,
  Execution,
  AuditEvent,
  DeploymentPackage,
  CustomerLead,
} from './traceTypes'
import { MOCK_ISSUES, MOCK_PLANS, SEED_AUDIT, MOCK_LEADS } from './mockData'

class TraceStore {
  issues = new Map<string, TraceIssue>()
  plans = new Map<string, ExecutionPlan>()
  approvals = new Map<string, Approval>()
  executions = new Map<string, Execution>()
  auditEvents: AuditEvent[] = []
  deployments = new Map<string, DeploymentPackage>()
  customerLeads: CustomerLead[] = []
  sponsorResults = new Map<string, unknown>()

  constructor() {
    MOCK_ISSUES.forEach(i => this.issues.set(i.id, i))
    MOCK_PLANS.forEach(p => this.plans.set(p.plan_id, p))
    this.auditEvents = [...SEED_AUDIT]
    this.customerLeads = [...MOCK_LEADS]
  }

  // ── Issues ─────────────────────────────────────────────────────────────────

  getIssues(): TraceIssue[] {
    return Array.from(this.issues.values())
  }

  getIssue(id: string): TraceIssue | undefined {
    return this.issues.get(id)
  }

  upsertIssue(issue: TraceIssue): void {
    this.issues.set(issue.id, issue)
  }

  // ── Plans ──────────────────────────────────────────────────────────────────

  getPlan(planId: string): ExecutionPlan | undefined {
    return this.plans.get(planId)
  }

  getPlanByIssue(issueId: string): ExecutionPlan | undefined {
    return Array.from(this.plans.values()).find(p => p.issue_id === issueId)
  }

  upsertPlan(plan: ExecutionPlan): void {
    this.plans.set(plan.plan_id, plan)
  }

  // ── Approvals ──────────────────────────────────────────────────────────────

  getApproval(approvalId: string): Approval | undefined {
    return this.approvals.get(approvalId)
  }

  getApprovalByIssue(issueId: string): Approval | undefined {
    return Array.from(this.approvals.values()).find(a => a.issue_id === issueId)
  }

  upsertApproval(approval: Approval): void {
    this.approvals.set(approval.approval_id, approval)
  }

  // ── Executions ─────────────────────────────────────────────────────────────

  getExecution(execId: string): Execution | undefined {
    return this.executions.get(execId)
  }

  upsertExecution(exec: Execution): void {
    this.executions.set(exec.execution_id, exec)
  }

  // ── Audit ──────────────────────────────────────────────────────────────────

  addAudit(event: AuditEvent): void {
    this.auditEvents.unshift(event)
  }

  getAudit(issueId?: string): AuditEvent[] {
    if (!issueId) return this.auditEvents
    return this.auditEvents.filter(e => e.issue_id === issueId)
  }

  // ── Deployments ────────────────────────────────────────────────────────────

  upsertDeployment(d: DeploymentPackage): void {
    this.deployments.set(d.deployment_id, d)
  }

  getDeployment(id: string): DeploymentPackage | undefined {
    return this.deployments.get(id)
  }

  // ── Customer leads ─────────────────────────────────────────────────────────

  getLeads(): CustomerLead[] {
    return this.customerLeads
  }

  addLead(lead: CustomerLead): void {
    this.customerLeads.push(lead)
  }
}

// Singleton — one instance per Next.js server process
const store = new TraceStore()
export default store
