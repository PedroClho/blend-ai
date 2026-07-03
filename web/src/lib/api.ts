/** Cliente da API do Blend AI (FastAPI em /api). */

export type Modo = "proposto" | "baseline";
/** O plano devolvido pode ser "manual" quando âncoras sobrescrevem o automático. */
export type ModoPlano = Modo | "manual";

export interface Segmento {
  start: number;
  end: number;
  label: string;
}

export interface Analise {
  bpm: number;
  key_camelot: string | null;
  n_beats: number;
  n_downbeats: number;
  duracao: number | null;
  segments: Segmento[];
}

/** Análise prévia completa (endpoint /api/analyses) — inclui a grade de downbeats. */
export interface AnaliseFaixa extends Analise {
  downbeats: number[];
  cache?: boolean;
}

/** Estado client-side da análise prévia de um deck (modo manual). */
export interface EstadoAnalise {
  status: "nenhuma" | "rodando" | "pronta" | "erro";
  etapa?: string;
  dados?: AnaliseFaixa;
  erro?: string;
}

/** Âncoras do modo manual, em segundos (vocal_in/dur no tempo de A; offset no de B). */
export interface Ancoras {
  vocal_in: number;
  vocal_dur: number;
  vocal_offset: number;
}

export interface OpcoesMashup {
  transpor?: boolean;
  ancoras?: Ancoras | null;
  /** BPM final do mashup: as DUAS faixas vão para esse BPM antes do merge
   * (a base estica sem mudar de tom). null/undefined = manter o BPM da base. */
  bpmAlvo?: number | null;
}

export interface Resultado {
  audio_url: string;
  duracao: number;
  score: {
    total: number;
    harmonico: number;
    tempo: number;
    energia: number | null;
    camelot_dist: number;
  };
  plan: {
    mode: ModoPlano;
    nivel_fallback: number;
    secao: Segmento;
    vocal_offset: number;
    bpm_ratio: number;
    /** stretch aplicado à BASE (1.0 = sem BPM alvo). Tempos da análise de B
     * estão no relógio ORIGINAL de B: dividir por base_ratio p/ desenhar. */
    base_ratio: number;
    bpm_alvo: number | null;
    pitch_shift_semitones: number;
    vocal_in: number;
    vocal_dur: number | null;
  };
  analise_vocal: Analise | null;
  analise_base: Analise | null;
}

export interface JobInfo {
  id: string;
  status: "na_fila" | "processando" | "concluido" | "erro";
  etapa: string;
  etapas: string[];
  modo: Modo;
  nome_a: string;
  nome_b: string;
  erro: string | null;
  resultado: Resultado | null;
}

export interface AnaliseJobInfo {
  id: string;
  status: "na_fila" | "processando" | "concluido" | "erro";
  etapa: string;
  etapas: string[];
  nome: string;
  erro: string | null;
  resultado: AnaliseFaixa | null;
}

export async function criarMashup(
  faixaA: File,
  faixaB: File,
  modo: Modo,
  opcoes: OpcoesMashup = {},
): Promise<string> {
  const form = new FormData();
  form.append("faixa_a", faixaA);
  form.append("faixa_b", faixaB);

  const params = new URLSearchParams({ modo });
  if (opcoes.transpor === false) params.set("transpor", "false");
  if (opcoes.bpmAlvo != null) params.set("bpm_alvo", opcoes.bpmAlvo.toFixed(2));
  if (opcoes.ancoras) {
    params.set("vocal_in", opcoes.ancoras.vocal_in.toFixed(3));
    params.set("vocal_dur", opcoes.ancoras.vocal_dur.toFixed(3));
    params.set("vocal_offset", opcoes.ancoras.vocal_offset.toFixed(3));
  }

  const resp = await fetch(`/api/mashups?${params}`, { method: "POST", body: form });
  if (!resp.ok) throw new Error(`falha ao criar job (HTTP ${resp.status})`);
  const data = (await resp.json()) as { job_id: string };
  return data.job_id;
}

export async function consultarJob(id: string): Promise<JobInfo> {
  const resp = await fetch(`/api/jobs/${id}`);
  if (!resp.ok) throw new Error(`job não encontrado (HTTP ${resp.status})`);
  return (await resp.json()) as JobInfo;
}

export async function criarAnalise(faixa: File): Promise<string> {
  const form = new FormData();
  form.append("faixa", faixa);
  const resp = await fetch("/api/analyses", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`falha ao criar análise (HTTP ${resp.status})`);
  const data = (await resp.json()) as { analysis_id: string };
  return data.analysis_id;
}

export async function consultarAnalise(id: string): Promise<AnaliseJobInfo> {
  const resp = await fetch(`/api/analyses/${id}`);
  if (!resp.ok) throw new Error(`análise não encontrada (HTTP ${resp.status})`);
  return (await resp.json()) as AnaliseJobInfo;
}

export const ROTULO_ETAPA: Record<string, string> = {
  carregando: "Decodificando as faixas",
  separando: "Separando stems (Demucs · GPU)",
  analisando: "Detectando beats, downbeats e estrutura (allin1)",
  estimando_tom: "Estimando tom → Camelot (Essentia)",
  alinhando: "Alinhando vocal à seção de groove",
  sintetizando: "Time-stretch + pitch-shift (Rubber Band) e mixagem",
  pronto: "Pronto",
};

/** Rótulos curtos das etapas da análise prévia (chips do deck). */
export const ROTULO_ETAPA_CURTO: Record<string, string> = {
  na_fila: "na fila (GPU ocupada)",
  carregando: "decodificando",
  analisando: "beats + seções",
  estimando_tom: "tom",
  pronto: "pronto",
};
