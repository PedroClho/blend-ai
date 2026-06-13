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


def _recortar(
    voc: np.ndarray,
    sr: int,
    inicio: float,
    dur: float | None,
    fade_in_s: float = 0.02,
    fade_out_s: float = 0.20,
) -> np.ndarray:
    """Corta o vocal (canais, n) em [inicio, inicio+dur) com fades nas bordas."""
    i0 = max(0, int(round(inicio * sr)))
    i1 = voc.shape[1] if dur is None else min(voc.shape[1], i0 + int(round(dur * sr)))
    if i1 <= i0:
        return np.zeros((voc.shape[0], 1), dtype=np.float32)
    out = np.ascontiguousarray(voc[:, i0:i1], dtype=np.float32).copy()
    nfi = min(int(fade_in_s * sr), out.shape[1])
    if nfi > 1:
        out[:, :nfi] *= np.linspace(0.0, 1.0, nfi, dtype=np.float32)
    nfo = min(int(fade_out_s * sr), out.shape[1])
    if nfo > 1:
        out[:, -nfo:] *= np.linspace(1.0, 0.0, nfo, dtype=np.float32)
    return out


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64))) if x.size else 0.0


def _to_channels(x: np.ndarray, ch: int) -> np.ndarray:
    """Ajusta o nº de canais: mono→ch (replica) ou estéreo→mono (média)."""
    if x.shape[0] == ch:
        return x
    if x.shape[0] == 1:
        return np.repeat(x, ch, axis=0)
    if x.shape[0] > ch:
        return x.mean(axis=0, keepdims=True)
    return np.repeat(x[:1], ch, axis=0)


def _passa_altas(x: np.ndarray, sr: int, fc: float = 110.0, ordem: int = 2) -> np.ndarray:
    """Passa-altas Butterworth (gentil): tira graves do vocal p/ não competir com o baixo de B."""
    if x.size == 0:
        return x
    from scipy.signal import butter, sosfilt

    sos = butter(ordem, fc / (sr / 2.0), btype="highpass", output="sos")
    return np.ascontiguousarray(sosfilt(sos, x, axis=-1), dtype=np.float32)


def _envelope(mono: np.ndarray, sr: int, suav_s: float = 0.05) -> np.ndarray:
    """Envelope de amplitude suavizado, normalizado em [0,1] (p/ ducking)."""
    win = max(1, int(suav_s * sr))
    env = np.convolve(np.abs(mono), np.ones(win, np.float32) / win, mode="same")
    m = float(env.max()) if env.size else 0.0
    return env / m if m > 1e-9 else env


def _ducking(
    instrumental: np.ndarray, voc: np.ndarray, offset: int, sr: int, reducao_db: float = 3.5
) -> np.ndarray:
    """Sidechain-lite: atenua a base em até −`reducao_db` onde o vocal é forte."""
    out = instrumental.copy()
    n = min(voc.shape[1], out.shape[1] - offset)
    if n <= 0:
        return out
    env = _envelope(voc.mean(axis=0)[:n], sr)
    alpha = 1.0 - 10.0 ** (-abs(reducao_db) / 20.0)  # 1 sem vocal → 10^(-db/20) no pico
    out[:, offset : offset + n] *= (1.0 - alpha * env).astype(np.float32)
    return out


def render(
    vocal: np.ndarray,
    base_stems: dict[str, np.ndarray],
    sr: int,
    plan: AlignmentPlan,
) -> np.ndarray:
    """Mixa o vocal de A (recortado/esticado/transposto) sobre o INSTRUMENTAL da base.

    Instrumental da base = todos os stems de B menos o vocal de B
    (drums + bass + other). O vocal é recortado em [vocal_in, vocal_in+vocal_dur)
    (tempo de A) antes do stretch e tem o ganho casado por RMS com o trecho do
    instrumental onde entra. Retorna o mashup (canais, amostras) float32.
    """
    instr_parts = [v for k, v in base_stems.items() if k != "vocals"]
    instrumental = np.sum(instr_parts, axis=0).astype(np.float32)
    if instrumental.ndim == 1:
        instrumental = instrumental[np.newaxis, :]

    voc = np.asarray(vocal, dtype=np.float32)
    if voc.ndim == 1:
        voc = voc[np.newaxis, :]
    voc = _recortar(voc, sr, plan.vocal_in, plan.vocal_dur)
    voc = _stretch_pitch(voc, sr, plan.bpm_ratio, plan.pitch_shift_semitones)
    if voc.ndim == 1:
        voc = voc[np.newaxis, :]

    ch = max(instrumental.shape[0], voc.shape[0])
    instrumental = _to_channels(instrumental, ch)
    voc = _to_channels(voc, ch)

    offset = max(0, int(round(plan.vocal_offset * sr)))

    # corte de graves no vocal: não disputa a região do baixo de B (menos "barro")
    voc = _passa_altas(voc, sr)

    # ganho: casa o RMS do vocal com a energia da base NA BANDA DO VOCAL (a base
    # também passa-altas, p/ o baixo não dominar a referência e estourar o vocal),
    # vocal no nível da base. clamp evita amplificar bleed da separação.
    trecho = instrumental[:, offset : offset + voc.shape[1]]
    rms_i, rms_v = _rms(_passa_altas(trecho, sr)), _rms(voc)
    if rms_i > 1e-6 and rms_v > 1e-6:
        voc = voc * float(np.clip(rms_i / rms_v, 0.25, 4.0))

    # ducking: abre espaço pro vocal atenuando a base sob ele (sidechain-lite)
    instrumental = _ducking(instrumental, voc, offset, sr)

    n = max(instrumental.shape[1], offset + voc.shape[1])
    mix = np.zeros((ch, n), dtype=np.float32)
    mix[:, : instrumental.shape[1]] += instrumental
    mix[:, offset : offset + voc.shape[1]] += voc

    pico = float(np.max(np.abs(mix))) if mix.size else 0.0
    if pico > 1.0:  # evita clipping mantendo o ganho relativo
        mix /= pico
    return mix
