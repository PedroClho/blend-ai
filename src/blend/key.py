"""Estimação de tom (Essentia, perfil EDMA), mapeamento Camelot e leitura do Rekordbox."""
from __future__ import annotations

import numpy as np


def estimate_key(samples: np.ndarray, sr: int) -> str:
    """Estima o tom com Essentia (perfil EDMA) e retorna em notação Camelot (ex.: '8A')."""
    raise NotImplementedError  # TODO P1 — Essentia EDMA


def to_camelot(key: str, scale: str) -> str:
    """Converte tom musical (ex.: 'A', 'minor') para Camelot (ex.: '8A')."""
    raise NotImplementedError  # TODO P1


def read_rekordbox_keys(xml_path: str) -> dict[str, str]:
    """Lê o tom (atributo Tonality) por faixa de um rekordbox.xml. Ground truth / atalho."""
    raise NotImplementedError  # TODO P1/P4 — pyrekordbox ou parse do XML
