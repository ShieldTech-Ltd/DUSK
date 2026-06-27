import { NextResponse } from 'next/server'
import { executeFix } from '@/lib/trace/fixExecutor'
import type { FixRequest } from '@/lib/trace/fixExecutor'

export async function POST(req: Request) {
  try {
    const body = await req.json() as FixRequest

    if (!body.issue_id) {
      return NextResponse.json({ error: 'issue_id is required' }, { status: 400 })
    }

    const result = executeFix(body)

    const statusCode = result.status === 'fixed' ? 200
      : result.status === 'needs_manual_review' ? 422
      : 500

    return NextResponse.json(result, { status: statusCode })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
