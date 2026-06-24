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
