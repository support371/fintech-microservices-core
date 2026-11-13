import { NextRequest, NextResponse } from "next/server";
import { requireUser, AuthError } from "@/src/server/auth";
import { checkRateLimit } from "@/src/server/ratelimit";
import {
  handleAccessRequest,
  handleDeletionRequest,
  handleRectificationRequest,
  handlePortabilityRequest,
  createDSR,
  getDSRsByUser,
  PrivacyError,
} from "@/src/server/privacy";
import type { DSRType } from "@/src/server/privacy";

export const dynamic = "force-dynamic";

/**
 * GET /api/privacy — List the user's data subject requests.
 */
export async function GET(req: NextRequest) {
  try {
    const user = await requireUser(req);
    const requests = getDSRsByUser(user.id);
    return NextResponse.json({ requests });
  } catch (err) {
    return handleError(err);
  }
}

/**
 * POST /api/privacy — Submit a data subject request.
 *
 * Supports GDPR Articles 15-20 and CCPA data rights:
 *   - access:       Right of access (GDPR Art. 15 / CCPA Right to Know)
 *   - rectification: Right to rectification (GDPR Art. 16)
 *   - deletion:     Right to erasure (GDPR Art. 17 / CCPA Right to Delete)
 *   - portability:  Right to data portability (GDPR Art. 20)
 *   - restriction:  Right to restrict processing (GDPR Art. 18)
 *
 * Body: { type: DSRType, updates?: { full_name?: string, email?: string } }
 */
export async function POST(req: NextRequest) {
  try {
    const limited = checkRateLimit(req, 5, 60_000); // Strict: 5 req/min
    if (limited) {
      return NextResponse.json(
        { error: "Rate limit exceeded" },
        { status: 429, headers: { "Retry-After": String(Math.ceil(limited.retryAfterMs / 1000)) } }
      );
    }

    const user = await requireUser(req);
    const body = await req.json();

    const type = body.type as DSRType;
    const validTypes = new Set<DSRType>(["access", "rectification", "deletion", "portability", "restriction"]);
    if (!validTypes.has(type)) {
      return NextResponse.json(
        { error: `Invalid request type. Supported: ${[...validTypes].join(", ")}` },
        { status: 400 }
      );
    }

    // Create tracked DSR record
    const dsr = createDSR(user.id, type);

    switch (type) {
      case "access": {
        const data = await handleAccessRequest(user.id);
        dsr.status = "completed";
        dsr.completedAt = new Date().toISOString();
        return NextResponse.json({
          request: dsr,
          data,
          notice: "This export contains all personal data held by Nexus Financial. " +
            "Financial records required for regulatory compliance are included for transparency.",
        });
      }

      case "rectification": {
        const updates = body.updates;
        if (!updates || typeof updates !== "object") {
          return NextResponse.json(
            { error: "rectification requires 'updates' object with fields to correct" },
            { status: 400 }
          );
        }
        const result = await handleRectificationRequest(user.id, updates);
        dsr.status = "completed";
        dsr.completedAt = new Date().toISOString();
        return NextResponse.json({ request: dsr, result });
      }

      case "deletion": {
        const result = await handleDeletionRequest(user.id);
        dsr.status = "completed";
        dsr.completedAt = new Date().toISOString();
        return NextResponse.json({
          request: dsr,
          result,
          notice: "Personal identifiers have been anonymised. Financial records are retained " +
            "for the minimum period required by anti-money-laundering regulations (GDPR Art. 17(3)(b)).",
        });
      }

      case "portability": {
        const data = await handlePortabilityRequest(user.id);
        dsr.status = "completed";
        dsr.completedAt = new Date().toISOString();
        return NextResponse.json({
          request: dsr,
          data,
          format: "application/json",
          notice: "Data provided in machine-readable JSON format per GDPR Art. 20.",
        });
      }

      case "restriction": {
        // For restriction requests, we log the request but require manual processing
        dsr.status = "pending";
        return NextResponse.json({
          request: dsr,
          notice: "Your restriction request has been logged and will be reviewed within 30 days " +
            "per GDPR Art. 18. You will be notified by email when processing is complete.",
        });
      }
    }
  } catch (err) {
    return handleError(err);
  }
}

function handleError(err: unknown) {
  if (err instanceof AuthError) {
    return NextResponse.json({ error: err.message }, { status: 401 });
  }
  if (err instanceof PrivacyError) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
  console.error("[privacy]", err);
  return NextResponse.json({ error: "Internal server error" }, { status: 500 });
}
