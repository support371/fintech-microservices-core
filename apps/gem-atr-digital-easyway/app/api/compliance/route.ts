/**
 * /api/compliance — Proxy to compliance_service.
 * Returns governance sweep results + screening decisions for the dashboard.
 */

import { NextRequest, NextResponse } from 'next/server';
import { requireUser } from '@/src/server/auth';
import { getConfig } from '@/src/server/config';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    const user = requireUser();
    const { complianceServiceUrl, appMode } = getConfig();

    if (appMode === 'mock') {
      // Return deterministic mock compliance state
      return NextResponse.json({
        mode: 'mock',
        frameworks: ['COBIT_2019', 'COSO_ERM', 'GAO_AI_ACCOUNTABILITY', 'IIA_AI_AUDITING'],
        satisfiedControls: 16,
        totalControls: 16,
        chainIntegrity: true,
        lastSweep: new Date().toISOString(),
        controls: Array.from({ length: 16 }, (_, i) => ({
          id: `ctrl-${i + 1}`,
          status: 'satisfied',
          framework: ['COBIT_2019', 'COSO_ERM', 'GAO_AI_ACCOUNTABILITY', 'IIA_AI_AUDITING'][Math.floor(i / 4)],
        })),
      });
    }

    const res = await fetch(`${complianceServiceUrl}/sweep/status`, {
      headers: { 'X-User-Id': user.id, 'X-User-Role': user.role },
    });

    if (!res.ok) {
      return NextResponse.json({ error: 'Compliance service unavailable' }, { status: 502 });
    }

    return NextResponse.json(await res.json());
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Internal error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
