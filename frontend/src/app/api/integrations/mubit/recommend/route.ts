import { NextResponse } from 'next/server'
import { mubitRecommend } from '@/lib/trace/integrations/mubitClient'
import type { MubitRecommendRequest } from '@/lib/trace/integrations/mubitClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as MubitRecommendRequest
    if (!body.task) {
      return NextResponse.json({ error: 'task is required' }, { status: 400 })
    }
    const result = await mubitRecommend(body)
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
