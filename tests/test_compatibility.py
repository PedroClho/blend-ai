"""Testes do score de compatibilidade (H2) — núcleo do motor de mashup (P2).

Tudo puro e determinístico: camelot e tempo não leem áudio; o componente de
energia recebe métricas injetadas (como o pipeline faria a partir do mix/stems).

Critério-fonte: specs/score-compatibilidade.md (Q1–Q4 FECHADAS).
"""
from __future__ import annotations

import pytest

from blend.compatibility import (
    ParamsScore,
    camelot_distance,
    comp_energia,
    comp_harmonico,
    comp_tempo,
    compatibility_score,
)
from blend.types import ScoreCompat, Segment, TrackAnalysis


def _track(bpm=128.0, key="8A", segs=None, path="x.wav"):
    return TrackAnalysis(
        path=path, sr=44100, bpm=bpm, key_camelot=key, segments=segs or []
    )


# --------------------------------------------------------------------------- #
# Q1 — distância Camelot (crua) + tabela de qualidade harmônica
# --------------------------------------------------------------------------- #
def test_camelot_distance_mesma_chave():
    assert camelot_distance("8A", "8A") == 0


def test_camelot_distance_relativo():
    assert camelot_distance("8A", "8B") == 1  # mesmo nº, troca de letra


def test_camelot_distance_vizinho():
    assert camelot_distance("8A", "9A") == 1  # ±1 mesma letra (quinta/quarta)
    assert camelot_distance("8A", "7A") == 1


def test_camelot_distance_wraparound():
    assert camelot_distance("12A", "1A") == 1  # roda circular


def test_camelot_distance_energy_boost():
    assert camelot_distance("8A", "10A") == 2  # +2 mesma letra


def test_camelot_distance_tritono():
    assert camelot_distance("1A", "7A") == 6  # +6 = máximo arco (tritono)


def test_camelot_distance_notacao_invalida_levanta():
    for bad in ("13A", "0A", "8C", "", "abc", "8"):
        with pytest.raises(ValueError):
            camelot_distance(bad, "8A")


def test_comp_harmonico_tabela_q1():
    # valores exatos da tabela do Q1
    assert comp_harmonico("8A", "8A") == pytest.approx(1.00)  # mesma
    assert comp_harmonico("8A", "8B") == pytest.approx(0.90)  # relativo
    assert comp_harmonico("8A", "9A") == pytest.approx(0.85)  # vizinho
    assert comp_harmonico("8A", "9B") == pytest.approx(0.55)  # vizinho diagonal
    assert comp_harmonico("8A", "10A") == pytest.approx(0.55)  # energy +2
    assert comp_harmonico("1A", "7A") == pytest.approx(0.05)  # tritono


def test_comp_harmonico_relativo_supera_vizinho_diagonal():
    # não-monotonia proposital: relativo (dist 1) > vizinho-diagonal (dist 2)
    assert comp_harmonico("8A", "8B") > comp_harmonico("8A", "9B")


def test_comp_harmonico_decaimento_geral():
    mesma = comp_harmonico("8A", "8A")
    relativo = comp_harmonico("8A", "8B")
    vizinho = comp_harmonico("8A", "9A")
    energy2 = comp_harmonico("8A", "10A")
    tritono = comp_harmonico("1A", "7A")
    assert mesma > relativo > vizinho >= energy2 > tritono
    assert tritono < 0.1


def test_comp_harmonico_tom_ausente_neutro():
    assert comp_harmonico(None, "8A") == 0.5
    assert comp_harmonico("xx", "8A") == 0.5
    assert comp_harmonico("8A", None) == 0.5


# --------------------------------------------------------------------------- #
# Q3/tempo — componente de tempo com half/double-time
# --------------------------------------------------------------------------- #
def test_comp_tempo_bpm_iguais():
    comp, ratio = comp_tempo(128.0, 128.0)
    assert comp == pytest.approx(1.0)
    assert ratio == pytest.approx(1.0)


def test_comp_tempo_tech_x_tech_alto():
    # 128 vs 126 -> stretch ~1.6% -> comp ~0.8
    comp, _ = comp_tempo(128.0, 126.0)
    assert comp > 0.75


def test_comp_tempo_half_double_resolve():
    # base=126, vocal=63 -> f=2 -> 126/126 = 1.0 (sem stretch)
    comp, ratio = comp_tempo(126.0, 63.0)
    assert ratio == pytest.approx(1.0)
    assert comp == pytest.approx(1.0)


def test_comp_tempo_gap_acima_do_limiar_zera():
    # 139 vs 128 -> stretch ~8.6% > max_stretch_pct=8 -> 0.0
    comp, _ = comp_tempo(139.0, 128.0)
    assert comp == pytest.approx(0.0)


def test_comp_tempo_bpm_invalido_neutro():
    comp, ratio = comp_tempo(0.0, 128.0)
    assert comp == 1.0
    assert ratio == 1.0


def test_comp_tempo_consistente_com_alinhamento():
    # mesma escolha de f que _escolher_bpm_ratio (reuso direto)
    from blend.alignment import _escolher_bpm_ratio

    _, ratio = comp_tempo(126.0, 63.0)
    assert ratio == pytest.approx(_escolher_bpm_ratio(126.0, 63.0))


# --------------------------------------------------------------------------- #
# Q2 — componente de energia (injetado e opcional)
# --------------------------------------------------------------------------- #
def test_comp_energia_iguais_um():
    assert comp_energia({"energia_a": -12.0, "energia_b": -12.0}) == pytest.approx(1.0)


def test_comp_energia_diferenca_tolerancia_zera():
    # diferença == energia_tol_db (6 dB) -> 0.0
    assert comp_energia({"energia_a": -10.0, "energia_b": -16.0}) == pytest.approx(0.0)


def test_comp_energia_diferenca_parcial():
    # 3 dB -> 0.5
    assert comp_energia({"energia_a": -10.0, "energia_b": -13.0}) == pytest.approx(0.5)


def test_comp_energia_ausente_none():
    assert comp_energia(None) is None
    assert comp_energia({}) is None
    assert comp_energia({"energia_a": -10.0}) is None


def test_comp_energia_nan_inf_none():
    # NaN/inf não pode escapar como casamento perfeito (envenenaria o Spearman do P4)
    assert comp_energia({"energia_a": float("nan"), "energia_b": -5.0}) is None
    assert comp_energia({"energia_a": -5.0, "energia_b": float("inf")}) is None


# --------------------------------------------------------------------------- #
# Combinação final + breakdown + paridade
# --------------------------------------------------------------------------- #
def test_score_par_ideal_alto():
    a = _track(bpm=128.0, key="8A")
    b = _track(bpm=128.0, key="8A")
    sc = compatibility_score(a, b, {"energia_a": -12.0, "energia_b": -12.0})
    assert isinstance(sc, ScoreCompat)
    assert sc.total > 0.95
    assert sc.harmonico == 1.0
    assert sc.tempo == pytest.approx(1.0)
    assert sc.energia == pytest.approx(1.0)
    assert sc.camelot_dist == 0


def test_score_par_ruim_baixo():
    # tritono + gap grande de BPM + energia díspar
    a = _track(bpm=139.0, key="1A")
    b = _track(bpm=128.0, key="7A")
    sc = compatibility_score(a, b, {"energia_a": -6.0, "energia_b": -18.0})
    assert sc.total < 0.1


def test_score_breakdown_e_pesos_somam_um():
    sc = compatibility_score(_track(), _track(), {"energia_a": -12.0, "energia_b": -12.0})
    assert 0.0 <= sc.total <= 1.0
    for c in (sc.harmonico, sc.tempo, sc.energia):
        assert 0.0 <= c <= 1.0
    assert sc.pesos["harmonico"] + sc.pesos["tempo"] + sc.pesos["energia"] == pytest.approx(1.0)


def test_score_paridade_sem_energia_redistribui():
    a, b = _track(), _track()
    sc = compatibility_score(a, b, metricas=None)
    assert sc.energia is None
    assert sc.pesos["energia"] == 0.0
    assert sc.pesos["harmonico"] + sc.pesos["tempo"] == pytest.approx(1.0)
    # renormalização correta: 0.50/0.85 e 0.35/0.85
    assert sc.pesos["harmonico"] == pytest.approx(0.50 / 0.85)
    assert sc.pesos["tempo"] == pytest.approx(0.35 / 0.85)
    # determinístico
    assert sc.total == compatibility_score(a, b, metricas=None).total


def test_score_harmonia_domina_pesos():
    p = ParamsScore()
    assert p.w_harmonico > p.w_tempo > p.w_energia
    assert p.w_harmonico + p.w_tempo + p.w_energia == pytest.approx(1.0)


def test_score_tom_ausente_nao_quebra():
    a = _track(key=None)
    b = _track(key="8A")
    sc = compatibility_score(a, b, {"energia_a": -12.0, "energia_b": -12.0})
    assert sc.harmonico == 0.5  # neutro
    assert sc.camelot_dist == -1  # sentinela
    assert 0.0 <= sc.total <= 1.0


def test_score_ordenacao_coerente():
    # relativo > energy(+2) > tritono no total, mantendo tempo/energia iguais
    base = _track(bpm=128.0, key="8A")
    metr = {"energia_a": -12.0, "energia_b": -12.0}
    relativo = compatibility_score(_track(key="8B"), base, metr).total
    energy = compatibility_score(_track(key="10A"), base, metr).total
    tritono = compatibility_score(_track(key="2A"), base, metr).total
    assert relativo > energy > tritono


def test_score_determinismo_repeticao():
    a, b = _track(key="9A"), _track(key="8A")
    r = [
        compatibility_score(a, b, {"energia_a": -11.0, "energia_b": -13.0}).total
        for _ in range(5)
    ]
    assert len(set(r)) == 1
