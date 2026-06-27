import { NextResponse } from 'next/server'

export function GET() {
  return NextResponse.json({
    service: 'Trace Backend Execution Layer',
    status: 'ok',
    mode: process.env.TRACE_MODE ?? 'demo',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
  })
}
