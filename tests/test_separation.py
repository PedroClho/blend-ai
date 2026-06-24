"""Testes do dispatch de backend de separação (Fase 1b) e dos helpers de I/O.

Mockam o modelo pesado (demucs/RoFormer) — rodam sem GPU nem libs de separação.
A interface pública `separate(samples, sr) -> dict{vocals,drums,bass,other}` é o contrato.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend import separation  # noqa: E402


# --------------------------------------------------------------------------- #
# Dispatch por BLEND_SEP_BACKEND
# --------------------------------------------------------------------------- #
def test_backend_default_eh_htdemucs(monkeypatch):
    monkeypatch.delenv("BLEND_SEP_BACKEND", raising=False)
    assert separation._backend() == "htdemucs"


def test_separate_despacha_para_htdemucs(monkeypatch):
    monkeypatch.delenv("BLEND_SEP_BACKEND", raising=False)
    fake = {k: np.zeros((2, 4), dtype=np.float32) for k in ("vocals", "drums", "bass", "other")}
    monkeypatch.setattr(separation, "_separate_htdemucs", lambda s, sr: fake)
    out = separation.separate(np.zeros((2, 4), dtype=np.float32), 44100)
    assert out is fake


def test_separate_despacha_para_roformer(monkeypatch):
    monkeypatch.setenv("BLEND_SEP_BACKEND", "roformer")
    fake = {k: np.zeros((2, 4), dtype=np.float32) for k in ("vocals", "drums", "bass", "other")}
    monkeypatch.setattr(separation, "_separate_roformer", lambda s, sr: fake)
    out = separation.separate(np.zeros((2, 4), dtype=np.float32), 44100)
    assert out is fake


def test_backend_invalido_levanta(monkeypatch):
    monkeypatch.setenv("BLEND_SEP_BACKEND", "xyz")
    try:
        separation.separate(np.zeros((2, 4), dtype=np.float32), 44100)
        assert False, "esperava ValueError"
    except ValueError as e:
        assert "xyz" in str(e)


# --------------------------------------------------------------------------- #
# I/O temporário (ponte in-memory ↔ API file-based do audio-separator)
# --------------------------------------------------------------------------- #
def test_roundtrip_tmp_wav(tmp_path):
    rng = np.random.default_rng(1)
    arr = rng.standard_normal((2, 1000)).astype(np.float32)
    p = separation._write_tmp_wav(arr, 44100, tmp_path / "x.wav")
    back = separation._read_stem_wav(p)
    assert back.shape == (2, 1000)
    assert back.dtype == np.float32
    assert np.allclose(back, arr, atol=1e-6)


# --------------------------------------------------------------------------- #
# Mapeamento 2-stem → contrato de 4 chaves
# --------------------------------------------------------------------------- #
def test_mapear_2stem_preenche_4_chaves():
    vocals = np.ones((2, 100), dtype=np.float32)
    instr = 0.5 * np.ones((2, 100), dtype=np.float32)
    d = separation._mapear_2stem(vocals, instr)
    assert set(d) == {"vocals", "drums", "bass", "other"}
    assert np.allclose(d["vocals"], vocals)
    assert np.allclose(d["other"], instr)
    assert np.all(d["drums"] == 0.0) and np.all(d["bass"] == 0.0)
    # "tudo menos vocals" (como synthesis.render soma) reconstrói o instrumental
    soma = d["drums"] + d["bass"] + d["other"]
    assert np.allclose(soma, instr)
