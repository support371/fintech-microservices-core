/**
 * GET /api/auth/me
 * Returns the currently authenticated user or 401.
 * Used by the dashboard to bootstrap session state on load.
 */

import { NextResponse } from 'next/server';
import { requireUser, AuthError } from '@/src/server/auth';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const user = await requireUser();
    return NextResponse.json({ user });
  } catch (err) {
    if (err instanceof AuthError) {
      return NextResponse.json({ error: err.message }, { status: err.statusCode });
    }
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
}
