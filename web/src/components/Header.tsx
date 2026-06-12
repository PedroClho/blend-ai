export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/85 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[15px] font-bold tracking-tight">
            Blend<span className="text-brand">·</span>AI
          </span>
          <span className="microlabel hidden border-l border-line pl-3 sm:inline">
            mashups guiados por estrutura
          </span>
        </div>
        <nav className="hidden items-center gap-1.5 sm:flex">
          {["HTDEMUCS", "ALLIN1", "CAMELOT", "RUBBER BAND"].map((t) => (
            <span
              key={t}
              className="microlabel rounded-full border border-line bg-surface px-2 py-0.5 !text-[0.56rem]"
            >
              {t}
            </span>
          ))}
        </nav>
      </div>
    </header>
  );
}
