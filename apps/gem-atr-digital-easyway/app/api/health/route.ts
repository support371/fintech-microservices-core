import { NextResponse } from 'next/server';

import { getConfig } from '@/src/server/config';

export function GET() {
  const config = getConfig();
  return NextResponse.json({
    ok: true,
    env: config.env,
    mockMode: config.mockMode,
    timestamp: new Date().toISOString(),
  });
}
