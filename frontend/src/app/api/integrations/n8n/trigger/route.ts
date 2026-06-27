import { NextResponse } from 'next/server'
import { n8nTrigger } from '@/lib/trace/integrations/n8nClient'
import type { N8nTriggerPayload } from '@/lib/trace/integrations/n8nClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as N8nTriggerPayload
    const result = await n8nTrigger(body)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
