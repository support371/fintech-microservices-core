'use client';

/**
 * page.tsx — Production-wired GEM ATR Dashboard.
 * Auth-gated: calls /api/auth/me on load; shows login screen if unauthenticated.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

type UserRole = 'user' | 'admin';
type AuthUser = { id: string; email: string; role: UserRole };
type Deposit = { id: string; amount: number; currency: string; status: string; createdAt: string };
type BitcoinCard = { id: string; status: string; nickname?: string };
type OperationLog = { id: string; operation: string; createdAt: string };
type LedgerSnapshot = { availableUsd: number; pendingUsd: number; btcAmount: number };
type ComplianceStatus = { satisfiedControls: number; totalControls: number; chainIntegrity: boolean; lastSweep: string };
type AuditEntry = { sequence_number: number; event_type: string; source_agent: string; timestamp: string; chain_valid: boolean };

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

function uid() { return crypto.randomUUID(); }
const fmt = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });

// ── Sub-components ────────────────────────────────────────────────────────────

function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-medium text-white shadow-2xl">
      {message}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-slate-500">{title}</h2>;
}

function Pill({ status }: { status: string }) {
  const map: Record<string, string> = {
    created: 'bg-yellow-100 text-yellow-800',
    received: 'bg-blue-100 text-blue-800',
    settled: 'bg-emerald-100 text-emerald-800',
    requested: 'bg-yellow-100 text-yellow-800',
    issued: 'bg-emerald-100 text-emerald-800',
    frozen: 'bg-rose-100 text-rose-800',
    satisfied: 'bg-emerald-100 text-emerald-800',
    failed: 'bg-rose-100 text-rose-800',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${map[status] ?? 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  );
}

function Btn({ label, onClick, color = 'slate', loading = false, full = false }: {
  label: string; onClick: () => void; color?: string; loading?: boolean; full?: boolean;
}) {
  const colors: Record<string, string> = {
    slate:   'bg-slate-900 text-white hover:bg-slate-800',
    indigo:  'bg-indigo-600 text-white hover:bg-indigo-700',
    emerald: 'bg-emerald-600 text-white hover:bg-emerald-700',
    rose:    'bg-rose-600   text-white hover:bg-rose-700',
  };
  return (
    <button
      className={`rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${colors[color] ?? colors.slate} ${full ? 'w-full' : ''}`}
      disabled={loading}
      onClick={onClick}
      type="button"
    >
      {loading ? 'Working…' : label}
    </button>
  );
}

// ── Login Screen ──────────────────────────────────────────────────────────────

function LoginScreen({ onLogin }: { onLogin: (u: AuthUser) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await apiFetch<{ user: AuthUser }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      onLogin(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-8 shadow ring-1 ring-slate-100"
      >
        <div>
          <h1 className="text-xl font-bold text-slate-900">GEM ATR Digital</h1>
          <p className="mt-1 text-xs text-slate-500">Sign in to your account</p>
        </div>

        {error && (
          <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
        )}

        <div className="space-y-3">
          <input
            autoComplete="email"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            onChange={e => setEmail(e.target.value)}
            placeholder="Email"
            required
            type="email"
            value={email}
          />
          <input
            autoComplete="current-password"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            required
            type="password"
            value={password}
          />
        </div>

        <button
          className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition"
          disabled={loading}
          type="submit"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="text-center text-xs text-slate-400">
          In mock mode, any email/password is accepted.
        </p>
      </form>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

function Dashboard({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const isAdmin = user.role === 'admin';
  const [toast, setToast] = useState('');
  const [loading, setLoading] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [deposits, setDeposits]       = useState<Deposit[]>([]);
  const [cards, setCards]             = useState<BitcoinCard[]>([]);
  const [operations, setOperations]   = useState<OperationLog[]>([]);
  const [ledger, setLedger]           = useState<LedgerSnapshot>({ availableUsd: 0, pendingUsd: 0, btcAmount: 0 });
  const [compliance, setCompliance]   = useState<ComplianceStatus | null>(null);
  const [auditLog, setAuditLog]       = useState<AuditEntry[]>([]);
  const [depositAmount, setDepositAmount] = useState('');
  const [depositCurrency, setDepositCurrency] = useState('USD');

  const notify = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 2800);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const [dep, cds] = await Promise.all([
        apiFetch<{ deposits: Deposit[] }>('/api/deposits'),
        apiFetch<{ cards: BitcoinCard[] }>('/api/cards'),
      ]);
      setDeposits(dep.deposits);
      setCards(cds.cards);

      const available = dep.deposits.filter(d => d.status === 'settled').reduce((a, d) => a + d.amount, 0);
      const pending   = dep.deposits.filter(d => d.status !== 'settled').reduce((a, d) => a + d.amount, 0);
      setLedger(prev => ({ ...prev, availableUsd: available, pendingUsd: pending }));

      if (isAdmin) {
        const ops = await apiFetch<{ operations: OperationLog[] }>('/api/admin/operations');
        setOperations(ops.operations);
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Failed to load data');
    }
  }, [isAdmin, notify]);

  const refreshCompliance = useCallback(async () => {
    try {
      setCompliance(await apiFetch<ComplianceStatus>('/api/compliance'));
    } catch { /* non-critical */ }
  }, []);

  const refreshAudit = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const data = await apiFetch<{ entries: AuditEntry[] }>('/api/audit?limit=10');
      setAuditLog(data.entries ?? []);
    } catch { /* non-critical */ }
  }, [isAdmin]);

  useEffect(() => { void refreshAll(); void refreshCompliance(); void refreshAudit(); }, [refreshAll, refreshCompliance, refreshAudit]);
  useEffect(() => { const id = setInterval(() => void refreshAll(), 30_000); return () => clearInterval(id); }, [refreshAll]);

  const handleCreateDeposit = async () => {
    const amount = parseFloat(depositAmount);
    if (!amount || amount <= 0) { notify('Enter a valid amount'); return; }
    setLoading(true);
    try {
      await apiFetch('/api/deposits', {
        method: 'POST',
        body: JSON.stringify({ amount, currency: depositCurrency, idempotency_key: uid() }),
      });
      setDepositAmount('');
      await refreshAll();
      notify('Deposit created.');
    } catch (err) { notify(err instanceof Error ? err.message : 'Deposit failed'); }
    finally { setLoading(false); }
  };

  const handleRequestCard = async () => {
    setLoading(true);
    try {
      await apiFetch('/api/cards', {
        method: 'POST',
        body: JSON.stringify({ nickname: 'GEM ATR Card', idempotency_key: uid() }),
      });
      await refreshAll();
      notify('Card requested and provisioned.');
    } catch (err) { notify(err instanceof Error ? err.message : 'Card request failed'); }
    finally { setLoading(false); }
  };

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
    onLogout();
  };

  const latestCard = cards[0];

  return (
    <main className="min-h-screen bg-slate-100 p-4 sm:p-8">
      <div className="mx-auto max-w-6xl space-y-6">

        {/* Header */}
        <header className="flex items-center justify-between rounded-2xl bg-white px-6 py-4 shadow ring-1 ring-slate-100">
          <div>
            <h1 className="text-xl font-bold text-slate-900">GEM ATR Digital</h1>
            <p className="text-xs text-slate-500">{user.email} · {user.role}</p>
          </div>
          <div className="flex items-center gap-3">
            {compliance && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${compliance.chainIntegrity ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                {compliance.satisfiedControls}/{compliance.totalControls} Controls
              </span>
            )}
            <button
              onClick={() => void handleLogout()}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 transition"
              type="button"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Stats */}
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Available USD" value={fmt(ledger.availableUsd)} sub="Settled deposits" />
          <StatCard label="Pending USD"   value={fmt(ledger.pendingUsd)}   sub="Awaiting settlement" />
          <StatCard label="BTC Balance"   value={`${ledger.btcAmount.toFixed(8)} BTC`} sub="Converted holdings" />
        </div>

        {/* Actions */}
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
            <SectionHeader title="New Deposit" />
            <div className="flex gap-2">
              <input
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-400"
                onChange={e => setDepositAmount(e.target.value)}
                placeholder="Amount"
                type="number"
                value={depositAmount}
              />
              <select
                className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
                onChange={e => setDepositCurrency(e.target.value)}
                value={depositCurrency}
              >
                <option>USD</option><option>EUR</option><option>GBP</option>
              </select>
              <Btn color="indigo" label="Deposit" loading={loading} onClick={() => void handleCreateDeposit()} />
            </div>
          </section>

          <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
            <SectionHeader title="Card Management" />
            <Btn label="Request Bitcoin Card" loading={loading} onClick={() => void handleRequestCard()} />
            {latestCard && (
              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Card: <span className="font-mono">{latestCard.id.slice(0, 12)}…</span>{' '}
                <Pill status={latestCard.status} />
              </div>
            )}
          </section>
        </div>

        {/* Deposits */}
        <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
          <SectionHeader title={`Deposits (${deposits.length})`} />
          {deposits.length === 0 ? (
            <p className="text-sm text-slate-400">No deposits yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b text-xs text-slate-400">
                    <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Amount</th>
                    <th className="pb-2 pr-4">Currency</th><th className="pb-2 pr-4">Status</th>
                    <th className="pb-2">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {deposits.map(d => (
                    <tr key={d.id} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-mono text-xs text-slate-500">{d.id.slice(0, 8)}…</td>
                      <td className="py-2 pr-4 font-semibold">{fmt(d.amount)}</td>
                      <td className="py-2 pr-4">{d.currency}</td>
                      <td className="py-2 pr-4"><Pill status={d.status} /></td>
                      <td className="py-2 text-slate-500">{new Date(d.createdAt).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Admin panels */}
        {isAdmin && (
          <>
            <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
              <SectionHeader title="Operations Log" />
              {operations.length === 0 ? (
                <p className="text-sm text-slate-400">No operations yet.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-600">
                  {operations.slice(0, 15).map(op => (
                    <li key={op.id} className="flex justify-between border-b py-1 last:border-0">
                      <span className="font-mono">{op.operation}</span>
                      <span className="text-slate-400">{new Date(op.createdAt).toLocaleTimeString()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {compliance && (
              <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
                <SectionHeader title="Compliance Status" />
                <div className="grid gap-3 sm:grid-cols-3">
                  <StatCard label="Controls Satisfied" value={`${compliance.satisfiedControls}/${compliance.totalControls}`} sub="COBIT · COSO · GAO · IIA" />
                  <StatCard label="Chain Integrity" value={compliance.chainIntegrity ? '✓ Valid' : '✗ Broken'} sub="Immutable audit chain" />
                  <StatCard label="Last Sweep" value={new Date(compliance.lastSweep).toLocaleTimeString()} sub={new Date(compliance.lastSweep).toLocaleDateString()} />
                </div>
              </section>
            )}

            {auditLog.length > 0 && (
              <section className="rounded-2xl bg-white p-5 shadow ring-1 ring-slate-100">
                <SectionHeader title="Immutable Audit Log (last 10)" />
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b text-slate-400">
                        <th className="pb-2 pr-4">Seq</th><th className="pb-2 pr-4">Event</th>
                        <th className="pb-2 pr-4">Agent</th><th className="pb-2 pr-4">Chain</th>
                        <th className="pb-2">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLog.map(e => (
                        <tr key={e.sequence_number} className="border-b last:border-0">
                          <td className="py-1.5 pr-4 font-mono">{e.sequence_number}</td>
                          <td className="py-1.5 pr-4 text-slate-600">{e.event_type}</td>
                          <td className="py-1.5 pr-4 text-slate-500">{e.source_agent}</td>
                          <td className="py-1.5 pr-4"><Pill status={e.chain_valid ? 'satisfied' : 'failed'} /></td>
                          <td className="py-1.5 text-slate-400">{new Date(e.timestamp).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}
      </div>
      <Toast message={toast} />
    </main>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [user, setUser]   = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Bootstrap: check for existing session on page load
  useEffect(() => {
    apiFetch<{ user: AuthUser }>('/api/auth/me')
      .then(data => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100">
        <p className="text-sm text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen onLogin={setUser} />;
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} />;
}
