import type { BitcoinCard, Deposit } from '@/src/server/operations';

import { BitcoinCard as BitcoinCardPanel } from './BitcoinCard';
import { DepositsList } from './DepositsList';

export function UserDashboard({ deposits, card }: { deposits: Deposit[]; card?: BitcoinCard }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <DepositsList deposits={deposits} />
      {card ? <BitcoinCardPanel nickname={card.nickname} status={card.status} /> : <div className="rounded-2xl bg-white p-5 text-sm text-slate-500 shadow">No card requested yet.</div>}
    </div>
  );
}
