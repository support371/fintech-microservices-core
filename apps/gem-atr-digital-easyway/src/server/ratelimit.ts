/**
 * ratelimit.ts — Simple in-process rate limiter (sliding window).
 *
 * Production upgrade path: swap this for Upstash Redis rate limiting.
 * The interface is identical — only the storage backend changes.
 *
 * Usage:
 *   const result = checkRateLimit('login:1.2.3.4', 10, 60_000);
 *   if (!result.allowed) return 429;
 */

interface WindowEntry {
  count: number;
  windowStart: number;
}

// In-memory store — resets on server restart (acceptable for mock/staging)
const store = new Map<string, WindowEntry>();

/**
 * @param key        Unique key (e.g. `login:<ip>`, `cards:<userId>`)
 * @param maxCalls   Max calls allowed within windowMs
 * @param windowMs   Window duration in milliseconds
 * @returns          { allowed: boolean; remaining: number; resetAt: number }
 */
export function checkRateLimit(
  key: string,
  maxCalls: number,
  windowMs: number
): { allowed: boolean; remaining: number; resetAt: number } {
  const now = Date.now();
  const entry = store.get(key);

  // Start a fresh window
  if (!entry || now - entry.windowStart >= windowMs) {
    store.set(key, { count: 1, windowStart: now });
    return { allowed: true, remaining: maxCalls - 1, resetAt: now + windowMs };
  }

  if (entry.count >= maxCalls) {
    return {
      allowed: false,
      remaining: 0,
      resetAt: entry.windowStart + windowMs,
    };
  }

  entry.count += 1;
  return {
    allowed: true,
    remaining: maxCalls - entry.count,
    resetAt: entry.windowStart + windowMs,
  };
}

/**
 * Prune stale entries to avoid unbounded memory growth.
 * Call periodically in long-running servers (not needed on serverless).
 */
export function pruneRateLimitStore(windowMs: number): number {
  const now = Date.now();
  let pruned = 0;
  for (const [key, entry] of store.entries()) {
    if (now - entry.windowStart >= windowMs) {
      store.delete(key);
      pruned++;
    }
  }
  return pruned;
}
