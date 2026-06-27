import { NextResponse } from 'next/server'
import { superlinkedMatch } from '@/lib/trace/integrations/superlinkedClient'
import type { SuperlinkedMatchRequest } from '@/lib/trace/integrations/superlinkedClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as SuperlinkedMatchRequest
    if (!body.company) {
      return NextResponse.json({ error: 'company is required' }, { status: 400 })
    }
    const result = await superlinkedMatch(body)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
