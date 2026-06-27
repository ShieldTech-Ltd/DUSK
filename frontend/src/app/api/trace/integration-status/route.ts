import { NextResponse } from 'next/server'
import { attioStatus } from '@/lib/trace/integrations/attioClient'
import { tavilyStatus } from '@/lib/trace/integrations/tavilyClient'
import { n8nStatus } from '@/lib/trace/integrations/n8nClient'
import { superlinkedStatus } from '@/lib/trace/integrations/superlinkedClient'
import { mubitStatus } from '@/lib/trace/integrations/mubitClient'
import { geminiStatus } from '@/lib/trace/integrations/geminiClient'
import { aikidoStatus } from '@/lib/trace/integrations/aikidoEvidence'

export function GET() {
  return NextResponse.json({
    attio: attioStatus(),
    tavily: tavilyStatus(),
    n8n: n8nStatus(),
    superlinked: superlinkedStatus(),
    mubit: mubitStatus(),
    gemini: geminiStatus(),
    aikido: aikidoStatus(),
  })
}
