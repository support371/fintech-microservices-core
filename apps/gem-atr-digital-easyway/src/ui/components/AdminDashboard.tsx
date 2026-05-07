import type { BitcoinCard, Deposit, OperationLog } from '@/src/server/operations';

export function AdminDashboard({
  deposits,
  cards,
  operations,
}: {
  deposits: Deposit[];
  cards: BitcoinCard[];
  operations: OperationLog[];
}) {
  return (
    <section className="rounded-2xl bg-slate-900 p-5 text-white shadow-xl">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-cyan-200">Admin Dashboard</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-slate-800 p-4">
          <p className="text-xs text-slate-300">Deposits tracked</p>
          <p className="text-2xl font-bold">{deposits.length}</p>
        </div>
        <div className="rounded-xl bg-slate-800 p-4">
          <p className="text-xs text-slate-300">Cards tracked</p>
          <p className="text-2xl font-bold">{cards.length}</p>
        </div>
        <div className="rounded-xl bg-slate-800 p-4">
          <p className="text-xs text-slate-300">Operations</p>
          <p className="text-2xl font-bold">{operations.length}</p>
        </div>
      </div>
    </section>
  );
}
