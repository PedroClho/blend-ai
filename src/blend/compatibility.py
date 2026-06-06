"""Score de compatibilidade entre duas faixas (H2)."""
from __future__ import annotations

from .types import TrackAnalysis


def camelot_distance(a: str, b: str) -> int:
    """Distância na roda Camelot (0 = mesmo; vizinhos compatíveis = 1)."""
    raise NotImplementedError  # TODO P2


def compatibility_score(a: TrackAnalysis, b: TrackAnalysis) -> float:
    """Índice preditivo: distância harmônica Camelot + razão de BPM + similaridade de energia/estrutura."""
    raise NotImplementedError  # TODO P2
