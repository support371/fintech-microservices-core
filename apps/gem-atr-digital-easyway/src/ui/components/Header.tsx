'use client';

type HeaderProps = {
  isAdmin: boolean;
  setIsAdmin: (value: boolean) => void;
};

export function Header({ isAdmin, setIsAdmin }: HeaderProps) {
  return (
    <header className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-slate-900 p-5 text-white shadow-lg">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">GEM ATR</p>
        <h1 className="text-2xl font-semibold">Digital EasyWay</h1>
      </div>
      <button
        className="rounded-xl border border-cyan-300/60 px-4 py-2 text-sm font-medium transition hover:bg-cyan-400 hover:text-slate-950"
        onClick={() => setIsAdmin(!isAdmin)}
        type="button"
      >
        Switch to {isAdmin ? 'User' : 'Admin'} View
      </button>
    </header>
  );
}
