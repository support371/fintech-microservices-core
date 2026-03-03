"use client";

import { useState, useEffect, useCallback } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Account {
  id: string;
  currency: string;
  account_type: string;
  balance: number;
  available_balance: number;
}

interface Deposit {
  id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

interface Card {
  id: string;
  card_number_masked: string;
  card_type: string;
  status: string;
  daily_limit: number;
  monthly_limit: number;
}

interface ExchangeOrder {
  id: string;
  fiat_amount: number;
  fiat_currency: string;
  btc_amount: number;
  exchange_rate: number;
  status: string;
  created_at: string;
}

interface Transfer {
  id: string;
  from_account_id: string;
  to_account_id: string;
  amount: number;
  currency: string;
  status: string;
  description: string;
  created_at: string;
}

type Tab = "overview" | "deposit" | "transfer" | "exchange" | "cards";

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

function generateKey(): string {
  return `k-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Currency formatting
// ─────────────────────────────────────────────────────────────────────────────

function formatAmount(amount: number, currency: string): string {
  if (currency === "BTC") {
    return `${amount.toFixed(8)} BTC`;
  }
  const symbol = { USD: "$", EUR: "\u20AC", GBP: "\u00A3" }[currency] ?? currency;
  return `${symbol}${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function statusBadge(status: string): string {
  switch (status) {
    case "completed":
    case "active":
    case "approved":
    case "sent":
      return "badge-success";
    case "pending":
    case "processing":
    case "requested":
    case "issued":
      return "badge-warning";
    case "failed":
    case "rejected":
    case "frozen":
    case "cancelled":
      return "badge-error";
    default:
      return "badge-info";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [exchangeOrders, setExchangeOrders] = useState<ExchangeOrder[]>([]);
  const [rates, setRates] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Deposit form
  const [depAccountId, setDepAccountId] = useState("");
  const [depAmount, setDepAmount] = useState("");
  const [depCurrency, setDepCurrency] = useState("USD");

  // Transfer form
  const [txFromId, setTxFromId] = useState("");
  const [txToId, setTxToId] = useState("");
  const [txAmount, setTxAmount] = useState("");
  const [txCurrency, setTxCurrency] = useState("USD");

  // Exchange form
  const [exchAmount, setExchAmount] = useState("");
  const [exchCurrency, setExchCurrency] = useState("USD");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const [acctRes, depRes, cardRes, exchRates] = await Promise.all([
        api<{ accounts: Account[] }>("/api/accounts"),
        api<{ deposits: Deposit[] }>("/api/deposits"),
        api<{ cards: Card[] }>("/api/cards"),
        api<{ rates: Record<string, number> }>("/api/exchange"),
      ]);
      setAccounts(acctRes.accounts);
      setDeposits(depRes.deposits);
      setCards(cardRes.cards);
      setRates(exchRates.rates);

      if (acctRes.accounts.length > 0) {
        if (!depAccountId) setDepAccountId(acctRes.accounts[0].id);
        if (!txFromId) setTxFromId(acctRes.accounts[0].id);
        if (acctRes.accounts.length > 1 && !txToId) setTxToId(acctRes.accounts[1].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [depAccountId, txFromId, txToId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(""), 4000);
  };

  // ── Deposit ──
  const handleDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api("/api/deposits", {
        method: "POST",
        body: JSON.stringify({
          account_id: depAccountId,
          amount: parseFloat(depAmount),
          currency: depCurrency,
          idempotency_key: generateKey(),
        }),
      });
      setDepAmount("");
      showSuccess("Deposit created successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deposit failed");
    }
  };

  // ── Transfer ──
  const handleTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api("/api/transfers", {
        method: "POST",
        body: JSON.stringify({
          from_account_id: txFromId,
          to_account_id: txToId,
          amount: parseFloat(txAmount),
          currency: txCurrency,
          idempotency_key: generateKey(),
          description: "Dashboard transfer",
        }),
      });
      setTxAmount("");
      showSuccess("Transfer completed successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transfer failed");
    }
  };

  // ── Exchange ──
  const handleExchange = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api<{ order: ExchangeOrder }>("/api/exchange", {
        method: "POST",
        body: JSON.stringify({
          fiat_amount: parseFloat(exchAmount),
          fiat_currency: exchCurrency,
          idempotency_key: generateKey(),
        }),
      });
      setExchAmount("");
      setExchangeOrders((prev) => [res.order, ...prev]);
      showSuccess(
        `Exchanged ${formatAmount(res.order.fiat_amount, res.order.fiat_currency)} for ${res.order.btc_amount.toFixed(8)} BTC`
      );
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Exchange failed");
    }
  };

  // ── Request Card ──
  const handleRequestCard = async () => {
    setError("");
    try {
      await api("/api/cards", {
        method: "POST",
        body: JSON.stringify({
          card_type: "virtual",
          idempotency_key: generateKey(),
        }),
      });
      showSuccess("Card requested successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Card request failed");
    }
  };

  // ── Tabs ──
  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "deposit", label: "Deposit" },
    { key: "transfer", label: "Transfer" },
    { key: "exchange", label: "BTC Exchange" },
    { key: "cards", label: "Cards" },
  ];

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-600 font-bold text-white">
              N
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Nexus Financial</h1>
              <p className="text-xs text-gray-400">Bitcoin Banking Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="badge-success">Mock Mode</span>
            <span className="text-sm text-gray-400">demo@nexus.financial</span>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-900/50">
        <div className="mx-auto flex max-w-7xl gap-1 px-4">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                tab === t.key
                  ? "border-amber-500 text-amber-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="mx-auto max-w-7xl px-4 py-6">
        {/* Alerts */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-red-300">
            {error}
            <button onClick={() => setError("")} className="float-right text-red-400 hover:text-red-300">
              x
            </button>
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-lg border border-green-800 bg-green-900/30 px-4 py-3 text-green-300">
            {success}
          </div>
        )}

        {/* Overview Tab */}
        {tab === "overview" && (
          <div className="space-y-6">
            {/* Account Cards */}
            <section>
              <h2 className="mb-4 text-lg font-semibold">Your Accounts</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {accounts.map((acct) => (
                  <div key={acct.id} className="card">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-sm font-medium uppercase text-gray-400">
                        {acct.currency} {acct.account_type}
                      </span>
                      <span className={acct.currency === "BTC" ? "text-amber-400" : "text-gray-300"}>
                        {acct.currency}
                      </span>
                    </div>
                    <p className="text-2xl font-bold text-white">
                      {formatAmount(acct.balance, acct.currency)}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      Available: {formatAmount(acct.available_balance, acct.currency)}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* BTC Rates */}
            <section>
              <h2 className="mb-4 text-lg font-semibold">BTC Exchange Rates</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                {Object.entries(rates).map(([currency, rate]) => (
                  <div key={currency} className="card">
                    <span className="text-sm text-gray-400">BTC / {currency}</span>
                    <p className="text-xl font-bold text-amber-400">
                      {formatAmount(rate, currency)}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* Recent Deposits */}
            <section>
              <h2 className="mb-4 text-lg font-semibold">Recent Deposits</h2>
              {deposits.length === 0 ? (
                <p className="text-gray-500">No deposits yet</p>
              ) : (
                <div className="card overflow-x-auto p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 text-left text-gray-400">
                        <th className="px-4 py-3">Amount</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deposits.slice(0, 10).map((dep) => (
                        <tr key={dep.id} className="border-b border-gray-800/50">
                          <td className="px-4 py-3 font-medium text-white">
                            {formatAmount(dep.amount, dep.currency)}
                          </td>
                          <td className="px-4 py-3">
                            <span className={statusBadge(dep.status)}>{dep.status}</span>
                          </td>
                          <td className="px-4 py-3 text-gray-400">
                            {new Date(dep.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}

        {/* Deposit Tab */}
        {tab === "deposit" && (
          <div className="mx-auto max-w-lg">
            <div className="card">
              <h2 className="mb-4 text-lg font-semibold">New Deposit</h2>
              <form onSubmit={handleDeposit} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Account</label>
                  <select
                    className="input"
                    value={depAccountId}
                    onChange={(e) => setDepAccountId(e.target.value)}
                  >
                    {accounts
                      .filter((a) => a.currency !== "BTC")
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.currency} {a.account_type} ({formatAmount(a.balance, a.currency)})
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Currency</label>
                  <select
                    className="input"
                    value={depCurrency}
                    onChange={(e) => setDepCurrency(e.target.value)}
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Amount</label>
                  <input
                    type="number"
                    className="input"
                    placeholder="0.00"
                    step="0.01"
                    min="0.01"
                    value={depAmount}
                    onChange={(e) => setDepAmount(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn-primary w-full">
                  Submit Deposit
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Transfer Tab */}
        {tab === "transfer" && (
          <div className="mx-auto max-w-lg">
            <div className="card">
              <h2 className="mb-4 text-lg font-semibold">Internal Transfer</h2>
              <form onSubmit={handleTransfer} className="space-y-4">
                <div>
                  <label className="mb-1 block text-sm text-gray-400">From Account</label>
                  <select
                    className="input"
                    value={txFromId}
                    onChange={(e) => setTxFromId(e.target.value)}
                  >
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.currency} {a.account_type} ({formatAmount(a.balance, a.currency)})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">To Account</label>
                  <select
                    className="input"
                    value={txToId}
                    onChange={(e) => setTxToId(e.target.value)}
                  >
                    {accounts
                      .filter((a) => a.id !== txFromId)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.currency} {a.account_type} ({formatAmount(a.balance, a.currency)})
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Currency</label>
                  <select
                    className="input"
                    value={txCurrency}
                    onChange={(e) => setTxCurrency(e.target.value)}
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="BTC">BTC</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">Amount</label>
                  <input
                    type="number"
                    className="input"
                    placeholder="0.00"
                    step="0.01"
                    min="0.01"
                    value={txAmount}
                    onChange={(e) => setTxAmount(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn-primary w-full">
                  Execute Transfer
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Exchange Tab */}
        {tab === "exchange" && (
          <div className="space-y-6">
            {/* Rates */}
            <div className="grid gap-4 sm:grid-cols-3">
              {Object.entries(rates).map(([currency, rate]) => (
                <div key={currency} className="card text-center">
                  <span className="text-sm text-gray-400">1 BTC =</span>
                  <p className="text-xl font-bold text-amber-400">{formatAmount(rate, currency)}</p>
                </div>
              ))}
            </div>

            {/* Exchange form */}
            <div className="mx-auto max-w-lg">
              <div className="card">
                <h2 className="mb-4 text-lg font-semibold">Buy Bitcoin</h2>
                <form onSubmit={handleExchange} className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm text-gray-400">Fiat Currency</label>
                    <select
                      className="input"
                      value={exchCurrency}
                      onChange={(e) => setExchCurrency(e.target.value)}
                    >
                      <option value="USD">USD</option>
                      <option value="EUR">EUR</option>
                      <option value="GBP">GBP</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm text-gray-400">Amount</label>
                    <input
                      type="number"
                      className="input"
                      placeholder="0.00"
                      step="0.01"
                      min="0.01"
                      value={exchAmount}
                      onChange={(e) => setExchAmount(e.target.value)}
                      required
                    />
                  </div>
                  {exchAmount && rates[exchCurrency] && (
                    <div className="rounded-lg bg-gray-800 p-3 text-center">
                      <span className="text-sm text-gray-400">You will receive approximately</span>
                      <p className="text-lg font-bold text-amber-400">
                        {(parseFloat(exchAmount) / rates[exchCurrency]).toFixed(8)} BTC
                      </p>
                    </div>
                  )}
                  <button type="submit" className="btn-primary w-full">
                    Buy BTC
                  </button>
                </form>
              </div>
            </div>

            {/* Recent exchange orders */}
            {exchangeOrders.length > 0 && (
              <section>
                <h2 className="mb-4 text-lg font-semibold">Recent Orders</h2>
                <div className="card overflow-x-auto p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 text-left text-gray-400">
                        <th className="px-4 py-3">Fiat</th>
                        <th className="px-4 py-3">BTC</th>
                        <th className="px-4 py-3">Rate</th>
                        <th className="px-4 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {exchangeOrders.map((order) => (
                        <tr key={order.id} className="border-b border-gray-800/50">
                          <td className="px-4 py-3 font-medium text-white">
                            {formatAmount(order.fiat_amount, order.fiat_currency)}
                          </td>
                          <td className="px-4 py-3 text-amber-400">
                            {order.btc_amount.toFixed(8)} BTC
                          </td>
                          <td className="px-4 py-3 text-gray-400">
                            {formatAmount(order.exchange_rate, order.fiat_currency)}
                          </td>
                          <td className="px-4 py-3">
                            <span className={statusBadge(order.status)}>{order.status}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        )}

        {/* Cards Tab */}
        {tab === "cards" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Bitcoin Debit Cards</h2>
              <button onClick={handleRequestCard} className="btn-primary">
                Request New Card
              </button>
            </div>

            {cards.length === 0 ? (
              <div className="card text-center">
                <p className="text-gray-400">No cards yet. Request your first Bitcoin debit card above.</p>
                <p className="mt-2 text-xs text-gray-500">Requires KYC tier 3 or higher</p>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {cards.map((card) => (
                  <div key={card.id} className="card">
                    <div className="mb-4 flex items-center justify-between">
                      <span className="text-sm font-medium uppercase text-gray-400">
                        {card.card_type} Card
                      </span>
                      <span className={statusBadge(card.status)}>{card.status}</span>
                    </div>
                    <p className="mb-4 font-mono text-xl tracking-wider text-white">
                      {card.card_number_masked || "**** **** **** ****"}
                    </p>
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>Daily limit: {formatAmount(card.daily_limit, "USD")}</span>
                      <span>Monthly limit: {formatAmount(card.monthly_limit, "USD")}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-6 text-center text-xs text-gray-600">
        Nexus Financial Platform &mdash; Bitcoin Banking with Double-Entry Ledger
      </footer>
    </div>
  );
}
