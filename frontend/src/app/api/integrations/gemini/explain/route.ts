import { NextResponse } from 'next/server'
import { geminiExplain } from '@/lib/trace/integrations/geminiClient'
import type { GeminiExplainRequest } from '@/lib/trace/integrations/geminiClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as GeminiExplainRequest
    if (!body.issue_id || !body.issue_summary) {
      return NextResponse.json(
        { error: 'issue_id and issue_summary are required' },
        { status: 400 }
      )
    }
    const result = await geminiExplain(body)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
