/**
 * POST /api/auth/login
 *
 * Body: { email: string; password: string }
 *
 * In APP_MODE=mock this always succeeds (use any credentials).
 * In staging/production, wire this to your user store / KYC provider.
 *
 * Returns: { user: AuthUser } + sets gem_token httpOnly cookie.
 */

import { NextRequest, NextResponse } from 'next/server';
import { signToken, buildAuthCookie } from '@/src/server/auth';
import { getConfig } from '@/src/server/config';
import { checkRateLimit } from '@/src/server/ratelimit';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const ip = req.headers.get('x-forwarded-for') ?? 'local';

  // Rate-limit: 10 login attempts per IP per 15 minutes
  const limited = checkRateLimit(`login:${ip}`, 10, 15 * 60_000);
  if (!limited.allowed) {
    return NextResponse.json({ error: 'Too many login attempts. Try again later.' }, { status: 429 });
  }

  const body = await req.json().catch(() => ({}));
  const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
  const password = typeof body.password === 'string' ? body.password : '';

  if (!email || !password) {
    return NextResponse.json({ error: 'email and password are required.' }, { status: 400 });
  }

  const { appMode } = getConfig();

  // ── Mock mode: accept any credentials ─────────────────────────────────────
  if (appMode === 'mock') {
    const role = email.startsWith('admin') ? 'admin' : 'user';
    const user = { id: `mock-${role}-1`, email, role } as const;
    const token = await signToken(user);
    return NextResponse.json(
      { user },
      { headers: { 'Set-Cookie': buildAuthCookie(token) } }
    );
  }

  // ── Staging / Production: wire your user store here ───────────────────────
  // Example: const user = await db.users.findByEmail(email);
  //          if (!user || !await bcrypt.compare(password, user.passwordHash)) { ... }
  //
  // For now we return a clear error rather than silently accepting anything.
  return NextResponse.json(
    { error: 'Production user store not yet wired. Set APP_MODE=mock for local development.' },
    { status: 501 }
  );
}
