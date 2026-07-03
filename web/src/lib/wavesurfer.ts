/** Helpers do waveform (wavesurfer): cores de seção, regions e formatação. */
import type { Resultado } from "./api";

/** Cor por rótulo de seção (assinatura visual do alinhamento estrutura-aware).
 * Pensada para render SÓLIDO na tira de seções — matizes bem separados entre
 * rótulos que aparecem juntos em EDM (verse/chorus/inst/break/drop). */
export const COR_SECAO: Record<string, string> = {
  intro: "#94a3b8",
  verse: "#3b82f6",
  chorus: "#6d5ef6",
  drop: "#ef4444",
  bridge: "#ec4899",
  solo: "#14b8a6",
  inst: "#10b981",
  break: "#f59e0b",
  outro: "#94a3b8",
  start: "#d5dae3",
  end: "#d5dae3",
  start_loop: "#d5dae3",
  silence: "#d5dae3",
  unknown: "#aab1bd",
  full: "#aab1bd",
};

/** Cor de texto legível sobre a cor de seção (luminância YIQ). */
export function textoContraste(hex: string): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 >= 150 ? "#14171f" : "#ffffff";
}

/** Funde seções adjacentes de mesmo rótulo (o allin1 fragmenta tech house em
 * blocos de 4–8 compassos — sem fundir, a tira vira confete ilegível). */
export function fundirSecoes(
  segments: { start: number; end: number; label: string }[],
): { start: number; end: number; label: string }[] {
  const out: { start: number; end: number; label: string }[] = [];
  for (const s of segments) {
    const ult = out[out.length - 1];
    if (ult && ult.label === s.label && s.start - ult.end < 0.05) {
      ult.end = Math.max(ult.end, s.end);
    } else {
      out.push({ ...s });
    }
  }
  return out;
}

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
 * Region da janela do vocal sobre o waveform do mashup (resultado). A estrutura
 * da base agora vive na tira de seções sólida abaixo da onda (legível), não em
 * lavagens de cor sobre a onda — sobre a onda fica só a marca do vocal.
 */
export function buildRegions(resultado: Resultado): RegionSpec[] {
  const base = resultado.analise_base;
  const { plan } = resultado;
  // tempos da análise de B estão no relógio ORIGINAL; com BPM alvo a base foi
  // esticada — divide por base_ratio p/ cair no relógio do mashup renderizado
  const br = plan.base_ratio || 1;
  const dur = Math.max(
    resultado.duracao,
    (base?.segments.at(-1)?.end ?? 0) / br,
    plan.secao.end / br,
  );

  const vocalIni = plan.vocal_offset;
  const vocalFim = Math.min(
    dur,
    plan.vocal_offset +
      (plan.vocal_dur != null ? plan.vocal_dur / plan.bpm_ratio : dur),
  );
  return [
    {
      id: "vocal",
      start: vocalIni,
      end: Math.max(vocalFim, vocalIni + 0.01),
      color: hexParaRgba("#3b82f6", 0.18),
      content: "vocal A",
      outline: "#3b82f6",
    },
  ];
}
