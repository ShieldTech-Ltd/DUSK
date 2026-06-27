import { randomUUID } from 'crypto'
import store from './traceStore'
import { writeAudit } from './auditService'
import type { DeploymentConfig, DeploymentPackage } from './traceTypes'

const PERMISSIONS_BY_MODE: Record<string, string[]> = {
  shadow_monitoring: [
    'read_agent_workflow',
    'read_api_schema',
    'read_database_schema',
    'create_policy_hook',
  ],
  approval_gate: [
    'read_agent_workflow',
    'read_api_schema',
    'read_database_schema',
    'create_policy_hook',
    'intercept_agent_actions',
    'send_approval_notifications',
  ],
  active_self_healing: [
    'read_agent_workflow',
    'write_agent_policy',
    'read_api_schema',
    'write_api_policy',
    'read_database_schema',
    'create_policy_hook',
    'intercept_agent_actions',
    'execute_remediation',
    'send_approval_notifications',
  ],
}

export function prepareDeployment(config: DeploymentConfig): DeploymentPackage {
  const deploymentId = `deploy_${randomUUID().slice(0, 8)}`
  const now = new Date().toISOString()

  const pkg: DeploymentPackage = {
    deployment_id: deploymentId,
    company: config.company,
    status: 'ready_for_manager_approval',
    mode: config.deployment_mode,
    required_permissions: PERMISSIONS_BY_MODE[config.deployment_mode] ?? PERMISSIONS_BY_MODE.shadow_monitoring,
    blocked_actions: config.blocked_actions,
    approval_required: true,
    manager_email: config.manager_email,
    generated_config: {
      monitoring_mode: config.deployment_mode.replace('_', ' '),
      approval_required: true,
      allowed_actions: config.allowed_actions,
      blocked_actions: config.blocked_actions,
    },
    connector_instructions: [
      `Connect ${config.company} agent workflow at ${config.agent_workflow_url || 'provided URL'} in test environment`,
      `Provide ${config.api_access_type || 'read-only'} API schema access`,
      `Provide ${config.database_type || 'database'} schema access (read-only)`,
      `Configure tool list: ${(config.tool_list ?? []).join(', ') || 'as provided'}`,
      `Attach approval manager: ${config.manager_email}`,
      `Deploy in ${config.deployment_mode} mode`,
    ],
    attio_payload: {
      object_type: 'deployment',
      company: config.company,
      deployment_id: deploymentId,
      mode: config.deployment_mode,
      status: 'ready_for_manager_approval',
      manager_email: config.manager_email,
      created_at: now,
    },
    created_at: now,
  }

  store.upsertDeployment(pkg)

  writeAudit(
    'deployment_prepared',
    `Deployment package prepared for ${config.company} in ${config.deployment_mode} mode`,
    'trace_deployment_service',
    { metadata: { deployment_id: deploymentId, mode: config.deployment_mode } }
  )

  return pkg
}

export function registerDeployment(deploymentId: string): DeploymentPackage | null {
  const pkg = store.getDeployment(deploymentId)
  if (!pkg) return null

  const updated: DeploymentPackage = { ...pkg, status: 'registered' }
  store.upsertDeployment(updated)

  writeAudit(
    'deployment_registered',
    `Deployment ${deploymentId} registered for ${pkg.company}`,
    'trace_deployment_service',
    { metadata: { deployment_id: deploymentId } }
  )

  return updated
}
