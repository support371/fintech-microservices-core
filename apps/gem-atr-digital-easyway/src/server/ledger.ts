export type LedgerSnapshot = {
  availableUsd: number;
  pendingUsd: number;
  btcAmount: number;
};

export function getMockLedgerSnapshot(): LedgerSnapshot {
  return {
    availableUsd: 12540.33,
    pendingUsd: 250,
    btcAmount: 0.4231,
  };
}
