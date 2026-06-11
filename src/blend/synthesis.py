"""Síntese do mashup: time-stretch + pitch-shift (Rubber Band) + mixagem."""
from __future__ import annotations

import numpy as np

from .types import AlignmentPlan


def _stretch_pitch(
    vocal: np.ndarray, sr: int, ratio: float, semitones: float
) -> np.ndarray:
    """Time-stretch (ratio) + pitch-shift (semitons) no vocal (canais, amostras).

    `ratio` é o fator de Rubber Band (>1 acelera, <1 desacelera) — já vem pronto
    do alinhamento (`bpm_ratio = bpm_base / (f·bpm_vocal)`).
    """
    import pyrubberband as pyrb

    y = np.asarray(vocal, dtype=np.float32)
    w = y.T if y.ndim == 2 else y  # pyrb espera (amostras,) ou (amostras, canais)
    if ratio and abs(ratio - 1.0) > 1e-4:
        w = pyrb.time_stretch(w, sr, ratio)
    if semitones and abs(semitones) > 1e-3:
        w = pyrb.pitch_shift(w, sr, semitones)
    out = w.T if y.ndim == 2 else w
    return np.ascontiguousarray(out, dtype=np.float32)


def _to_channels(x: np.ndarray, ch: int) -> np.ndarray:
    """Ajusta o nº de canais: mono→ch (replica) ou estéreo→mono (média)."""
    if x.shape[0] == ch:
        return x
    if x.shape[0] == 1:
        return np.repeat(x, ch, axis=0)
    if x.shape[0] > ch:
        return x.mean(axis=0, keepdims=True)
    return np.repeat(x[:1], ch, axis=0)


def render(
    vocal: np.ndarray,
    base_stems: dict[str, np.ndarray],
    sr: int,
    plan: AlignmentPlan,
) -> np.ndarray:
    """Mixa o vocal de A (esticado/transposto) sobre o INSTRUMENTAL da base.

    Instrumental da base = todos os stems de B menos o vocal de B
    (drums + bass + other). Retorna o mashup (canais, amostras) float32.
    """
    instr_parts = [v for k, v in base_stems.items() if k != "vocals"]
    instrumental = np.sum(instr_parts, axis=0).astype(np.float32)
    if instrumental.ndim == 1:
        instrumental = instrumental[np.newaxis, :]

    voc = _stretch_pitch(vocal, sr, plan.bpm_ratio, plan.pitch_shift_semitones)
    if voc.ndim == 1:
        voc = voc[np.newaxis, :]

    ch = max(instrumental.shape[0], voc.shape[0])
    instrumental = _to_channels(instrumental, ch)
    voc = _to_channels(voc, ch)

    offset = max(0, int(round(plan.vocal_offset * sr)))
    n = max(instrumental.shape[1], offset + voc.shape[1])

    mix = np.zeros((ch, n), dtype=np.float32)
    mix[:, : instrumental.shape[1]] += instrumental
    mix[:, offset : offset + voc.shape[1]] += voc

    pico = float(np.max(np.abs(mix))) if mix.size else 0.0
    if pico > 1.0:  # evita clipping mantendo o ganho relativo
        mix /= pico
    return mix
