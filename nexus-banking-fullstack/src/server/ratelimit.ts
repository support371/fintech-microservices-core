import { NextRequest } from "next/server";

/**
 * In-memory token bucket rate limiter.
 *
 * Production note: Replace with Upstash Redis or a distributed store
 * for multi-instance deployments behind a load balancer.
 */

interface Bucket {
  tokens: number;
  lastRefill: number;
}

const buckets = new Map<string, Bucket>();

const DEFAULT_CAPACITY = 30;
const DEFAULT_WINDOW_MS = 60_000;

/**
 * Check rate limit for a request. Returns null if allowed,
 * or an object with retry info if rate-limited.
 */
export function checkRateLimit(
  req: NextRequest,
  capacity: number = DEFAULT_CAPACITY,
  windowMs: number = DEFAULT_WINDOW_MS
): { limited: true; retryAfterMs: number } | null {
  const ip = getClientIp(req);
  const key = `${ip}:${req.nextUrl.pathname}`;
  const now = Date.now();

  let bucket = buckets.get(key);
  if (!bucket) {
    bucket = { tokens: capacity, lastRefill: now };
    buckets.set(key, bucket);
  }

  // Refill tokens based on elapsed time
  const elapsed = now - bucket.lastRefill;
  const refillRate = capacity / windowMs;
  bucket.tokens = Math.min(capacity, bucket.tokens + elapsed * refillRate);
  bucket.lastRefill = now;

  if (bucket.tokens < 1) {
    const retryAfterMs = Math.ceil((1 - bucket.tokens) / refillRate);
    return { limited: true, retryAfterMs };
  }

  bucket.tokens -= 1;
  return null;
}

function getClientIp(req: NextRequest): string {
  return (
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    req.headers.get("x-real-ip") ??
    "unknown"
  );
}

// Periodic cleanup to prevent memory leaks (every 5 minutes)
if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const now = Date.now();
    for (const [key, bucket] of buckets) {
      if (now - bucket.lastRefill > DEFAULT_WINDOW_MS * 2) {
        buckets.delete(key);
      }
    }
  }, 300_000);
}
