"""Orquestra o fluxo completo: 2 faixas → mashup."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .alignment import align
from .compatibility import compatibility_score
from .types import AlignmentPlan, ScoreCompat


@dataclass
class MashupResult:
    mashup: np.ndarray
    sr: int
    stems: dict
    score: ScoreCompat
    plan: AlignmentPlan


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


def make_mashup(
    path_vocal: str, path_base: str, mode: str = "proposto", sr: int = 44100
) -> MashupResult:
    """Vocal de `path_vocal` sobre o instrumental de `path_base`.

    Fluxo: load → separação → análise (beat/downbeat/estrutura) → tom → score →
    alinhamento → síntese. Integra blend-audio (P1) + blend-mashup (P2).
    """
    from . import io, key, separation, synthesis
    from .analysis import analyze

    # 1) carregar A (vocal) e B (base)
    voc_samples, _ = io.load_audio(path_vocal, sr=sr, mono=False)
    base_samples, _ = io.load_audio(path_base, sr=sr, mono=False)

    # 2) separar: instrumental de B (stems) + vocal isolado de A
    stems_base = separation.separate(base_samples, sr)
    vocal_only = separation.separate(voc_samples, sr)["vocals"]

    # 3) análise rítmica/estrutural de ambas
    an_vocal = analyze(path_vocal, voc_samples, sr)
    an_base = analyze(path_base, base_samples, sr)

    # 4) tom → Camelot (Essentia); sem tom, o score harmônico fica neutro
    try:
        an_vocal.key_camelot = key.estimate_key(voc_samples, sr)
        an_base.key_camelot = key.estimate_key(base_samples, sr)
    except Exception:
        pass

    # 5) score de compatibilidade (H2)
    score = compatibility_score(an_vocal, an_base)

    # 6) alinhamento (H1). métricas de áudio por segmento ainda não injetadas
    #    (TODO P2: vocal_fit_rel dos stems) → escolha de seção degrada determinística
    plan = align(an_vocal, an_base, mode=mode)

    # 6b) recorte do vocal: a janela do tamanho da seção alvo com mais energia
    #     vocal, ancorada no downbeat de A (fase da grade). `vocal_dur` em tempo
    #     de A: após o stretch (÷ bpm_ratio) vira o tempo da base.
    dur_na_base = plan.target_segment.end - plan.vocal_offset
    if dur_na_base > 0:
        plan.vocal_dur = dur_na_base * plan.bpm_ratio
        plan.vocal_in = _melhor_janela_vocal(
            vocal_only, sr, plan.vocal_dur, an_vocal.downbeats
        )

    # 7) síntese: vocal de A sobre o instrumental de B
    mashup = synthesis.render(vocal_only, stems_base, sr, plan)

    return MashupResult(mashup=mashup, sr=sr, stems=stems_base, score=score, plan=plan)
