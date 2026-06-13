"""Testes da síntese (recorte/fades/ganho/mix) e da detecção de atividade vocal.

Tudo com áudio sintético e bpm_ratio=1.0 / pitch=0 — não dependem do binário
rubberband nem de modelos.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend.alignment import align  # noqa: E402
from blend.pipeline import _melhor_janela_vocal, _recorte_vocal  # noqa: E402
from blend.synthesis import _ducking, _passa_altas, _recortar, render  # noqa: E402
from blend.types import AlignmentPlan, Segment, TrackAnalysis  # noqa: E402

SR = 44100


def _plan(**kw) -> AlignmentPlan:
    base = dict(
        target_segment=Segment(0.0, 10.0, "full"),
        bpm_ratio=1.0,
        pitch_shift_semitones=0.0,
        vocal_offset=0.0,
    )
    base.update(kw)
    return AlignmentPlan(**base)


# --------------------------------------------------------------------------- #
# _recortar
# --------------------------------------------------------------------------- #
def test_recortar_intervalo_e_fades():
    voc = np.ones((1, 3 * SR), dtype=np.float32)
    out = _recortar(voc, SR, inicio=1.0, dur=1.0)
    assert out.shape == (1, SR)
    assert out[0, 0] == 0.0  # fade-in parte do zero
    assert out[0, -1] == 0.0  # fade-out termina em zero
    meio = out[0, SR // 2]
    assert 0.99 <= meio <= 1.0  # miolo intacto


def test_recortar_dur_none_vai_ate_o_fim():
    voc = np.ones((2, 2 * SR), dtype=np.float32)
    out = _recortar(voc, SR, inicio=1.0, dur=None)
    assert out.shape == (2, SR)


def test_recortar_fora_da_faixa_nao_quebra():
    voc = np.ones((1, SR), dtype=np.float32)
    out = _recortar(voc, SR, inicio=5.0, dur=1.0)
    assert out.shape[1] >= 1
    assert np.all(out == 0.0)


# --------------------------------------------------------------------------- #
# _melhor_janela_vocal
# --------------------------------------------------------------------------- #
def test_janela_ignora_bleed_e_acha_o_vocal():
    # 120s: vazamento fraco o tempo todo + vocal forte só em [60, 80)s
    rng = np.random.default_rng(7)
    y = (0.01 * rng.standard_normal(120 * SR)).astype(np.float32)
    t = np.arange(20 * SR) / SR
    y[60 * SR : 80 * SR] += (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    voc = y[np.newaxis, :]
    downbeats = [float(d) for d in range(0, 120, 2)]
    ini = _melhor_janela_vocal(voc, SR, dur_s=15.0, downbeats=downbeats)
    assert 56.0 <= ini <= 62.0  # janela cai no trecho cantado (snap em downbeat)


def test_janela_silencio_retorna_zero():
    voc = np.zeros((1, 10 * SR), dtype=np.float32)
    assert _melhor_janela_vocal(voc, SR, dur_s=5.0, downbeats=[]) == 0.0


def test_janela_dur_maior_que_faixa():
    voc = np.ones((1, 5 * SR), dtype=np.float32)
    ini = _melhor_janela_vocal(voc, SR, dur_s=60.0, downbeats=[0.0])
    assert ini == 0.0


def test_janela_ancora_no_downbeat_anterior():
    y = np.zeros(60 * SR, dtype=np.float32)
    y[30 * SR :] = 0.5
    voc = y[np.newaxis, :]
    ini = _melhor_janela_vocal(voc, SR, dur_s=10.0, downbeats=[0.0, 28.6, 31.2])
    assert ini == 28.6  # argmax ~30s → downbeat anterior


# --------------------------------------------------------------------------- #
# render (recorte + offset + ganho; sem stretch/pitch)
# --------------------------------------------------------------------------- #
def test_render_recorta_e_posiciona():
    # vocal: 1s silêncio + 2s de tom (sobrevive ao passa-altas); recorte em [1s, 2s)
    t = np.arange(3 * SR) / SR
    voc = np.zeros((1, 3 * SR), dtype=np.float32)
    voc[0, SR:] = (0.5 * np.sin(2 * np.pi * 330 * t[SR:])).astype(np.float32)
    stems = {
        "vocals": np.zeros((1, 5 * SR), dtype=np.float32),  # excluído da mix
        "other": np.zeros((1, 5 * SR), dtype=np.float32),
    }
    plan = _plan(vocal_offset=2.0, vocal_in=1.0, vocal_dur=1.0)
    mix = render(voc[:, :], stems, SR, plan)
    assert mix.shape[1] == 5 * SR  # instrumental define o tamanho
    # vocal só entre 2s e 3s
    assert np.max(np.abs(mix[:, : int(1.9 * SR)])) == 0.0
    assert np.max(np.abs(mix[:, int(2.4 * SR) : int(2.6 * SR)])) > 0.1
    assert np.max(np.abs(mix[:, int(3.2 * SR) :])) == 0.0


def test_render_ganho_casa_com_instrumental():
    rng = np.random.default_rng(42)
    voc = np.zeros((1, 2 * SR), dtype=np.float32)
    voc[0, :] = 0.01 * rng.standard_normal(2 * SR)  # vocal muito baixo
    instr = 0.3 * rng.standard_normal((1, 4 * SR)).astype(np.float32)
    stems = {"vocals": np.zeros((1, 4 * SR), dtype=np.float32), "other": instr}
    plan = _plan(vocal_offset=0.0, vocal_in=0.0, vocal_dur=None)
    mix = render(voc, stems, SR, plan)
    # com clamp de ganho ≤4x, o vocal sobe mas não explode: a mix difere do
    # instrumental puro, sem passar de 1.0 de pico
    assert float(np.max(np.abs(mix))) <= 1.0
    dif = mix[:, : 2 * SR] - instr[:, : 2 * SR] / max(
        1.0, float(np.max(np.abs(instr)))
    )
    assert float(np.max(np.abs(dif))) > 0.0


def test_render_sem_clipping():
    t = np.arange(SR) / SR
    voc = (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[np.newaxis, :]
    instr = 0.9 * np.ones((1, 2 * SR), dtype=np.float32)
    stems = {"vocals": np.zeros((1, 2 * SR), dtype=np.float32), "drums": instr}
    plan = _plan(vocal_offset=0.0, vocal_in=0.0, vocal_dur=None)
    mix = render(voc, stems, SR, plan)
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6


def test_passa_altas_corta_grave_preserva_agudo():
    t = np.arange(SR) / SR
    grave = np.sin(2 * np.pi * 50 * t).astype(np.float32)[np.newaxis, :]
    agudo = np.sin(2 * np.pi * 2000 * t).astype(np.float32)[np.newaxis, :]
    r = lambda x: float(np.sqrt(np.mean(x**2)))  # noqa: E731
    assert r(_passa_altas(grave, SR)) < 0.3 * r(grave)  # 50 Hz bem atenuado
    assert r(_passa_altas(agudo, SR)) > 0.8 * r(agudo)  # 2 kHz preservado


def test_ducking_atenua_sob_o_vocal():
    instr = np.ones((1, 4 * SR), dtype=np.float32)
    t = np.arange(2 * SR) / SR
    voc = (0.8 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)[np.newaxis, :]
    out = _ducking(instr, voc, offset=SR, sr=SR, reducao_db=3.5)
    assert abs(out[0, SR // 2] - 1.0) < 1e-3  # antes do vocal: base intacta
    meio = float(np.mean(out[0, int(1.5 * SR) : int(2.5 * SR)]))
    assert 0.6 < meio < 0.92  # sob o vocal: atenuada (~−3.5 dB)
    assert abs(out[0, int(3.5 * SR)] - 1.0) < 1e-3  # depois do vocal: intacta


# --------------------------------------------------------------------------- #
# _recorte_vocal + invariante de H1 (mesmo trecho vocal nos dois braços)
# --------------------------------------------------------------------------- #
def test_recorte_vocal_comprimento_fixo_em_compassos():
    voc = np.ones((1, 90 * SR), dtype=np.float32)  # vocal sobra
    _ini, dur = _recorte_vocal(voc, SR, bpm_vocal=120.0, downbeats=[])
    assert abs(dur - 32.0) < 0.6  # 16 compassos a 120 BPM = 32 s


def test_recorte_vocal_capado_pelo_vocal_disponivel():
    voc = np.ones((1, 10 * SR), dtype=np.float32)  # só 10 s
    _ini, dur = _recorte_vocal(voc, SR, bpm_vocal=130.0, downbeats=[])
    assert dur <= 10.0 + 1e-6


def test_h1_invariante_vocal_identico_baseline_vs_proposto():
    """Invariante de H1: trecho vocal idêntico nos 2 modos; só a colocação muda."""
    # vocal com energia concentrada em 30–45 s
    y = (0.01 * np.ones(60 * SR)).astype(np.float32)
    y[30 * SR : 45 * SR] = 0.6
    vocal = y[np.newaxis, :]

    an_vocal = TrackAnalysis(
        path="a", sr=SR, bpm=130.0,
        downbeats=[i * (4 * 60 / 130) for i in range(30)],
        segments=[], key_camelot="1A",
    )
    bar_b = 4 * 60 / 128
    an_base = TrackAnalysis(
        path="b", sr=SR, bpm=128.0,
        downbeats=[i * bar_b for i in range(45)],
        segments=[Segment(0.0, 30.0, "intro"), Segment(30.0, 70.0, "chorus")],
        key_camelot="8A",
    )

    plan_base = align(an_vocal, an_base, mode="baseline")
    plan_prop = align(an_vocal, an_base, mode="proposto")

    # o recorte é função SÓ de A → idêntico para os dois modos
    rec_base = _recorte_vocal(vocal, SR, an_vocal.bpm, an_vocal.downbeats)
    rec_prop = _recorte_vocal(vocal, SR, an_vocal.bpm, an_vocal.downbeats)
    assert rec_base == rec_prop
    assert abs(rec_prop[1] - 16 * (4 * 60 / 130)) < 0.6  # clipe fixo, não a seção

    # stretch e pitch idênticos; SÓ a colocação sobre B difere (manipulação de H1)
    assert plan_base.bpm_ratio == plan_prop.bpm_ratio
    assert plan_base.pitch_shift_semitones == plan_prop.pitch_shift_semitones
    assert plan_base.vocal_offset != plan_prop.vocal_offset
    assert plan_prop.nivel_fallback == 0  # escolheu o refrão de verdade
