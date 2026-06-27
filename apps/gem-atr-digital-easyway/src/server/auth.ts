/**
 * auth.ts — JWT-based authentication for GEM ATR Dashboard.
 *
 * HOW IT WORKS
 * ─────────────────────────────────────────────────────────────
 * 1. Client obtains a signed JWT from /api/auth/login (email+password)
 *    or from your OAuth provider callback (Striga, Clerk, etc.).
 * 2. The JWT is stored in an httpOnly cookie named `gem_token`.
 * 3. Every server route calls requireUser() / requireAdmin() which
 *    reads the cookie, verifies the HS256 signature, and returns the
 *    typed AuthUser — or throws if invalid/missing.
 *
 * ENV VARS
 * ─────────────────────────────────────────────────────────────
 *   JWT_SECRET          — HS256 signing secret (min 32 chars, required in staging/prod)
 *   JWT_EXPIRY_HOURS    — Token lifetime in hours (default: 24)
 *   MOCK_USER_ROLE      — 'user' | 'admin'  (APP_MODE=mock only)
 *
 * UPGRADING TO CLERK
 * ─────────────────────────────────────────────────────────────
 * Replace the verifyJwt() call inside requireUser() with:
 *   import { auth } from '@clerk/nextjs/server';
 *   const { userId, sessionClaims } = auth();
 * The AuthUser shape stays the same — no other files need to change.
 */

import { SignJWT, jwtVerify, type JWTPayload } from 'jose';
import { cookies } from 'next/headers';
import { getConfig } from './config';

// ── Types ─────────────────────────────────────────────────────────────────────

export type UserRole = 'user' | 'admin';

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
}

interface GemJWTPayload extends JWTPayload {
  uid: string;
  email: string;
  role: UserRole;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const COOKIE_NAME = 'gem_token';
const DEFAULT_EXPIRY_HOURS = 24;

// ── Helpers ───────────────────────────────────────────────────────────────────

function getSecret(): Uint8Array {
  const secret = process.env.JWT_SECRET;
  if (!secret || secret.length < 32) {
    const { appMode } = getConfig();
    if (appMode !== 'mock') {
      throw new Error(
        'JWT_SECRET must be set and at least 32 characters in staging/production mode.'
      );
    }
    // In mock mode fall back to a dev-only secret
    return new TextEncoder().encode('gem-atr-dev-only-secret-change-me!');
  }
  return new TextEncoder().encode(secret);
}

function expiryHours(): number {
  const val = Number(process.env.JWT_EXPIRY_HOURS ?? DEFAULT_EXPIRY_HOURS);
  return Number.isFinite(val) && val > 0 ? val : DEFAULT_EXPIRY_HOURS;
}

// ── Token creation ────────────────────────────────────────────────────────────

/**
 * Sign a JWT for the given user. Call this in your login route after
 * verifying credentials, then set the result as an httpOnly cookie.
 */
export async function signToken(user: AuthUser): Promise<string> {
  const secret = getSecret();
  const expiresIn = `${expiryHours()}h`;

  return new SignJWT({
    uid: user.id,
    email: user.email,
    role: user.role,
  } satisfies Omit<GemJWTPayload, keyof JWTPayload>)
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .setSubject(user.id)
    .sign(secret);
}

// ── Token verification ────────────────────────────────────────────────────────

async function verifyJwt(token: string): Promise<AuthUser> {
  const secret = getSecret();
  const { payload } = await jwtVerify<GemJWTPayload>(token, secret);

  if (!payload.uid || !payload.email || !payload.role) {
    throw new Error('Malformed JWT payload — missing uid, email, or role.');
  }

  return {
    id: payload.uid,
    email: payload.email,
    role: payload.role,
  };
}

// ── Request-scoped auth ───────────────────────────────────────────────────────

/**
 * Returns the authenticated user or throws.
 * Safe to call in any Next.js Route Handler (App Router).
 */
export async function requireUser(): Promise<AuthUser> {
  const { appMode } = getConfig();

  // ── Mock mode ──────────────────────────────────────────────────────────────
  if (appMode === 'mock') {
    const role: UserRole =
      process.env.MOCK_USER_ROLE === 'admin' ? 'admin' : 'user';
    return {
      id: 'mock-user-1',
      email:
        role === 'admin' ? 'admin@gematr.local' : 'user@gematr.local',
      role,
    };
  }

  // ── Staging / Production ───────────────────────────────────────────────────
  const cookieStore = cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    throw new AuthError('No session token. Please log in.', 401);
  }

  try {
    return await verifyJwt(token);
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : 'Invalid or expired session.';
    throw new AuthError(msg, 401);
  }
}

/**
 * Returns the authenticated user only if they have the admin role.
 * Throws AuthError(403) for authenticated non-admin users.
 */
export async function requireAdmin(): Promise<AuthUser> {
  const user = await requireUser();
  if (user.role !== 'admin') {
    throw new AuthError('Admin role required.', 403);
  }
  return user;
}

// ── Cookie helpers ────────────────────────────────────────────────────────────

/**
 * Returns a Set-Cookie header string for the JWT token.
 * Use in login route responses.
 */
export function buildAuthCookie(token: string): string {
  const maxAge = expiryHours() * 3600;
  const { appMode } = getConfig();
  const secure = appMode === 'production' ? '; Secure' : '';
  return `${COOKIE_NAME}=${token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${maxAge}${secure}`;
}

/**
 * Returns a Set-Cookie header string that clears the auth cookie.
 * Use in logout route responses.
 */
export function clearAuthCookie(): string {
  return `${COOKIE_NAME}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0`;
}

// ── Error class ───────────────────────────────────────────────────────────────

export class AuthError extends Error {
  constructor(
    message: string,
    public readonly statusCode: 401 | 403 = 401
  ) {
    super(message);
    this.name = 'AuthError';
  }
}
