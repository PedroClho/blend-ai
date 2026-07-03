/** Espelhos client-side de decisões do motor — preview do modo manual antes de gerar.
 *
 * O snap em downbeat é responsabilidade da UI (o motor confia nos segundos que
 * recebe); o stretch mostrado aqui é estimativa com a MESMA regra do motor
 * (`_escolher_bpm_ratio`), então a região desenhada em B bate com o resultado.
 */
import type { Segmento } from "./api";

/** Regra do motor: f ∈ {0.5, 1, 2} que deixa ratio = bpmB/(f·bpmA) mais perto de 1. */
export function bpmRatio(bpmBase: number, bpmVocal: number): number {
  if (!bpmBase || !bpmVocal || bpmBase <= 0 || bpmVocal <= 0) return 1;
  let melhor = 1;
  let dist = Infinity;
  for (const f of [0.5, 1, 2]) {
    const r = bpmBase / (f * bpmVocal);
    const d = Math.abs(r - 1);
    if (d < dist) {
      dist = d;
      melhor = r;
    }
  }
  return melhor;
}

/** Downbeat mais próximo de t (snap por compasso); sem grade, devolve o próprio t. */
export function downbeatMaisProximo(downbeats: number[], t: number): number {
  if (downbeats.length === 0) return Math.max(0, t);
  let melhor = downbeats[0];
  for (const d of downbeats) {
    if (Math.abs(d - t) < Math.abs(melhor - t)) melhor = d;
  }
  return melhor;
}

/** Duração de N compassos (4/4) em segundos no BPM dado. */
export function segundosDeCompassos(bpm: number, compassos: number): number {
  if (!bpm || bpm <= 0) return compassos * 2;
  return (compassos * 4 * 60) / bpm;
}

/** Nº do compasso (1-based) cujo downbeat inicia em/antes de t — leitura de DJ. */
export function numeroDoCompasso(downbeats: number[], t: number): number {
  let n = 0;
  for (const d of downbeats) {
    if (d <= t + 1e-6) n++;
    else break;
  }
  return Math.max(1, n);
}

/** Rótulo da seção que contém o instante t; null se fora de todas. */
export function secaoEm(segments: Segmento[], t: number): string | null {
  for (const s of segments) {
    if (s.start <= t && t < s.end) return s.label;
  }
  return null;
}

/** Downbeat vizinho: ±delta compassos a partir do downbeat mais próximo de t. */
export function downbeatVizinho(downbeats: number[], t: number, delta: number): number {
  if (downbeats.length === 0) return Math.max(0, t);
  let idx = 0;
  for (let i = 1; i < downbeats.length; i++) {
    if (Math.abs(downbeats[i] - t) < Math.abs(downbeats[idx] - t)) idx = i;
  }
  const novo = Math.min(downbeats.length - 1, Math.max(0, idx + delta));
  return downbeats[novo];
}
