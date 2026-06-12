import type { Resultado } from "../lib/api";

/** Cor por rótulo de seção (assinatura visual do alinhamento estrutura-aware). */
const COR_SECAO: Record<string, string> = {
  intro: "#cbd2dd",
  verse: "#93b8f8",
  chorus: "#6d5ef6",
  drop: "#ef4444",
  bridge: "#14b8a6",
  inst: "#10b981",
  break: "#f59e0b",
  outro: "#cbd2dd",
  start_loop: "#e4e7ee",
  end: "#e4e7ee",
  unknown: "#aab1bd",
  full: "#aab1bd",
};

/**
 * Timeline da base: blocos coloridos por seção detectada (allin1) + faixa do
 * vocal sobreposta — a tese do trabalho (H1) desenhada na tela.
 */
export function SectionTimeline({ resultado }: { resultado: Resultado }) {
  const base = resultado.analise_base;
  const { plan } = resultado;
  const dur = Math.max(
    resultado.duracao,
    base?.segments.at(-1)?.end ?? 0,
    plan.secao.end,
  );
  if (dur <= 0) return null;

  const pct = (s: number) => `${Math.min(100, Math.max(0, (s / dur) * 100))}%`;
  const segmentos =
    base && base.segments.length > 0
      ? base.segments
      : [{ start: 0, end: dur, label: "unknown" }];

  const vocalIni = plan.vocal_offset;
  const vocalFim = Math.min(
    dur,
    plan.vocal_offset + (plan.vocal_dur != null ? plan.vocal_dur / plan.bpm_ratio : dur),
  );

  const rotulos = [...new Set(segmentos.map((s) => s.label))];

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="microlabel">estrutura da base × entrada do vocal</span>
        <span className="font-mono text-[11px] text-ink-faint">
          {plan.nivel_fallback === 0
            ? `seção real: ${plan.secao.label}`
            : `fallback nível ${plan.nivel_fallback}`}
        </span>
      </div>

      <div className="relative h-12 overflow-hidden rounded-md border border-line bg-surface">
        {/* blocos de seção */}
        {segmentos.map((s, i) => (
          <div
            key={i}
            title={`${s.label} · ${s.start.toFixed(0)}–${s.end.toFixed(0)}s`}
            className="absolute inset-y-0 border-r border-white/60"
            style={{
              left: pct(s.start),
              width: pct(s.end - s.start),
              background: COR_SECAO[s.label] ?? COR_SECAO.unknown,
              opacity: 0.32,
            }}
          />
        ))}
        {/* região do vocal */}
        <div
          className="absolute inset-y-1.5 rounded-sm border-2 border-vocal bg-vocal/25"
          style={{ left: pct(vocalIni), width: pct(vocalFim - vocalIni) }}
          title={`vocal: ${vocalIni.toFixed(1)}–${vocalFim.toFixed(1)}s`}
        >
          <span className="microlabel absolute -top-0.5 left-1.5 !text-[0.55rem] !text-vocal">
            vocal A
          </span>
        </div>
        {/* marcador do downbeat de entrada */}
        <div
          className="absolute inset-y-0 w-[2px] bg-vocal"
          style={{ left: pct(vocalIni) }}
        />
      </div>

      {/* régua de tempo + legenda */}
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-ink-faint">
        <span>0:00</span>
        <span>
          {Math.floor(dur / 60)}:{String(Math.round(dur % 60)).padStart(2, "0")}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {rotulos.map((r) => (
          <span key={r} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-[3px]"
              style={{ background: COR_SECAO[r] ?? COR_SECAO.unknown, opacity: 0.55 }}
            />
            <span className="microlabel !text-[0.58rem]">{r}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
