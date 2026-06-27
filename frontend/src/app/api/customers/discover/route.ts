import { NextResponse } from 'next/server'
import { discoverCustomers } from '@/lib/trace/customerDiscoveryService'

export async function POST(req: Request) {
  try {
    const body = await req.json() as { query?: string }
    const leads = discoverCustomers(body.query)
    return NextResponse.json(leads)
  } catch {
    // Also handle GET-style calls with no body
    return NextResponse.json(discoverCustomers())
  }
}

export function GET() {
  return NextResponse.json(discoverCustomers())
}
