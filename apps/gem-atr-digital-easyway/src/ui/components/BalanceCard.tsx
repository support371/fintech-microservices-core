type BalanceCardProps = {
  available: number;
  pending: number;
};

export function BalanceCard({ available, pending }: BalanceCardProps) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">Balances</h2>
      <div className="mt-4 space-y-2">
        <p className="text-3xl font-bold text-slate-900">${available.toLocaleString()}</p>
        <p className="text-sm text-slate-500">Pending: ${pending.toLocaleString()}</p>
      </div>
    </section>
  );
}
