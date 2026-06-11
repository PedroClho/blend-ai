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

    # 7) síntese: vocal de A sobre o instrumental de B
    mashup = synthesis.render(vocal_only, stems_base, sr, plan)

    return MashupResult(mashup=mashup, sr=sr, stems=stems_base, score=score, plan=plan)
