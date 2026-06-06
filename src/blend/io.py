"""I/O de áudio: decodificar (mp3→samples), carregar e salvar."""
from __future__ import annotations

import numpy as np


def load_audio(path: str, sr: int = 44100, mono: bool = False) -> tuple[np.ndarray, int]:
    """Carrega um arquivo de áudio (mp3/wav/flac) em samples float32. Usa ffmpeg/soundfile."""
    raise NotImplementedError  # TODO P1


def save_audio(path: str, samples: np.ndarray, sr: int) -> None:
    """Salva samples em .wav."""
    raise NotImplementedError  # TODO P1
