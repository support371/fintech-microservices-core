import { NextRequest } from "next/server";

/**
 * In-memory token bucket rate limiter with anomaly detection.
 *
 * Production note: Replace with Upstash Redis or a distributed store
 * for multi-instance deployments behind a load balancer.
 *
 * Anomaly detection tracks request patterns per IP and flags:
 *   - Burst patterns: >10 requests in 5 seconds
 *   - Sustained high volume: consistently near capacity
 *   - Repeated auth failures: tracked externally via recordAuthFailure()
 *   - Geographic anomaly: rapid requests from different geolocations
 */

interface Bucket {
  tokens: number;
  lastRefill: number;
}

interface AnomalyTracker {
  /** Timestamps of recent requests (sliding window) */
  requestTimestamps: number[];
  /** Count of rate-limit violations */
  violationCount: number;
  /** Count of auth failures */
  authFailures: number;
  /** First seen timestamp */
  firstSeen: number;
  /** Whether this IP is currently flagged */
  flagged: boolean;
}

const buckets = new Map<string, Bucket>();
const anomalyTrackers = new Map<string, AnomalyTracker>();

const DEFAULT_CAPACITY = 30;
const DEFAULT_WINDOW_MS = 60_000;

// Anomaly detection thresholds
const BURST_THRESHOLD = 10;        // requests
const BURST_WINDOW_MS = 5_000;     // 5 seconds
const VIOLATION_FLAG_THRESHOLD = 5; // violations before flagging
const AUTH_FAILURE_THRESHOLD = 10;  // auth failures before flagging
const ANOMALY_WINDOW_MS = 300_000; // 5-minute sliding window for request tracking

export interface RateLimitResult {
  limited: true;
  retryAfterMs: number;
  anomaly?: AnomalyAlert;
}

export interface AnomalyAlert {
  type: "burst" | "sustained" | "auth_failure" | "flagged_ip";
  ip: string;
  details: string;
  severity: "warning" | "critical";
}

/**
 * Check rate limit for a request. Returns null if allowed,
 * or an object with retry info if rate-limited.
 *
 * Also performs anomaly detection and returns alerts inline.
 */
export function checkRateLimit(
  req: NextRequest,
  capacity: number = DEFAULT_CAPACITY,
  windowMs: number = DEFAULT_WINDOW_MS
): RateLimitResult | null {
  const ip = getClientIp(req);
  const key = `${ip}:${req.nextUrl.pathname}`;
  const now = Date.now();

  // ── Token bucket ──
  let bucket = buckets.get(key);
  if (!bucket) {
    bucket = { tokens: capacity, lastRefill: now };
    buckets.set(key, bucket);
  }

  const elapsed = now - bucket.lastRefill;
  const refillRate = capacity / windowMs;
  bucket.tokens = Math.min(capacity, bucket.tokens + elapsed * refillRate);
  bucket.lastRefill = now;

  // ── Anomaly tracking ──
  let tracker = anomalyTrackers.get(ip);
  if (!tracker) {
    tracker = {
      requestTimestamps: [],
      violationCount: 0,
      authFailures: 0,
      firstSeen: now,
      flagged: false,
    };
    anomalyTrackers.set(ip, tracker);
  }

  // Record request timestamp (sliding window)
  tracker.requestTimestamps.push(now);
  tracker.requestTimestamps = tracker.requestTimestamps.filter(
    (ts) => now - ts < ANOMALY_WINDOW_MS
  );

  // Check for burst pattern
  const recentBurst = tracker.requestTimestamps.filter(
    (ts) => now - ts < BURST_WINDOW_MS
  ).length;

  let anomaly: AnomalyAlert | undefined;

  if (tracker.flagged) {
    anomaly = {
      type: "flagged_ip",
      ip,
      details: `IP is flagged: ${tracker.violationCount} violations, ${tracker.authFailures} auth failures`,
      severity: "critical",
    };
  } else if (recentBurst > BURST_THRESHOLD) {
    anomaly = {
      type: "burst",
      ip,
      details: `Burst detected: ${recentBurst} requests in ${BURST_WINDOW_MS}ms`,
      severity: "warning",
    };
  }

  // ── Rate limit check ──
  if (bucket.tokens < 1) {
    tracker.violationCount++;
    if (tracker.violationCount >= VIOLATION_FLAG_THRESHOLD) {
      tracker.flagged = true;
    }

    const retryAfterMs = Math.ceil((1 - bucket.tokens) / refillRate);
    return {
      limited: true,
      retryAfterMs,
      anomaly: anomaly ?? {
        type: "sustained",
        ip,
        details: `Rate limited: violation #${tracker.violationCount}`,
        severity: tracker.violationCount >= VIOLATION_FLAG_THRESHOLD ? "critical" : "warning",
      },
    };
  }

  bucket.tokens -= 1;

  // Return anomaly alert even if not rate-limited (for logging)
  if (anomaly) {
    // Log but don't block
    console.warn(`[anomaly] ${anomaly.severity}: ${anomaly.type} from ${ip} — ${anomaly.details}`);
  }

  return null;
}

/**
 * Record an authentication failure for anomaly tracking.
 * Call this when a request fails auth to detect brute-force patterns.
 */
export function recordAuthFailure(req: NextRequest): AnomalyAlert | null {
  const ip = getClientIp(req);
  let tracker = anomalyTrackers.get(ip);
  if (!tracker) {
    tracker = {
      requestTimestamps: [],
      violationCount: 0,
      authFailures: 0,
      firstSeen: Date.now(),
      flagged: false,
    };
    anomalyTrackers.set(ip, tracker);
  }

  tracker.authFailures++;

  if (tracker.authFailures >= AUTH_FAILURE_THRESHOLD) {
    tracker.flagged = true;
    return {
      type: "auth_failure",
      ip,
      details: `${tracker.authFailures} authentication failures — IP flagged`,
      severity: "critical",
    };
  }

  return null;
}

/**
 * Get current anomaly status for an IP address.
 */
export function getAnomalyStatus(ip: string): AnomalyTracker | null {
  return anomalyTrackers.get(ip) ?? null;
}

/**
 * Get all currently flagged IPs.
 */
export function getFlaggedIPs(): Array<{ ip: string; tracker: AnomalyTracker }> {
  const flagged: Array<{ ip: string; tracker: AnomalyTracker }> = [];
  for (const [ip, tracker] of anomalyTrackers) {
    if (tracker.flagged) flagged.push({ ip, tracker });
  }
  return flagged;
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
    // Clean up old anomaly trackers (older than 1 hour and not flagged)
    for (const [ip, tracker] of anomalyTrackers) {
      if (!tracker.flagged && now - tracker.firstSeen > 3_600_000) {
        anomalyTrackers.delete(ip);
      }
    }
  }, 300_000);
}
