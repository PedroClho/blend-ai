"""Testes da síntese (recorte/fades/ganho/mix) e da detecção de atividade vocal.

Tudo com áudio sintético e bpm_ratio=1.0 / pitch=0 — não dependem do binário
rubberband nem de modelos.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend.pipeline import _melhor_janela_vocal  # noqa: E402
from blend.synthesis import _recortar, render  # noqa: E402
from blend.types import AlignmentPlan, Segment  # noqa: E402

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
    # vocal: 1s silêncio + 2s de "voz" constante; recorte em [1s, 2s)
    voc = np.zeros((1, 3 * SR), dtype=np.float32)
    voc[0, SR:] = 0.5
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
    voc = 0.9 * np.ones((1, SR), dtype=np.float32)
    instr = 0.9 * np.ones((1, 2 * SR), dtype=np.float32)
    stems = {"vocals": np.zeros((1, 2 * SR), dtype=np.float32), "drums": instr}
    plan = _plan(vocal_offset=0.0, vocal_in=0.0, vocal_dur=None)
    mix = render(voc, stems, SR, plan)
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6
