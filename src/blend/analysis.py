"""Análise rítmica e estrutural com allin1 (beat, downbeat, tempo, seções)."""
from __future__ import annotations

import numpy as np

from .types import TrackAnalysis


def analyze(
    path: str, samples: np.ndarray | None = None, sr: int | None = None
) -> TrackAnalysis:
    """Roda allin1 e devolve TrackAnalysis (bpm, beats, downbeats, segments).

    key_camelot é preenchido depois por key.py.
    """
    raise NotImplementedError  # TODO P1 — allin1
