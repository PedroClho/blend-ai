"""Análise rítmica e estrutural.

Com allin1 (stack torch 2.0): beat + downbeat + tempo + seções **rotuladas**
(intro/verse/chorus/drop…) — insumo da escolha de seção do alinhamento (H1).
Fallback sem allin1 (stack torch 2.6): beat/downbeat via madmom; `segments=[]`
(o alinhamento então usa o fallback de seção por janela/energia).
"""
from __future__ import annotations

import numpy as np

from .types import Segment, TrackAnalysis


def analyze(
    path: str, samples: np.ndarray | None = None, sr: int | None = None
) -> TrackAnalysis:
    """Devolve TrackAnalysis (bpm, beats, downbeats, segments).

    Tenta allin1; se indisponível (ImportError) ou falhar, cai no fallback madmom.
    `key_camelot` é preenchido depois por key.py.
    """
    try:
        return _analyze_allin1(path, sr)
    except Exception:
        import sys
        import traceback

        print(f"[analysis] allin1 falhou em {path!r}; fallback madmom:", file=sys.stderr)
        traceback.print_exc()
        return _analyze_madmom(path, sr)


def _analyze_allin1(path: str, sr: int | None) -> TrackAnalysis:
    import allin1

    r = allin1.analyze(path, keep_byproducts=False)
    segments = [
        Segment(float(s.start), float(s.end), str(s.label)) for s in r.segments
    ]
    return TrackAnalysis(
        path=path,
        sr=int(sr or 44100),
        bpm=float(r.bpm),
        beats=[float(b) for b in r.beats],
        downbeats=[float(d) for d in r.downbeats],
        segments=segments,
    )


def _analyze_madmom(path: str, sr: int | None) -> TrackAnalysis:
    from madmom.features.downbeats import (
        DBNDownBeatTrackingProcessor,
        RNNDownBeatProcessor,
    )

    act = RNNDownBeatProcessor()(path)
    proc = DBNDownBeatTrackingProcessor(beats_per_bar=[4], fps=100)
    result = proc(act)  # linhas [tempo(s), posição_no_compasso]

    beats = [float(t) for t, _pos in result]
    downbeats = [float(t) for t, pos in result if int(pos) == 1]
    bpm = float(60.0 / np.median(np.diff(beats))) if len(beats) >= 2 else 0.0

    return TrackAnalysis(
        path=path,
        sr=int(sr or 44100),
        bpm=bpm,
        beats=beats,
        downbeats=downbeats,
        segments=[],
    )
