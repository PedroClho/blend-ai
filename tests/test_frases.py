"""Testes da sincronização frase-a-frase (Fase 1a).

Tudo sintético; render usa bpm_ratio=1.0/pitch=0 (não chama o binário rubberband).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from blend import synthesis  # noqa: E402
from blend.types import AlignmentPlan, Segment  # noqa: E402

SR = 44100


def _tom(dur_s: float, freq: float = 440.0, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(dur_s * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _sil(dur_s: float) -> np.ndarray:
    return np.zeros(int(dur_s * SR), dtype=np.float32)


# --------------------------------------------------------------------------- #
# _detectar_frases
# --------------------------------------------------------------------------- #
def test_detectar_frases_conta_3_blocos():
    # 3 tons de 1 s separados por 0,5 s de silêncio (gap >= min_gap)
    y = np.concatenate([_tom(1.0), _sil(0.5), _tom(1.0), _sil(0.5), _tom(1.0)])
    frases = synthesis._detectar_frases(y[np.newaxis, :], SR)
    assert len(frases) == 3
    # 1ª frase começa ~0 e termina ~1 s
    ini0, fim0 = frases[0]
    assert ini0 < 0.15 and abs(fim0 - 1.0) < 0.15


def test_detectar_frases_funde_frase_curta():
    # bloco de 0,2 s (< min_frase) + gap 0,4 s + bloco de 1,0 s → funde em 1 frase
    y = np.concatenate([_tom(0.2), _sil(0.4), _tom(1.0)])
    frases = synthesis._detectar_frases(y[np.newaxis, :], SR)
    assert len(frases) == 1
    ini, fim = frases[0]
    assert ini < 0.15 and fim > 1.5  # frase fundida cobre do início ao fim do 2º bloco


def test_detectar_frases_silencio_total_retorna_vazio():
    assert synthesis._detectar_frases(_sil(3.0)[np.newaxis, :], SR) == []


def test_detectar_frases_tudo_ativo_uma_frase():
    y = _tom(2.0)
    frases = synthesis._detectar_frases(y[np.newaxis, :], SR)
    assert len(frases) == 1
    ini, fim = frases[0]
    assert ini < 0.1 and abs(fim - 2.0) < 0.15


def test_detectar_frases_ignora_bleed_fraco():
    # vazamento fraco (-60 dB ~ 0,001) o tempo todo + 2 blocos fortes (0,5)
    rng = np.random.default_rng(3)
    total = 2.5
    y = (0.001 * rng.standard_normal(int(total * SR))).astype(np.float32)
    y[: int(0.8 * SR)] += _tom(0.8)
    y[int(1.5 * SR) : int(1.5 * SR) + int(0.8 * SR)] += _tom(0.8)
    frases = synthesis._detectar_frases(y[np.newaxis, :], SR)
    assert len(frases) == 2  # o bleed entre/around os blocos não vira frase


def test_detectar_frases_estereo_vira_mono():
    y = _tom(1.0)
    est = np.stack([y, y])  # (2, n)
    frases = synthesis._detectar_frases(est, SR)
    assert len(frases) == 1


# --------------------------------------------------------------------------- #
# sincronizar_frases
# --------------------------------------------------------------------------- #
def _voc_2frases() -> np.ndarray:
    # frase em [0,1)s e [2,3)s (1 s de silêncio entre → 2 frases: t_voc=0.0 e 2.0)
    y = np.concatenate([_tom(1.0), _sil(1.0), _tom(1.0)])
    return y[np.newaxis, :]


def _plan(**kw) -> AlignmentPlan:
    base = dict(
        target_segment=Segment(0.0, 20.0, "full"),
        bpm_ratio=1.0,
        pitch_shift_semitones=0.0,
        vocal_offset=4.0,
    )
    base.update(kw)
    return AlignmentPlan(**base)


def test_sincronizar_frases_primeira_ancora_e_o_vocal_offset():
    plan = _plan(vocal_offset=5.0)
    anc = synthesis.sincronizar_frases(
        _voc_2frases(), SR, plan, base_downbeats=[0, 2, 4, 5, 6, 8], bpm_base=120.0
    )
    assert len(anc) == 2
    assert abs(anc[0][0] - 0.0) < 0.1  # t_voc da 1ª frase ~0
    assert abs(anc[0][1] - 5.0) < 1e-6  # 1ª frase entra exatamente no vocal_offset


def test_sincronizar_frases_snap_perto_de_downbeat():
    # derivado da 2ª frase = vocal_offset(4) + (2-0)/1 = 6.0; downbeat 6.05 dentro da tol
    plan = _plan(vocal_offset=4.0, bpm_ratio=1.0)
    anc = synthesis.sincronizar_frases(
        _voc_2frases(), SR, plan,
        base_downbeats=[0.0, 2.0, 4.0, 6.05, 8.0, 10.0], bpm_base=120.0,
    )
    assert abs(anc[1][1] - 6.05) < 1e-6  # snap no downbeat próximo


def test_sincronizar_frases_nao_forca_quando_longe():
    # sem downbeat perto de 6.0 (grade 0,2,4,8,10) → mantém a posição derivada
    plan = _plan(vocal_offset=4.0, bpm_ratio=1.0)
    anc = synthesis.sincronizar_frases(
        _voc_2frases(), SR, plan,
        base_downbeats=[0.0, 2.0, 4.0, 8.0, 10.0], bpm_base=120.0,
    )
    assert abs(anc[1][1] - 6.0) < 1e-6  # derivado, não forçado


def test_sincronizar_frases_restringe_a_target_segment():
    # 2ª frase em [2.9,3.9) → derivado = 4 + 2.9 = 6.9; o downbeat 7.05 (FORA da seção,
    # end 7.0) é o globalmente mais próximo e DEVE ser ignorado → snap no 6.05 (dentro)
    y = np.concatenate([_tom(1.0), _sil(1.9), _tom(1.0)])
    voc = y[np.newaxis, :]
    plan = _plan(target_segment=Segment(4.0, 7.0, "chorus"), vocal_offset=4.0, bpm_ratio=1.0)
    anc = synthesis.sincronizar_frases(
        voc, SR, plan,
        base_downbeats=[4.0, 6.05, 7.05, 9.0], bpm_base=120.0,
    )
    assert abs(anc[1][1] - 6.05) < 1e-6  # só downbeats dentro da seção
    assert all(abs(b - 7.05) > 1e-6 for _, b in anc)  # nunca o de fora


def test_sincronizar_frases_sem_downbeats_retorna_vazio():
    plan = _plan()
    assert synthesis.sincronizar_frases(_voc_2frases(), SR, plan, base_downbeats=[], bpm_base=120.0) == []


# --------------------------------------------------------------------------- #
# render frase-a-frase
# --------------------------------------------------------------------------- #
def _stems_zeros(dur_s: float) -> dict:
    return {
        "vocals": _sil(dur_s)[np.newaxis, :],
        "other": _sil(dur_s)[np.newaxis, :],
    }


def _plan_render(**kw) -> AlignmentPlan:
    base = dict(
        target_segment=Segment(0.0, 20.0, "full"),
        bpm_ratio=1.0,
        pitch_shift_semitones=0.0,
        vocal_offset=0.0,
        vocal_in=0.0,
        vocal_dur=None,
    )
    base.update(kw)
    return AlignmentPlan(**base)


def test_render_frase_a_frase_posiciona_cada_frase():
    # recorte = clip inteiro; frases t_voc 0.0 e 2.0 colocadas em 2.0s e 6.0s
    voc = _voc_2frases()
    stems = _stems_zeros(10.0)
    plan = _plan_render(phrase_anchors=[(0.0, 2.0), (2.0, 6.0)])
    mix = synthesis.render(voc, stems, SR, plan)
    e = lambda a, b: float(np.max(np.abs(mix[:, int(a * SR) : int(b * SR)])))  # noqa: E731
    assert e(0.0, 1.9) < 1e-3   # antes da 1ª frase: silêncio
    assert e(2.0, 2.5) > 0.1    # 1ª frase entra em 2.0s
    assert e(4.5, 5.5) < 1e-3   # vão entre as frases: silêncio
    assert e(6.0, 6.5) > 0.1    # 2ª frase entra em 6.0s


def test_render_frase_a_frase_sem_clipping():
    voc = _voc_2frases()
    instr = (0.9 * np.ones((1, 10 * SR))).astype(np.float32)
    stems = {"vocals": _sil(10.0)[np.newaxis, :], "drums": instr}
    plan = _plan_render(phrase_anchors=[(0.0, 1.0), (2.0, 4.0)])
    mix = synthesis.render(voc, stems, SR, plan)
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6


def test_render_phrase_anchors_vazio_cai_para_ancora_unica():
    # [] e None devem produzir EXATAMENTE o mesmo resultado (caminho de âncora única)
    voc = _voc_2frases()
    stems = _stems_zeros(10.0)
    mix_none = synthesis.render(voc, stems, SR, _plan_render(vocal_offset=2.0, phrase_anchors=None))
    mix_empty = synthesis.render(voc, stems, SR, _plan_render(vocal_offset=2.0, phrase_anchors=[]))
    assert np.array_equal(mix_none, mix_empty)
