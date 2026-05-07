import type { Deposit } from '@/src/server/operations';

export function DepositsList({ deposits }: { deposits: Deposit[] }) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">Deposits</h2>
      <ul className="mt-3 space-y-3">
        {deposits.length === 0 ? <li className="text-sm text-slate-500">No deposits yet.</li> : null}
        {deposits.map((deposit) => (
          <li key={deposit.id} className="flex items-center justify-between rounded-xl bg-slate-50 p-3">
            <div>
              <p className="font-medium text-slate-900">
                {deposit.currency} {deposit.amount}
              </p>
              <p className="text-xs text-slate-500">{new Date(deposit.createdAt).toLocaleString()}</p>
            </div>
            <span className="rounded-full bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">{deposit.status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
