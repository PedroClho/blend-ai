"""Testes da mashability aprendida (Fase 2).

A função `mashability()` (em compatibility.py) é **pura** e reusa `compatibility_score`
— `embed=None` é byte-idêntico ao H2. O COCOLA real é mockado/injetado (cabeça fake),
então tudo roda sem GPU nem checkpoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blend.compatibility import compatibility_score, mashability  # noqa: E402
from blend.types import EmbedFeatures, TrackAnalysis  # noqa: E402


def _ta(camelot, bpm) -> TrackAnalysis:
    return TrackAnalysis(path="x", sr=44100, bpm=bpm, key_camelot=camelot)


class _CabecaFake:
    """Cabeça de calibração fake: retorna valores fixos para (A→B, B→A)."""

    def __init__(self, val=0.9, rev=0.2):
        self.val, self.rev = val, rev

    def pontuar(self, embed, sc):  # noqa: ARG002
        return self.val, self.rev


# --------------------------------------------------------------------------- #
# embed=None → idêntico ao H2 (não contamina o score científico)
# --------------------------------------------------------------------------- #
def test_mashability_sem_embed_identico_ao_h2():
    pares = [("8A", "8A"), ("8A", "2B"), (None, "8A"), ("8A", "8A")]
    for ca, cb in pares:
        a, b = _ta(ca, 128.0), _ta(cb, 128.0)
        for metr in (None, {"energia_a": -10.0, "energia_b": -12.0}):
            m = mashability(a, b, embed=None, metricas=metr)
            h = compatibility_score(a, b, metr)
            assert m.total == h.total
            assert m.harmonico == h.harmonico and m.tempo == h.tempo
            assert m.energia == h.energia and m.camelot_dist == h.camelot_dist
            assert m.bpm_ratio == h.bpm_ratio and m.pesos == h.pesos
            assert m.learned_score is None
            assert m.learned_score_rev is None
            assert m.embed_sim is None


# --------------------------------------------------------------------------- #
# zero-shot: sem cabeça treinada, o próprio sim direcional é o score de produto
# --------------------------------------------------------------------------- #
def test_mashability_zero_shot_usa_sim_direcional():
    a, b = _ta("8A", 128.0), _ta("9A", 128.0)
    ef = EmbedFeatures(emb_vocal=[0.1], emb_instr=[0.2], sim_ab=0.7, sim_ba=0.4)
    m = mashability(a, b, embed=ef)  # sem cabeça → zero-shot
    assert m.embed_sim == 0.7
    assert m.learned_score == 0.7 and m.learned_score_rev == 0.4
    h = compatibility_score(a, b)
    assert m.total == h.total and m.harmonico == h.harmonico  # H2 intacto


# --------------------------------------------------------------------------- #
# com cabeça calibrada: usa a predição; embed_sim continua o diagnóstico cru
# --------------------------------------------------------------------------- #
def test_mashability_com_cabeca_usa_predicao():
    a, b = _ta("8A", 128.0), _ta("8A", 130.0)
    ef = EmbedFeatures(emb_vocal=[0.1], emb_instr=[0.2], sim_ab=0.6, sim_ba=0.3)
    m = mashability(a, b, embed=ef, cabeca=_CabecaFake(0.95, 0.15))
    assert m.embed_sim == 0.6
    assert m.learned_score == 0.95 and m.learned_score_rev == 0.15
    h = compatibility_score(a, b)
    assert m.total == h.total  # o produto não altera o H2


def test_embedfeatures_tem_sim_direcional_default_none():
    ef = EmbedFeatures(emb_vocal=[1.0], emb_instr=[2.0])
    assert ef.sim_ab is None and ef.sim_ba is None


# =========================================================================== #
# Módulo blend.mashability — partes puras (sem COCOLA/GPU)
# =========================================================================== #
import numpy as np  # noqa: E402


def test_score_bilinear_assimetrico():
    from blend import mashability as mm

    W = np.array([[1.0, 2.0], [0.0, 1.0]])  # não-simétrica
    h1, h2 = [1.0, 0.0], [0.0, 1.0]
    ab = mm.score_bilinear(h1, h2, W)  # h1 W h2 = W[0,1] = 2.0
    ba = mm.score_bilinear(h2, h1, W)  # h2 W h1 = W[1,0] = 0.0
    assert abs(ab - 2.0) < 1e-9 and abs(ba - 0.0) < 1e-9
    assert ab != ba  # assimetria pela forma bilinear


def test_preparar_audio_16k_mono_5s():
    from blend import mashability as mm

    sr = 44100
    est = np.zeros((2, sr * 7), dtype=np.float32)  # estéreo, 7 s
    est[:, : sr] = 0.5
    y = mm._preparar_audio(est, sr)
    assert y.ndim == 1  # mono
    assert y.shape[0] == 16000 * 5  # 16 kHz, 5 s = 80000 amostras


def test_preparar_audio_pad_curto():
    from blend import mashability as mm

    sr = 16000
    curto = np.ones(sr * 2, dtype=np.float32)  # só 2 s @ 16k
    y = mm._preparar_audio(curto, sr)
    assert y.shape[0] == 16000 * 5
    assert np.all(y[16000 * 2 :] == 0.0)  # zero-pad no fim


# --- cache de embeddings (1× por faixa) ---
def test_embed_cacheado_calcula_uma_vez_e_reusa(tmp_path):
    from blend import mashability as mm

    chamadas = {"n": 0}

    def embedder():
        chamadas["n"] += 1
        return np.array([1.0, 2.0, 3.0], dtype=np.float32)

    e1 = mm.embed_cacheado("faixaA.wav", "vocal", embedder, cache_dir=str(tmp_path))
    e2 = mm.embed_cacheado("faixaA.wav", "vocal", embedder, cache_dir=str(tmp_path))
    assert chamadas["n"] == 1  # 2ª vez lê do disco, não recomputa
    assert np.allclose(e1, [1.0, 2.0, 3.0]) and np.allclose(e2, e1)


def test_caminho_cache_distingue_faixa_papel_modo(tmp_path):
    from blend import mashability as mm

    p = lambda tid, pap, mo: mm.caminho_cache(tid, pap, mo, str(tmp_path))  # noqa: E731
    assert p("A", "vocal", "both") == p("A", "vocal", "both")
    assert p("A", "vocal", "both") != p("A", "instr", "both")
    assert p("A", "vocal", "both") != p("B", "vocal", "both")
    assert p("A", "vocal", "both") != p("A", "vocal", "harmonic")


# --- embed_de_audio: prepara o áudio e passa pro encoder (encoder mockado) ---
def test_embed_de_audio_prepara_e_passa_pro_modelo(monkeypatch):
    from blend import mashability as mm

    capturado = {}

    class FakeModelo:
        def embed(self, x):
            capturado["len"] = int(np.asarray(x).size)
            return np.arange(512, dtype=np.float32)

    monkeypatch.setattr(mm, "_carregar_modelo", lambda modo="both": FakeModelo())
    emb = mm.embed_de_audio(np.ones((2, 44100 * 7), dtype=np.float32), 44100)
    assert capturado["len"] == 16000 * 5  # recebeu 5 s @ 16 kHz mono
    assert isinstance(emb, list) and len(emb) == 512


# --- montar_features + Calibrador (cabeça de calibração) ---
def _ef(sim_ab=0.7, sim_ba=0.4, centroide=None):
    return EmbedFeatures(emb_vocal=[0.0], emb_instr=[0.0], sim_ab=sim_ab, sim_ba=sim_ba, centroide=centroide)


def test_montar_features_ordem_e_none():
    from blend import mashability as mm

    sc = compatibility_score(_ta("8A", 128.0), _ta("9A", 128.0))  # energia None
    f = mm.montar_features(_ef(0.7, 0.4), sc)
    assert f[0] == 0.7 and f[1] == 0.4          # sim_ab, sim_ba
    assert f[2] == sc.harmonico and f[3] == sc.tempo
    assert f[4] == 0.0 and f[5] == 0.0          # energia None / centroide None → 0


def test_montar_features_reverso_troca_sim():
    from blend import mashability as mm

    sc = compatibility_score(_ta("8A", 128.0), _ta("8A", 128.0))
    f = mm.montar_features(_ef(0.7, 0.4), sc, reverso=True)
    assert f[0] == 0.4 and f[1] == 0.7          # direção reversa troca sim_ab/sim_ba


def test_calibrador_aprende_separavel():
    from blend import mashability as mm

    # rótulo determinado pela 1ª feature (sim_ab): separável
    X = [[s, 0.0, 0.5, 0.5, 0.0, 0.0] for s in np.linspace(0, 1, 40)]
    y = [1 if row[0] > 0.5 else 0 for row in X]
    cal = mm.Calibrador().fit(X, y)
    assert cal._prob([0.95, 0, 0.5, 0.5, 0, 0]) > cal._prob([0.05, 0, 0.5, 0.5, 0, 0])


def test_calibrador_pontuar_captura_assimetria():
    from blend import mashability as mm

    X = [[s, 0.0, 0.5, 0.5, 0.0, 0.0] for s in np.linspace(0, 1, 40)]
    y = [1 if row[0] > 0.5 else 0 for row in X]
    cal = mm.Calibrador().fit(X, y)
    sc = compatibility_score(_ta("8A", 128.0), _ta("8A", 128.0))
    ab, ba = cal.pontuar(_ef(0.9, 0.1), sc)  # A→B forte, B→A fraco
    assert ab > ba  # a forma direcional propaga pela cabeça


def test_calibrador_serializa(tmp_path):
    from blend import mashability as mm

    X = [[s, 0.0, 0.5, 0.5, 0.0, 0.0] for s in np.linspace(0, 1, 40)]
    y = [1 if row[0] > 0.5 else 0 for row in X]
    cal = mm.Calibrador().fit(X, y)
    p = str(tmp_path / "cabeca.pkl")
    cal.salvar(p)
    cal2 = mm.Calibrador.carregar(p)
    amostra = [0.8, 0.2, 0.5, 0.5, 0.0, 0.0]
    assert abs(cal._prob(amostra) - cal2._prob(amostra)) < 1e-9
