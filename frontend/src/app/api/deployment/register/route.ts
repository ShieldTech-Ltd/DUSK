import { NextResponse } from 'next/server'
import { registerDeployment } from '@/lib/trace/deploymentService'

export async function POST(req: Request) {
  try {
    const body = await req.json() as { deployment_id?: string }

    if (!body.deployment_id) {
      return NextResponse.json({ error: 'deployment_id is required' }, { status: 400 })
    }

    const pkg = registerDeployment(body.deployment_id)
    if (!pkg) {
      return NextResponse.json(
        { error: `Deployment ${body.deployment_id} not found` },
        { status: 404 }
      )
    }

    return NextResponse.json(pkg)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
