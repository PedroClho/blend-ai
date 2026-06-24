"""Testes das extensões de tipos (Fase 0 do roadmap de produto).

Campos novos são **opcionais com default None** → a construção antiga continua
válida (retrocompat) e nenhum consumidor existente (eval, pipeline) quebra.
Tudo puro: sem áudio, sem GPU.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blend.types import AlignmentPlan, ScoreCompat, Segment  # noqa: E402


def _plan(**kw) -> AlignmentPlan:
    base = dict(
        target_segment=Segment(0.0, 10.0, "full"),
        bpm_ratio=1.0,
        pitch_shift_semitones=0.0,
        vocal_offset=0.0,
    )
    base.update(kw)
    return AlignmentPlan(**base)


def _score(**kw) -> ScoreCompat:
    base = dict(
        total=0.8, harmonico=0.9, tempo=0.7, energia=None,
        camelot_dist=1, bpm_ratio=1.0,
    )
    base.update(kw)
    return ScoreCompat(**base)


# --------------------------------------------------------------------------- #
# AlignmentPlan.phrase_anchors (Fase 1a)
# --------------------------------------------------------------------------- #
def test_alignment_plan_phrase_anchors_default_none():
    assert _plan().phrase_anchors is None


def test_alignment_plan_phrase_anchors_armazena_lista():
    p = _plan(phrase_anchors=[(0.0, 4.0), (2.0, 6.0)])
    assert p.phrase_anchors == [(0.0, 4.0), (2.0, 6.0)]


# --------------------------------------------------------------------------- #
# ScoreCompat — campos aprendidos (Fase 2)
# --------------------------------------------------------------------------- #
def test_scorecompat_campos_novos_default_none():
    sc = _score()
    assert sc.learned_score is None
    assert sc.learned_score_rev is None
    assert sc.embed_sim is None


def test_scorecompat_aceita_campos_aprendidos():
    sc = _score(learned_score=0.42, learned_score_rev=0.31, embed_sim=0.5)
    assert sc.learned_score == 0.42
    assert sc.learned_score_rev == 0.31
    assert sc.embed_sim == 0.5


def test_scorecompat_retrocompat_construcao_antiga():
    # mesma forma usada por compatibility_score hoje (com `pesos`)
    sc = ScoreCompat(
        total=0.5, harmonico=0.5, tempo=0.5, energia=0.5,
        camelot_dist=0, bpm_ratio=1.0, pesos={"harmonico": 1.0},
    )
    assert sc.total == 0.5 and sc.pesos == {"harmonico": 1.0}
    assert sc.learned_score is None  # default não atrapalha a forma antiga


# --------------------------------------------------------------------------- #
# EmbedFeatures (Fase 2)
# --------------------------------------------------------------------------- #
def test_embedfeatures_constroi_minimo():
    from blend.types import EmbedFeatures

    ef = EmbedFeatures(emb_vocal=[0.1, 0.2], emb_instr=[0.3, 0.4])
    assert ef.emb_vocal == [0.1, 0.2]
    assert ef.emb_instr == [0.3, 0.4]
    assert ef.emb_vocal_b is None and ef.centroide is None


def test_embedfeatures_campos_opcionais():
    from blend.types import EmbedFeatures

    ef = EmbedFeatures(
        emb_vocal=[1.0], emb_instr=[2.0], emb_vocal_b=[3.0], emb_instr_a=[4.0],
        centroide=1500.0, mfcc=[0.0], rms_por_stem={"vocals": -12.0},
    )
    assert ef.emb_vocal_b == [3.0] and ef.emb_instr_a == [4.0]
    assert ef.centroide == 1500.0 and ef.rms_por_stem == {"vocals": -12.0}
