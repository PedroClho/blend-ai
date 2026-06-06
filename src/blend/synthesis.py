"""Síntese do mashup: time-stretch + pitch-shift (Rubber Band) + mixagem."""
from __future__ import annotations

import numpy as np

from .types import AlignmentPlan


def render(
    vocal: np.ndarray,
    base_stems: dict[str, np.ndarray],
    sr: int,
    plan: AlignmentPlan,
) -> np.ndarray:
    """Aplica stretch/pitch ao vocal conforme o plano e mixa com a base. Retorna o mashup."""
    raise NotImplementedError  # TODO P2 — pyrubberband
