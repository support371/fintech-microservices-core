'use client';

import { useMemo, useState } from 'react';

import { AdminDashboard } from '@/src/ui/components/AdminDashboard';
import { BalanceCard } from '@/src/ui/components/BalanceCard';
import { Header } from '@/src/ui/components/Header';
import { NewDepositForm } from '@/src/ui/components/NewDepositForm';
import { UserDashboard } from '@/src/ui/components/UserDashboard';
import type { BitcoinCard, Deposit, OperationLog } from '@/src/server/operations';

export default function HomePage() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [toast, setToast] = useState('');
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [cards, setCards] = useState<BitcoinCard[]>([]);
  const [operations, setOperations] = useState<OperationLog[]>([]);

  const latestCard = cards[0];
  const available = deposits.filter((d) => d.status === 'settled').reduce((acc, d) => acc + d.amount, 0);
  const pending = deposits.filter((d) => d.status !== 'settled').reduce((acc, d) => acc + d.amount, 0);

  const addToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 2200);
  };

  const markReceived = () => {
    setDeposits((prev) => prev.map((deposit) => (deposit.status === 'created' ? { ...deposit, status: 'received' } : deposit)));
    addToast('Created deposits marked as received.');
  };

  const settleDeposits = () => {
    setDeposits((prev) => prev.map((deposit) => (deposit.status === 'received' ? { ...deposit, status: 'settled' } : deposit)));
    addToast('Received deposits settled.');
  };

  const requestCard = () => {
    if (cards.some((card) => card.status === 'requested' || card.status === 'issued')) {
      addToast('Only one requested/issued card is allowed.');
      return;
    }

    const card: BitcoinCard = {
      id: crypto.randomUUID(),
      userId: 'demo-user',
      nickname: 'Everyday BTC',
      status: 'requested',
      createdAt: new Date().toISOString(),
    };

    setCards((prev) => [card, ...prev]);
    setOperations((prev) => [
      { id: crypto.randomUUID(), operation: `card_requested:${card.id}`, actorId: 'demo-user', createdAt: new Date().toISOString() },
      ...prev,
    ]);
    addToast('Bitcoin card requested.');
  };

  const issueCard = () => {
    setCards((prev) => prev.map((card) => (card.status === 'requested' ? { ...card, status: 'issued' } : card)));
    addToast('Requested card issued.');
  };

  const freezeCard = () => {
    setCards((prev) => prev.map((card) => (card.status === 'issued' ? { ...card, status: 'frozen' } : card)));
    addToast('Issued card frozen.');
  };

  const createDeposit = ({ amount, currency }: { amount: number; currency: string }) => {
    if (!amount || amount <= 0) {
      addToast('Amount must be greater than zero.');
      return;
    }

    const deposit: Deposit = {
      id: crypto.randomUUID(),
      userId: 'demo-user',
      amount,
      currency,
      status: 'created',
      idempotencyKey: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
    };

    setDeposits((prev) => [deposit, ...prev]);
    setOperations((prev) => [
      { id: crypto.randomUUID(), operation: `deposit_created:${deposit.id}`, actorId: 'demo-user', createdAt: new Date().toISOString() },
      ...prev,
    ]);
    addToast('Deposit created.');
  };

  const operationPreview = useMemo(() => operations.slice(0, 5), [operations]);

  return (
    <main className="min-h-screen bg-slate-100 p-4 sm:p-8">
      <div className="mx-auto max-w-6xl">
        <Header isAdmin={isAdmin} setIsAdmin={setIsAdmin} />

        <div className="mb-5 grid gap-5 lg:grid-cols-3">
          <BalanceCard available={available} pending={pending} />
          <NewDepositForm onCreate={createDeposit} />
          <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">Actions</h2>
            <div className="mt-3 flex flex-col gap-3">
              <button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white" onClick={requestCard} type="button">
                Request bitcoin card
              </button>
              <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white" onClick={markReceived} type="button">
                Mark deposits received
              </button>
              <button className="rounded-lg bg-indigo-700 px-4 py-2 text-sm font-medium text-white" onClick={settleDeposits} type="button">
                Settle deposits
              </button>
              <button className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white" onClick={issueCard} type="button">
                Issue card
              </button>
              <button className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white" onClick={freezeCard} type="button">
                Freeze card
              </button>
            </div>
            <ul className="mt-4 space-y-2 text-xs text-slate-500">
              {operationPreview.map((op) => (
                <li key={op.id}>{op.operation}</li>
              ))}
            </ul>
          </section>
        </div>

        {isAdmin ? <AdminDashboard cards={cards} deposits={deposits} operations={operations} /> : <UserDashboard card={latestCard} deposits={deposits} />}
      </div>

      {toast ? <div className="fixed bottom-4 right-4 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white shadow-xl">{toast}</div> : null}
    </main>
  );
}
