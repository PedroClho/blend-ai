"""Seleção de pares e preparo de estímulos do experimento subjetivo (P4).

Helpers PUROS (sem GPU/áudio pesado) — testáveis isoladamente. A geração em
lote que chama o motor fica em `gera_estimulos.py`. Ver `specs/experimento-subjetivo.md`.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from blend.compatibility import compatibility_score  # noqa: E402
from blend.types import ScoreCompat, TrackAnalysis  # noqa: E402

CSV_GT = ROOT / "data" / "rekordbox" / "groundtruth.csv"
DIR_BASES = ROOT / "data" / "raw" / "bases"


# --------------------------------------------------------------------------- #
# Ground truth ↔ arquivos
# --------------------------------------------------------------------------- #
def nucleo_titulo(titulo: str) -> str:
    """Núcleo do título p/ casar com o nome do arquivo: tira '(...)' e '[...]'."""
    return titulo.split(" (")[0].split(" [")[0].strip()


def carregar_groundtruth(csv_path: Path = CSV_GT) -> list[dict]:
    """Lê o groundtruth do Rekordbox em dicts (num, titulo, bpm, camelot, genero)."""
    faixas: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            faixas.append(
                {
                    "num": int(r["num"]),
                    "titulo": r["titulo"],
                    "nucleo": nucleo_titulo(r["titulo"]),
                    "interprete": r.get("interprete", ""),
                    "bpm": float(r["bpm"]),
                    "camelot": r["camelot"],
                    "genero": r.get("genero", ""),
                }
            )
    return faixas


def casar_arquivo(fx: dict, dir_bases: Path = DIR_BASES) -> Path | None:
    """Acha o .mp3 cujo nome contém o núcleo do título (case-insensitive)."""
    nucleo = fx["nucleo"].lower()
    for p in sorted(dir_bases.glob("*.mp3")):
        if nucleo and nucleo in p.name.lower():
            return p
    return None


def track_de(fx: dict) -> TrackAnalysis:
    """TrackAnalysis a partir do ground truth (BPM + Camelot; sem áudio)."""
    return TrackAnalysis(
        path=fx["nucleo"], sr=44100, bpm=fx["bpm"], key_camelot=fx["camelot"]
    )


# --------------------------------------------------------------------------- #
# Seleção de pares — estratificada por quartil de score (H2 precisa de espalhamento)
# --------------------------------------------------------------------------- #
def selecionar_pares(
    faixas: list[dict],
    n: int = 12,
    max_dbpm: float = 3.0,
    cap_por_vocal: int = 2,
    so_com_arquivo: bool = True,
    dir_bases: Path = DIR_BASES,
) -> list[dict]:
    """Pares ordenados (A=vocal, B=base) com |ΔBPM| ≤ `max_dbpm`, espalhados no score.

    Estratégia: pontua todos os candidatos, ordena por score e pega `n` posições
    uniformemente espaçadas (cobre os quartis → variação de score p/ H2),
    respeitando no máx. `cap_por_vocal` usos de cada faixa como vocal e sem pares
    repetidos. Determinístico (sem RNG). Retorna dicts com a, b e o ScoreCompat.
    """
    elegiveis = faixas
    if so_com_arquivo:
        elegiveis = [fx for fx in faixas if casar_arquivo(fx, dir_bases) is not None]

    cands: list[tuple[float, dict, dict, ScoreCompat]] = []
    for a in elegiveis:
        for b in elegiveis:
            if a["num"] == b["num"]:
                continue
            if abs(a["bpm"] - b["bpm"]) > max_dbpm:
                continue
            sc = compatibility_score(track_de(a), track_de(b))
            cands.append((sc.total, a, b, sc))
    if not cands:
        return []
    cands.sort(key=lambda c: c[0])

    def _quantis(qtd: int) -> list[int]:
        if qtd <= 1:
            return [0]
        return sorted({round(i * (len(cands) - 1) / (qtd - 1)) for i in range(qtd)})

    escolhidos: list[dict] = []
    chaves: set[tuple[int, int]] = set()
    uso: dict[int, int] = {}

    def _tenta(idx: int) -> None:
        _total, a, b, sc = cands[idx]
        chave = (a["num"], b["num"])
        if chave in chaves or uso.get(a["num"], 0) >= cap_por_vocal:
            return
        chaves.add(chave)
        uso[a["num"]] = uso.get(a["num"], 0) + 1
        escolhidos.append({"a": a, "b": b, "score": sc})

    for idx in _quantis(n):  # passe 1: espaçado por quantil (garante extremos)
        if len(escolhidos) >= n:
            break
        _tenta(idx)
    for idx in range(len(cands)):  # passe 2: completa preservando variedade
        if len(escolhidos) >= n:
            break
        _tenta(idx)
    return escolhidos[:n]


# --------------------------------------------------------------------------- #
# Excerto + normalização de loudness
# --------------------------------------------------------------------------- #
def excerto(
    samples: np.ndarray, sr: int, centro_s: float, dur_s: float, lead_in_s: float = 1.85
) -> np.ndarray:
    """Recorta uma janela de `dur_s` começando `lead_in_s` antes de `centro_s`.

    `samples` em (canais, n) ou (n,). Devolve (canais, m). Clampa às bordas.
    """
    y = samples if samples.ndim == 2 else samples[np.newaxis, :]
    i0 = max(0, int(round((centro_s - lead_in_s) * sr)))
    i1 = min(y.shape[1], i0 + int(round(dur_s * sr)))
    if i1 <= i0:
        return np.zeros((y.shape[0], 1), dtype=np.float32)
    return np.ascontiguousarray(y[:, i0:i1], dtype=np.float32)


def normalizar_rms(
    samples: np.ndarray, alvo_dbfs: float = -14.0, teto: float = 0.97
) -> np.ndarray:
    """Normaliza o RMS para `alvo_dbfs` (volume comum entre estímulos) com teto de pico."""
    y = np.asarray(samples, dtype=np.float32)
    rms = float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))) if y.size else 0.0
    if rms < 1e-6:
        return y
    g = (10.0 ** (alvo_dbfs / 20.0)) / rms
    y = y * g
    pico = float(np.max(np.abs(y)))
    if pico > teto:
        y = y * (teto / pico)
    return y.astype(np.float32)
