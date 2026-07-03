"""Ancoragem manual (DJ-in-the-loop): overrides sobre o plano + cache de análises.

Cobre a lógica pura da feature "ver + ancorar" (specs/ancoragem-manual.md):
`aplicar_ancoras_manuais` (re-rotulo da seção + marca 'manual'), a serialização
do cache por hash e a validação das âncoras na API. Nada aqui toca áudio/GPU.
"""
from __future__ import annotations

import pytest

from blend.pipeline import _secao_no_instante, aplicar_ancoras_manuais
from blend.types import AlignmentPlan, Segment, TrackAnalysis


def _plano() -> AlignmentPlan:
    return AlignmentPlan(
        target_segment=Segment(30.0, 60.0, "chorus"),
        bpm_ratio=1.02,
        pitch_shift_semitones=1.0,
        vocal_offset=31.5,
        mode="proposto",
        nivel_fallback=0,
        vocal_in=12.0,
        vocal_dur=29.0,
    )


def _base(segments: list[Segment] | None = None) -> TrackAnalysis:
    return TrackAnalysis(
        path="b.mp3",
        sr=44100,
        bpm=128.0,
        beats=[],
        downbeats=[0.0, 1.875, 3.75],
        segments=segments
        if segments is not None
        else [
            Segment(0.0, 30.0, "intro"),
            Segment(30.0, 60.0, "chorus"),
            Segment(60.0, 90.0, "break"),
            Segment(90.0, 180.0, "verse"),
        ],
    )


# --------------------------------------------------------------------------- #
# _secao_no_instante
# --------------------------------------------------------------------------- #
def test_secao_no_instante_acha_secao_que_contem_t():
    seg = _secao_no_instante(_base().segments, 75.0)
    assert seg is not None and seg.label == "break"


def test_secao_no_instante_fronteira_pertence_a_secao_que_comeca():
    seg = _secao_no_instante(_base().segments, 60.0)
    assert seg is not None and seg.label == "break"


def test_secao_no_instante_fora_de_todas_devolve_none():
    assert _secao_no_instante(_base().segments, 500.0) is None
    assert _secao_no_instante([], 10.0) is None


# --------------------------------------------------------------------------- #
# aplicar_ancoras_manuais
# --------------------------------------------------------------------------- #
def test_sem_ancoras_nao_muda_nada():
    plan = _plano()
    aplicar_ancoras_manuais(plan, _base(), None, None, None)
    assert plan.mode == "proposto"
    assert plan.vocal_offset == 31.5
    assert plan.target_segment.label == "chorus"


def test_offset_manual_marca_manual_e_rerotula_para_secao_do_break():
    plan = _plano()
    aplicar_ancoras_manuais(plan, _base(), None, None, 62.0)
    assert plan.mode == "manual"
    assert plan.vocal_offset == 62.0
    assert plan.target_segment.label == "break"
    assert plan.target_segment.start == 60.0


def test_so_recorte_manual_marca_manual_mas_preserva_secao_alvo():
    plan = _plano()
    aplicar_ancoras_manuais(plan, _base(), 40.0, 15.0, None)
    assert plan.mode == "manual"
    assert plan.vocal_in == 40.0
    assert plan.vocal_dur == 15.0
    assert plan.target_segment.label == "chorus"  # posição em B não mudou


def test_offset_fora_das_secoes_cria_secao_sintetica_manual():
    plan = _plano()
    aplicar_ancoras_manuais(plan, _base(), None, None, 300.0)
    assert plan.mode == "manual"
    assert plan.target_segment.label == "manual"
    assert plan.target_segment.start == 300.0
    assert plan.target_segment.end > plan.target_segment.start


def test_base_sem_secoes_tambem_gera_sintetica():
    plan = _plano()
    aplicar_ancoras_manuais(plan, _base(segments=[]), None, None, 10.0)
    assert plan.target_segment.label == "manual"


# --------------------------------------------------------------------------- #
# Cache de análises (round-trip + política de completude)
# --------------------------------------------------------------------------- #
def _analise(segments: list[Segment]) -> TrackAnalysis:
    return TrackAnalysis(
        path="/tmp/x.mp3",
        sr=44100,
        bpm=127.5,
        beats=[0.1, 0.55],
        downbeats=[0.1, 1.98],
        segments=segments,
        key_camelot="6A",
    )


def test_cache_round_trip_preserva_analise(tmp_path):
    from api.analysis_cache import CacheAnalises

    cache = CacheAnalises(tmp_path)
    an = _analise([Segment(0.0, 30.0, "intro"), Segment(30.0, 60.0, "drop")])
    assert cache.salvar("abc123", an) is True

    lido = cache.carregar("abc123")
    assert lido is not None
    assert lido.bpm == an.bpm
    assert lido.key_camelot == "6A"
    assert lido.downbeats == an.downbeats
    assert [(s.start, s.end, s.label) for s in lido.segments] == [
        (0.0, 30.0, "intro"),
        (30.0, 60.0, "drop"),
    ]


def test_cache_nao_salva_analise_degradada_sem_secoes(tmp_path):
    from api.analysis_cache import CacheAnalises

    cache = CacheAnalises(tmp_path)
    assert cache.salvar("abc123", _analise([])) is False
    assert cache.carregar("abc123") is None


def test_cache_miss_em_json_corrompido_ou_versao_antiga(tmp_path):
    from api.analysis_cache import CacheAnalises

    cache = CacheAnalises(tmp_path)
    (tmp_path / "quebrado.json").write_text("{nao é json", encoding="utf-8")
    assert cache.carregar("quebrado") is None
    (tmp_path / "velho.json").write_text('{"versao": 0, "analise": {}}', encoding="utf-8")
    assert cache.carregar("velho") is None


def test_hash_arquivo_estavel_e_sensivel_ao_conteudo(tmp_path):
    from api.analysis_cache import hash_arquivo

    p1, p2 = tmp_path / "a.bin", tmp_path / "b.bin"
    p1.write_bytes(b"blend" * 1000)
    p2.write_bytes(b"blend" * 1000)
    assert hash_arquivo(p1) == hash_arquivo(p2)  # mesmo conteúdo, nomes diferentes
    p2.write_bytes(b"BLEND" * 1000)
    assert hash_arquivo(p1) != hash_arquivo(p2)


# --------------------------------------------------------------------------- #
# Validação das âncoras na API
# --------------------------------------------------------------------------- #
def test_validar_ancoras_aceita_valores_sensatos():
    from api.server import _validar_ancoras

    _validar_ancoras(None, None, None)
    _validar_ancoras(12.0, 30.0, 61.9)
    _validar_ancoras(0.0, 0.05, 0.0)


@pytest.mark.parametrize(
    "vin,vdur,voff",
    [
        (-1.0, None, None),
        (None, 0.0, None),
        (None, -5.0, None),
        (None, 601.0, None),
        (None, None, -0.1),
        (99999.0, None, None),
        (float("nan"), None, None),
        (None, float("nan"), None),
    ],
)
def test_validar_ancoras_rejeita_fora_de_faixa(vin, vdur, voff):
    from fastapi import HTTPException

    from api.server import _validar_ancoras

    with pytest.raises(HTTPException):
        _validar_ancoras(vin, vdur, voff)
