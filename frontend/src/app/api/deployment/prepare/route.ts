import { NextResponse } from 'next/server'
import { prepareDeployment } from '@/lib/trace/deploymentService'
import type { DeploymentConfig } from '@/lib/trace/traceTypes'

export async function POST(req: Request) {
  try {
    const body = await req.json() as Partial<DeploymentConfig>

    if (!body.company) {
      return NextResponse.json({ error: 'company is required' }, { status: 400 })
    }

    const config: DeploymentConfig = {
      company: body.company,
      agent_workflow_url: body.agent_workflow_url ?? '',
      api_access_type: body.api_access_type ?? 'read-only',
      database_type: body.database_type ?? 'postgres',
      tool_list: body.tool_list ?? [],
      manager_email: body.manager_email ?? '',
      allowed_actions: body.allowed_actions ?? [],
      blocked_actions: body.blocked_actions ?? [],
      test_environment_url: body.test_environment_url ?? '',
      deployment_mode: body.deployment_mode ?? 'shadow_monitoring',
    }

    const pkg = prepareDeployment(config)
    return NextResponse.json(pkg, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
