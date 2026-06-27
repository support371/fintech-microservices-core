/**
 * card_provider.ts — Card issuance provider adapter.
 * Returns mock data in 'mock' mode, calls real API in staging/production.
 */

import { getConfig } from '../config';

export type CardIssuanceResult = {
  success: boolean;
  providerCardId: string;
  maskedPan?: string;
  expiryDate?: string;
  provider: 'mock' | 'live';
  raw?: unknown;
};

export async function issueCardWithProvider(input: {
  userId: string;
  cardId: string;
  nickname: string;
}): Promise<CardIssuanceResult> {
  const { appMode, cardProviderApiKey } = getConfig();

  if (appMode === 'mock') {
    // Deterministic mock — no network call
    return {
      success: true,
      providerCardId: `mock-prov-${input.cardId.slice(0, 8)}`,
      maskedPan: '****  ****  ****  4242',
      expiryDate: '12/28',
      provider: 'mock',
    };
  }

  // Staging and production — call real card provider API
  const res = await fetch('https://api.card-provider.example.com/v1/cards', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${cardProviderApiKey}`,
      'Content-Type': 'application/json',
      'X-Idempotency-Key': input.cardId,
    },
    body: JSON.stringify({
      external_user_id: input.userId,
      external_card_id: input.cardId,
      card_name: input.nickname,
      type: 'virtual',
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Card provider error ${res.status}: ${text.slice(0, 200)}`);
  }

  const data = (await res.json()) as {
    card_id: string;
    masked_pan?: string;
    expiry?: string;
  };

  return {
    success: true,
    providerCardId: data.card_id,
    maskedPan: data.masked_pan,
    expiryDate: data.expiry,
    provider: 'live',
    raw: data,
  };
}
