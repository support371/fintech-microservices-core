/**
 * POST /api/auth/logout
 * Clears the gem_token httpOnly cookie.
 */

import { NextResponse } from 'next/server';
import { clearAuthCookie } from '@/src/server/auth';

export const dynamic = 'force-dynamic';

export async function POST() {
  return NextResponse.json(
    { ok: true },
    { headers: { 'Set-Cookie': clearAuthCookie() } }
  );
}
