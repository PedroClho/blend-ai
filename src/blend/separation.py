"""Separação de fontes com Demucs v4 (htdemucs_ft)."""
from __future__ import annotations

import numpy as np


def separate(samples: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Separa em stems: 'vocals', 'drums', 'bass', 'other'."""
    raise NotImplementedError  # TODO P1 — Demucs htdemucs_ft
