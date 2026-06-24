"""Integração leve do make_mashup (Fase 1a Tarefa 6): wiring da sincronização de frases.

Mocka io/separação/análise/tom (sem librosa/torch/essentia); a síntese roda de verdade.
Verifica que o proposto preenche `phrase_anchors` e o baseline não (invariante de H1).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend import analysis as analysis_mod  # noqa: E402
from blend import io, key, pipeline, separation  # noqa: E402
from blend.types import Segment, TrackAnalysis  # noqa: E402

SR = 44100


def _vocal_longo() -> np.ndarray:
    # 60 s: [tom 2 s, silêncio 1 s] repetido → frases detectáveis em qualquer janela
    bloco = np.concatenate(
        [
            (0.5 * np.sin(2 * np.pi * 440 * np.arange(2 * SR) / SR)).astype(np.float32),
            np.zeros(SR, dtype=np.float32),
        ]
    )
    return np.tile(bloco, 20)[: 60 * SR][np.newaxis, :]


def _stems(_samples) -> dict:
    voc = _vocal_longo()
    n = voc.shape[1]
    z = np.zeros((1, n), dtype=np.float32)
    return {"vocals": voc, "drums": (0.1 * np.ones((1, n))).astype(np.float32), "bass": z, "other": z.copy()}


def _patch(monkeypatch):
    monkeypatch.delenv("BLEND_SEP_BACKEND", raising=False)
    monkeypatch.setattr(io, "load_audio", lambda p, sr=SR, mono=False: (np.zeros((2, 60 * SR), np.float32), SR))
    monkeypatch.setattr(separation, "separate", lambda s, sr: _stems(s))
    monkeypatch.setattr(key, "estimate_key", lambda s, sr: "8A")
    bar = 4 * 60 / 128
    an_v = TrackAnalysis(path="a.mp3", sr=SR, bpm=128.0, downbeats=[i * bar for i in range(60)], segments=[], key_camelot="8A")
    an_b = TrackAnalysis(
        path="b.mp3", sr=SR, bpm=128.0, downbeats=[i * bar for i in range(60)],
        segments=[Segment(0.0, 30.0, "intro"), Segment(30.0, 90.0, "chorus")], key_camelot="8A",
    )
    monkeypatch.setattr(analysis_mod, "analyze", lambda path, samples=None, sr=None: an_v if path == "a.mp3" else an_b)


def test_make_mashup_proposto_preenche_phrase_anchors(monkeypatch):
    _patch(monkeypatch)
    r = pipeline.make_mashup("a.mp3", "b.mp3", mode="proposto")
    assert r.plan.nivel_fallback == 0  # escolheu o chorus
    assert r.plan.phrase_anchors is not None and len(r.plan.phrase_anchors) >= 1
    assert r.mashup.shape[0] >= 1  # gerou áudio


def test_make_mashup_baseline_nao_usa_frases(monkeypatch):
    _patch(monkeypatch)
    r = pipeline.make_mashup("a.mp3", "b.mp3", mode="baseline")
    assert r.plan.phrase_anchors is None  # baseline nunca usa frases (teste justo de H1)
