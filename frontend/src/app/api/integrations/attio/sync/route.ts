import { NextResponse } from 'next/server'
import { attioSync } from '@/lib/trace/integrations/attioClient'
import type { AttioSyncPayload } from '@/lib/trace/integrations/attioClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as AttioSyncPayload
    if (!body.object_type) {
      return NextResponse.json({ error: 'object_type is required' }, { status: 400 })
    }
    const result = await attioSync(body)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
