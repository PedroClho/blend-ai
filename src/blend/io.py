"""I/O de áudio: decodificar (mp3→samples), carregar e salvar.

Convenção interna de áudio em todo o Blend AI: float32, shape **(canais, amostras)**
— sempre 2D, mesmo mono (1, n). Casa com o formato esperado pelo Demucs e mantém
o pipeline consistente (separação → análise → síntese).
"""
from __future__ import annotations

import numpy as np


def load_audio(path: str, sr: int = 44100, mono: bool = False) -> tuple[np.ndarray, int]:
    """Carrega áudio (mp3/wav/flac) em float32, shape (canais, amostras).

    Usa librosa (aciona ffmpeg/audioread para mp3) e reamostra para `sr`.
    Retorna sempre 2D: mono → (1, n); estéreo → (2, n).
    """
    import librosa

    y, sr_out = librosa.load(path, sr=sr, mono=mono)
    if y.ndim == 1:  # librosa devolve (n,) para mono ou fontes mono
        y = y[np.newaxis, :]
    return np.ascontiguousarray(y, dtype=np.float32), int(sr_out)


def save_audio(path: str, samples: np.ndarray, sr: int) -> None:
    """Salva em .wav (PCM 16-bit). Aceita (canais, amostras) ou (amostras,).

    Faz clip em [-1, 1] para evitar wrap-around na conversão para inteiro.
    """
    import soundfile as sf

    y = np.asarray(samples, dtype=np.float32)
    if y.ndim == 2:  # (canais, amostras) -> (amostras, canais) p/ soundfile
        y = y.T
    y = np.clip(y, -1.0, 1.0)
    sf.write(path, y, int(sr), subtype="PCM_16")
