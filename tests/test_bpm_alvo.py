"""BPM alvo: base E vocal esticados para o BPM final escolhido pelo usuário.

Cobre `aplicar_bpm_alvo` (recalcula o ratio do vocal contra o alvo com
half/double-time, estica a base e converte o offset para o relógio esticado)
e a validação do parâmetro na API. Nada aqui toca áudio/GPU.
"""
from __future__ import annotations

import pytest

from blend.pipeline import aplicar_bpm_alvo
from blend.types import AlignmentPlan, Segment


def _plano(offset: float = 120.0, ratio: float = 120.0 / 128.0) -> AlignmentPlan:
    return AlignmentPlan(
        target_segment=Segment(100.0, 160.0, "inst"),
        bpm_ratio=ratio,
        pitch_shift_semitones=0.0,
        vocal_offset=offset,
        mode="manual",
    )


def test_sem_alvo_e_noop():
    plan = _plano()
    aplicar_bpm_alvo(plan, bpm_vocal=128.0, bpm_base=120.0, bpm_alvo=None)
    assert plan.base_ratio == 1.0
    assert plan.bpm_alvo is None
    assert plan.vocal_offset == 120.0
    assert plan.bpm_ratio == pytest.approx(120.0 / 128.0)


def test_alvo_igual_a_base_nao_estica_base():
    plan = _plano()
    aplicar_bpm_alvo(plan, bpm_vocal=128.0, bpm_base=120.0, bpm_alvo=120.0)
    assert plan.base_ratio == pytest.approx(1.0)
    assert plan.vocal_offset == pytest.approx(120.0)
    assert plan.bpm_ratio == pytest.approx(120.0 / 128.0)  # vocal mira o alvo (=base)


def test_alvo_acima_estica_base_e_converte_offset():
    plan = _plano(offset=120.0)
    aplicar_bpm_alvo(plan, bpm_vocal=128.0, bpm_base=120.0, bpm_alvo=126.0)
    assert plan.base_ratio == pytest.approx(1.05)
    assert plan.bpm_alvo == 126.0
    # âncora escolhida no relógio original de B → relógio esticado (t/ratio)
    assert plan.vocal_offset == pytest.approx(120.0 / 1.05)
    # vocal recalculado direto contra o alvo
    assert plan.bpm_ratio == pytest.approx(126.0 / 128.0)


def test_half_double_contra_o_alvo():
    # vocal 65 bpm com alvo 130: f=2 → ratio exatamente 1.0 (sem esticar o vocal)
    plan = _plano(ratio=1.0)
    aplicar_bpm_alvo(plan, bpm_vocal=65.0, bpm_base=124.0, bpm_alvo=130.0)
    assert plan.bpm_ratio == pytest.approx(1.0)
    assert plan.base_ratio == pytest.approx(130.0 / 124.0)


def test_sem_bpm_do_vocal_acompanha_o_alvo_pelo_ratio_antigo():
    plan = _plano(ratio=0.9)
    aplicar_bpm_alvo(plan, bpm_vocal=0.0, bpm_base=120.0, bpm_alvo=132.0)
    assert plan.base_ratio == pytest.approx(1.1)
    assert plan.bpm_ratio == pytest.approx(0.9 * 1.1)


def test_base_sem_bpm_e_noop():
    plan = _plano()
    aplicar_bpm_alvo(plan, bpm_vocal=128.0, bpm_base=0.0, bpm_alvo=126.0)
    assert plan.base_ratio == 1.0
    assert plan.vocal_offset == 120.0


def test_validar_bpm_alvo_aceita_faixa_de_dj():
    from api.server import _validar_bpm_alvo

    _validar_bpm_alvo(None)
    _validar_bpm_alvo(40.0)
    _validar_bpm_alvo(128.0)
    _validar_bpm_alvo(220.0)


@pytest.mark.parametrize("v", [39.9, 220.1, -10.0, 0.0, float("nan")])
def test_validar_bpm_alvo_rejeita_fora_de_faixa(v):
    from fastapi import HTTPException

    from api.server import _validar_bpm_alvo

    with pytest.raises(HTTPException):
        _validar_bpm_alvo(v)
