"""Orquestra o fluxo completo: 2 faixas → mashup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .alignment import align
from .compatibility import compatibility_score
from .types import AlignmentPlan, ScoreCompat, TrackAnalysis


@dataclass
class MashupResult:
    mashup: np.ndarray
    sr: int
    stems: dict
    score: ScoreCompat
    plan: AlignmentPlan
    analise_vocal: TrackAnalysis | None = None  # análise de A (UI/avaliação)
    analise_base: TrackAnalysis | None = None  # análise de B (UI/avaliação)


def _melhor_janela_vocal(
    vocal: np.ndarray,
    sr: int,
    dur_s: float,
    downbeats: list[float],
    win_s: float = 0.5,
) -> float:
    """Início (s) da janela de `dur_s` com MAIS energia vocal no stem.

    Soma móvel da energia (RMS² por frames de `win_s`) e argmax da janela do
    tamanho do recorte, ancorada no downbeat de A imediatamente anterior (mantém
    a fase da grade). Robusto a vazamento da separação — "primeira atividade"
    disparava em bleed de hi-hat em faixas de vocal esparso e recortava silêncio.
    """
    y = np.asarray(vocal)
    if y.ndim == 2:
        y = y.mean(axis=0)
    win = max(1, int(win_s * sr))
    n = len(y) // win
    if n == 0:
        return 0.0
    energia = np.mean(np.square(y[: n * win]).reshape(n, win), axis=1)
    k = max(1, min(n, int(round(dur_s / win_s))))
    csum = np.concatenate([[0.0], np.cumsum(energia)])
    janelas = csum[k:] - csum[:-k]  # energia acumulada de cada janela de k frames
    ini = float(int(np.argmax(janelas)) * win_s)
    antes = [d for d in downbeats if d <= ini + 1e-6]
    return antes[-1] if antes else ini


# Comprimento fixo do trecho vocal: 16 compassos de A (~30 s a 130 BPM, alinhado
# à recomendação do P4). Deliberadamente independente da seção da base.
CLIPE_COMPASSOS = 16


def _recorte_vocal(
    vocal: np.ndarray,
    sr: int,
    bpm_vocal: float,
    downbeats: list[float],
    compassos: int = CLIPE_COMPASSOS,
) -> tuple[float, float]:
    """Trecho vocal (vocal_in, vocal_dur) em segundos de A — INDEPENDENTE do modo.

    Comprimento fixo em compassos de A (não da seção da base): garante que
    baseline e proposto usem EXATAMENTE o mesmo conteúdo vocal, diferindo só na
    COLOCAÇÃO sobre B (vocal_offset). É a invariante que torna a H1 um teste
    justo — sem ela, o painel compararia trechos vocais diferentes (duração e
    conteúdo), não o alinhamento estrutura-aware. A janela é a de maior energia
    vocal, ancorada em downbeat de A; `vocal_dur` é capado pelo vocal disponível.
    """
    bar_s = 4 * 60.0 / bpm_vocal if bpm_vocal and bpm_vocal > 0 else 2.0
    dur = min(compassos * bar_s, vocal.shape[-1] / sr)
    ini = _melhor_janela_vocal(vocal, sr, dur, downbeats)
    return ini, dur


def make_mashup(
    path_vocal: str,
    path_base: str,
    mode: str = "proposto",
    sr: int = 44100,
    on_stage: Callable[[str], None] | None = None,
) -> MashupResult:
    """Vocal de `path_vocal` sobre o instrumental de `path_base`.

    Fluxo: load → separação → análise (beat/downbeat/estrutura) → tom → score →
    alinhamento → síntese. Integra blend-audio (P1) + blend-mashup (P2).
    `on_stage` (opcional) recebe o nome da etapa ao iniciá-la (progresso na UI).
    """
    from . import io, key, separation, synthesis
    from .analysis import analyze

    def _stage(nome: str) -> None:
        if on_stage is not None:
            on_stage(nome)

    # 1) carregar A (vocal) e B (base)
    _stage("carregando")
    voc_samples, _ = io.load_audio(path_vocal, sr=sr, mono=False)
    base_samples, _ = io.load_audio(path_base, sr=sr, mono=False)

    # 2) separar: instrumental de B (stems) + vocal isolado de A
    _stage("separando")
    stems_base = separation.separate(base_samples, sr)
    vocal_only = separation.separate(voc_samples, sr)["vocals"]

    # 3) análise rítmica/estrutural de ambas
    _stage("analisando")
    an_vocal = analyze(path_vocal, voc_samples, sr)
    an_base = analyze(path_base, base_samples, sr)

    # 4) tom → Camelot (Essentia); sem tom, o score harmônico fica neutro
    _stage("estimando_tom")
    try:
        an_vocal.key_camelot = key.estimate_key(voc_samples, sr)
        an_base.key_camelot = key.estimate_key(base_samples, sr)
    except Exception:
        pass

    # 5) score de compatibilidade (H2)
    score = compatibility_score(an_vocal, an_base)

    # 6) alinhamento (H1). métricas de áudio por segmento ainda não injetadas
    #    (TODO P2: vocal_fit_rel dos stems) → escolha de seção degrada determinística
    _stage("alinhando")
    plan = align(an_vocal, an_base, mode=mode)

    # 6b) recorte do vocal: trecho de comprimento FIXO (compassos de A), IDÊNTICO
    #     entre baseline e proposto — invariante de H1. As duas pontas diferem só
    #     na COLOCAÇÃO sobre B (vocal_offset / seção), nunca no conteúdo vocal.
    #     `vocal_dur` em tempo de A; após o stretch (÷ bpm_ratio) vira tempo de B.
    plan.vocal_in, plan.vocal_dur = _recorte_vocal(
        vocal_only, sr, an_vocal.bpm, an_vocal.downbeats
    )

    # 7) síntese: vocal de A sobre o instrumental de B
    _stage("sintetizando")
    mashup = synthesis.render(vocal_only, stems_base, sr, plan)

    return MashupResult(
        mashup=mashup,
        sr=sr,
        stems=stems_base,
        score=score,
        plan=plan,
        analise_vocal=an_vocal,
        analise_base=an_base,
    )
