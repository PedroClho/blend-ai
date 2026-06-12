"""Testes da síntese (recorte/fades/ganho/mix) e da detecção de atividade vocal.

Tudo com áudio sintético e bpm_ratio=1.0 / pitch=0 — não dependem do binário
rubberband nem de modelos.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend.pipeline import _inicio_atividade_vocal  # noqa: E402
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
# _inicio_atividade_vocal
# --------------------------------------------------------------------------- #
def test_atividade_detecta_inicio_apos_silencio():
    t = np.arange(3 * SR) / SR
    seno = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    voc = np.concatenate([np.zeros(2 * SR, dtype=np.float32), seno])[np.newaxis, :]
    ini = _inicio_atividade_vocal(voc, SR)
    assert ini is not None
    assert 1.8 <= ini <= 2.2


def test_atividade_silencio_total_retorna_none():
    voc = np.zeros((1, 2 * SR), dtype=np.float32)
    assert _inicio_atividade_vocal(voc, SR) is None


def test_atividade_ignora_estalo_curto():
    voc = np.zeros((1, 3 * SR), dtype=np.float32)
    voc[0, SR : SR + SR // 10] = 0.8  # estalo de 100 ms < min_dur_s=400 ms
    assert _inicio_atividade_vocal(voc, SR) is None


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
