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


def _inicio_atividade_vocal(
    vocal: np.ndarray,
    sr: int,
    win_s: float = 0.10,
    min_dur_s: float = 0.40,
    limiar_rel: float = 0.15,
) -> float | None:
    """Início (s) da primeira atividade vocal sustentada no stem; None se silêncio.

    RMS por janelas de `win_s`; ativo = acima de `limiar_rel`·P95(RMS); exige
    `min_dur_s` contínuos pra ignorar respiros/vazamento da separação.
    """
    y = np.asarray(vocal)
    if y.ndim == 2:
        y = y.mean(axis=0)
    win = max(1, int(win_s * sr))
    n = len(y) // win
    if n == 0:
        return None
    rms = np.sqrt(np.mean(np.square(y[: n * win].reshape(n, win)), axis=1))
    pico = float(np.percentile(rms, 95))
    if pico <= 1e-6:
        return None
    ativo = rms >= limiar_rel * pico
    need = max(1, int(round(min_dur_s / win_s)))
    seguidos = 0
    for i, a in enumerate(ativo):
        seguidos = seguidos + 1 if a else 0
        if seguidos >= need:
            return float((i - need + 1) * win_s)
    return None


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

    # 6b) recorte do vocal: começa onde há voz de verdade (snap no downbeat de A
    #     anterior, p/ manter a fase da grade) e dura até o fim da seção alvo.
    #     `vocal_dur` em tempo de A: após o stretch (÷ bpm_ratio) vira o tempo da base.
    ini = _inicio_atividade_vocal(vocal_only, sr)
    if ini is not None:
        antes = [d for d in an_vocal.downbeats if d <= ini + 1e-6]
        plan.vocal_in = antes[-1] if antes else ini
    dur_na_base = plan.target_segment.end - plan.vocal_offset
    if dur_na_base > 0:
        plan.vocal_dur = dur_na_base * plan.bpm_ratio

    # 7) síntese: vocal de A sobre o instrumental de B
    mashup = synthesis.render(vocal_only, stems_base, sr, plan)

    return MashupResult(mashup=mashup, sr=sr, stems=stems_base, score=score, plan=plan)
