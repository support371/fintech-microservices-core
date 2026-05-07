import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

import { requireAdmin } from '@/src/server/auth';
import { getOperations } from '@/src/server/operations';

export function GET() {
  requireAdmin();
  return NextResponse.json({ operations: getOperations(25) });
}
