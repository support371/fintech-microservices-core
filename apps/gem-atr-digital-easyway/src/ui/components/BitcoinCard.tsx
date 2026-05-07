import type { CardStatus } from '@/src/server/operations';

type BitcoinCardProps = {
  status: CardStatus;
  nickname: string;
};

const statusClass: Record<CardStatus, string> = {
  requested: 'bg-amber-100 text-amber-700',
  issued: 'bg-emerald-100 text-emerald-700',
  frozen: 'bg-rose-100 text-rose-700',
};

export function BitcoinCard({ status, nickname }: BitcoinCardProps) {
  return (
    <section className="rounded-2xl bg-gradient-to-br from-slate-900 to-indigo-950 p-5 text-white shadow-xl">
      <p className="text-xs uppercase tracking-widest text-cyan-200">Bitcoin Card</p>
      <p className="mt-2 text-lg font-semibold">{nickname || 'GEM ATR Card'}</p>
      <span className={`mt-4 inline-flex rounded-full px-3 py-1 text-xs font-semibold ${statusClass[status]}`}>
        {status}
      </span>
    </section>
  );
}
