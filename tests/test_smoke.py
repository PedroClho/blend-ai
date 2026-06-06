"""Smoke test — garante que o pacote importa e o contrato existe.

Substituir/expandir por testes reais por módulo (ver Fluxo de desenvolvimento no CLAUDE.md).
"""


def test_importa_pacote():
    import blend  # noqa: F401
    from blend import types

    assert hasattr(types, "TrackAnalysis")
    assert hasattr(types, "AlignmentPlan")


def test_segment_e_dataclass():
    from blend.types import Segment

    seg = Segment(start=0.0, end=8.0, label="intro")
    assert seg.label == "intro"
    assert seg.end > seg.start
