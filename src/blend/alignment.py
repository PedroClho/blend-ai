"""Alinhamento do vocal (A) sobre a base (B). Contribuição central (H1)."""
from __future__ import annotations

from .types import AlignmentPlan, TrackAnalysis


def align(vocal: TrackAnalysis, base: TrackAnalysis, mode: str = "proposto") -> AlignmentPlan:
    """Decide como o vocal entra sobre a base.

    mode='proposto': estrutura-aware (escolhe a seção + sincroniza frases ao downbeat).
    mode='baseline': ingênuo (casa BPM/tom + 1º downbeat).
    Ambos existem para o experimento comparativo (P4).
    """
    raise NotImplementedError  # TODO P2
