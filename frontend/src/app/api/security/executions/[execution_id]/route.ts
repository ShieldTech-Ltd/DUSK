import { NextResponse } from 'next/server'
import store from '@/lib/trace/traceStore'

export function GET(
  _req: Request,
  { params }: { params: { execution_id: string } }
) {
  const exec = store.getExecution(params.execution_id)
  if (!exec) {
    return NextResponse.json(
      { error: `Execution ${params.execution_id} not found` },
      { status: 404 }
    )
  }
  return NextResponse.json(exec)
}
