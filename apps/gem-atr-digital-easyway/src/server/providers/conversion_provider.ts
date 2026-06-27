/**
 * conversion_provider.ts — Fiat-to-BTC conversion provider adapter.
 */

import { getConfig } from '../config';

export type ConversionResult = {
  success: boolean;
  btcAmount: number;
  exchangeRate: number;
  traceId: string;
  provider: 'mock' | 'live';
};

const MOCK_RATE = 65_000; // 1 BTC = $65,000 in mock

export async function convertFiatToBtc(input: {
  userId: string;
  depositId: string;
  amountUsd: number;
  traceId: string;
}): Promise<ConversionResult> {
  const { appMode, converterServiceSecret } = getConfig();

  if (appMode === 'mock') {
    const btcAmount = Math.round((input.amountUsd / MOCK_RATE) * 1e8) / 1e8;
    return {
      success: true,
      btcAmount,
      exchangeRate: MOCK_RATE,
      traceId: input.traceId,
      provider: 'mock',
    };
  }

  // Real converter service call (internal microservice)
  const res = await fetch(`${getConfig().complianceServiceUrl.replace('compliance-service:8001', 'converter-service:8003')}/internal/transfer_funds`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': converterServiceSecret,
      'X-Trace-Id': input.traceId,
    },
    body: JSON.stringify({
      user_id: input.userId,
      deposit_id: input.depositId,
      amount_usd: input.amountUsd,
      trace_id: input.traceId,
    }),
  });

  if (!res.ok) {
    throw new Error(`Converter service error ${res.status}`);
  }

  const data = (await res.json()) as {
    btc_amount: number;
    exchange_rate: number;
    trace_id: string;
  };

  return {
    success: true,
    btcAmount: data.btc_amount,
    exchangeRate: data.exchange_rate,
    traceId: data.trace_id,
    provider: 'live',
  };
}
