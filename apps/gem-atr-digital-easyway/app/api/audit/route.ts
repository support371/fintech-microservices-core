/**
 * /api/audit — Proxy to audit_service; admin-only.
 * Returns the most recent immutable audit log entries.
 */

import { NextRequest, NextResponse } from 'next/server';
import { requireAdmin } from '@/src/server/auth';
import { getConfig } from '@/src/server/config';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    requireAdmin();
    const { auditServiceUrl, appMode } = getConfig();
    const limit = Number(req.nextUrl.searchParams.get('limit') ?? '25');

    if (appMode === 'mock') {
      const now = new Date();
      return NextResponse.json({
        mode: 'mock',
        entries: Array.from({ length: Math.min(limit, 10) }, (_, i) => ({
          sequence_number: 57 - i,
          event_type: i === 0 ? 'system_event' : i === 3 ? 'sar_generated' : 'compliance_check',
          source_agent: ['GovernanceEngine', 'ReportingAgent', 'ScreeningAgent'][i % 3],
          timestamp: new Date(now.getTime() - i * 3_600_000).toISOString(),
          chain_valid: true,
        })),
        chain_integrity: true,
        verified_entries: 54,
        quarantined_entries: 2,
      });
    }

    const res = await fetch(`${auditServiceUrl}/entries?limit=${limit}`, {
      headers: { 'X-Admin': 'true' },
    });

    if (!res.ok) {
      return NextResponse.json({ error: 'Audit service unavailable' }, { status: 502 });
    }

    return NextResponse.json(await res.json());
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Internal error';
    const status = message.includes('role') || message.includes('Admin') ? 403 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
