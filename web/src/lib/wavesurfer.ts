/** Helpers do waveform (wavesurfer): cores de seção, regions e formatação. */
import type { Resultado } from "./api";

/** Cor por rótulo de seção (assinatura visual do alinhamento estrutura-aware). */
export const COR_SECAO: Record<string, string> = {
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

export function corSecao(label: string): string {
  return COR_SECAO[label] ?? COR_SECAO.unknown;
}

/** "#rrggbb" + alpha → "rgba(...)" (cores das regions precisam de transparência). */
export function hexParaRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Segundos → "M:SS". */
export function fmtTime(s: number): string {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/** Region desenhada sobre o waveform (seção da base ou janela do vocal). */
export interface RegionSpec {
  id: string;
  start: number;
  end: number;
  color: string;
  /** rótulo opcional dentro da region (só a janela do vocal usa). */
  content?: string;
  /** contorno opcional (destaca a janela do vocal). */
  outline?: string;
}

/**
 * Constrói as regions do resultado: blocos de seção da base (allin1) + a janela
 * onde o vocal entra. Mesmo mapeamento do antigo SectionTimeline — a base entra
 * inteira no mashup, então os tempos das seções batem com o waveform do mashup.
 */
export function buildRegions(resultado: Resultado): RegionSpec[] {
  const base = resultado.analise_base;
  const { plan } = resultado;
  const dur = Math.max(
    resultado.duracao,
    base?.segments.at(-1)?.end ?? 0,
    plan.secao.end,
  );

  const segmentos =
    base && base.segments.length > 0
      ? base.segments
      : [{ start: 0, end: dur, label: "unknown" }];

  const regs: RegionSpec[] = segmentos.map((s, i) => ({
    id: `seg-${i}`,
    start: s.start,
    end: Math.max(s.end, s.start + 0.01),
    color: hexParaRgba(corSecao(s.label), 0.16),
  }));

  const vocalIni = plan.vocal_offset;
  const vocalFim = Math.min(
    dur,
    plan.vocal_offset +
      (plan.vocal_dur != null ? plan.vocal_dur / plan.bpm_ratio : dur),
  );
  regs.push({
    id: "vocal",
    start: vocalIni,
    end: Math.max(vocalFim, vocalIni + 0.01),
    color: hexParaRgba("#3b82f6", 0.18),
    content: "vocal A",
    outline: "#3b82f6",
  });

  return regs;
}
