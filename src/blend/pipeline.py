"""Orquestra o fluxo completo: 2 faixas → mashup."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import AlignmentPlan


@dataclass
class MashupResult:
    mashup: np.ndarray
    sr: int
    stems: dict
    score: float
    plan: AlignmentPlan


def make_mashup(path_vocal: str, path_base: str, mode: str = "proposto") -> MashupResult:
    """Vocal de `path_vocal` sobre o instrumental de `path_base`.

    Fluxo: separação → análise → tom → score → alinhamento → síntese.
    Integra blend-audio (P1) + blend-mashup (P2).
    """
    raise NotImplementedError  # TODO P2
