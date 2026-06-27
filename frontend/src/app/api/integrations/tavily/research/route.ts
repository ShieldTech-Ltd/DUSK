import { NextResponse } from 'next/server'
import { tavilyResearch, tavilyEnrich } from '@/lib/trace/integrations/tavilyClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      query?: string
      agent_id?: string
      action_type?: string
      mitre_id?: string
      mode?: 'research' | 'enrich'
    }

    if (body.mode === 'enrich' || body.agent_id) {
      if (!body.agent_id || !body.action_type || !body.mitre_id) {
        return NextResponse.json(
          { error: 'agent_id, action_type, and mitre_id are required for enrich mode' },
          { status: 400 }
        )
      }
      const result = await tavilyEnrich(body.agent_id, body.action_type, body.mitre_id)
      return NextResponse.json(result)
    }

    if (!body.query) {
      return NextResponse.json({ error: 'query is required' }, { status: 400 })
    }

    const result = await tavilyResearch(body.query)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
