/** Cliente da API do Blend AI (FastAPI em /api). */

export type Modo = "proposto" | "baseline";

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
    mode: Modo;
    nivel_fallback: number;
    secao: Segmento;
    vocal_offset: number;
    bpm_ratio: number;
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

export async function criarMashup(
  faixaA: File,
  faixaB: File,
  modo: Modo,
): Promise<string> {
  const form = new FormData();
  form.append("faixa_a", faixaA);
  form.append("faixa_b", faixaB);
  const resp = await fetch(`/api/mashups?modo=${modo}`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) throw new Error(`falha ao criar job (HTTP ${resp.status})`);
  const data = (await resp.json()) as { job_id: string };
  return data.job_id;
}

export async function consultarJob(id: string): Promise<JobInfo> {
  const resp = await fetch(`/api/jobs/${id}`);
  if (!resp.ok) throw new Error(`job não encontrado (HTTP ${resp.status})`);
  return (await resp.json()) as JobInfo;
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
