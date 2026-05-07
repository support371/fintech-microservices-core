'use client';

import { useState } from 'react';

type NewDepositFormProps = {
  onCreate: (payload: { amount: number; currency: string }) => void;
};

export function NewDepositForm({ onCreate }: NewDepositFormProps) {
  const [amount, setAmount] = useState('250');
  const [currency, setCurrency] = useState('USD');

  return (
    <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">New Deposit</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <input
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          min="1"
          onChange={(event) => setAmount(event.target.value)}
          type="number"
          value={amount}
        />
        <select
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          onChange={(event) => setCurrency(event.target.value)}
          value={currency}
        >
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="GBP">GBP</option>
        </select>
        <button
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
          onClick={() => onCreate({ amount: Number(amount), currency })}
          type="button"
        >
          Create deposit
        </button>
      </div>
    </section>
  );
}
