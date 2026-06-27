import { NextResponse } from 'next/server'
import { getAikidoEvidence } from '@/lib/trace/integrations/aikidoEvidence'

export function GET() {
  const evidence = getAikidoEvidence()
  return NextResponse.json(evidence)
}
