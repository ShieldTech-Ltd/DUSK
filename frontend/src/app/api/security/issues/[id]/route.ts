import { NextResponse } from 'next/server'
import store from '@/lib/trace/traceStore'

export function GET(_req: Request, { params }: { params: { id: string } }) {
  const issue = store.getIssue(params.id)
  if (!issue) {
    return NextResponse.json({ error: `Issue ${params.id} not found` }, { status: 404 })
  }
  return NextResponse.json(issue)
}
