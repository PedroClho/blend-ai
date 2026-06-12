"""Testes da conversão de tom → Camelot (lógica pura, sem áudio)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

from blend.key import (  # noqa: E402
    _tonality_to_camelot,
    pitch_shift_para_compatibilizar,
    to_camelot,
)


@pytest.mark.parametrize(
    "nota,escala,esperado",
    [
        ("A", "minor", "8A"),
        ("C", "major", "8B"),
        ("F#", "minor", "11A"),
        ("Gb", "minor", "11A"),  # enarmônico de F#
        ("Bb", "minor", "3A"),
        ("A#", "minor", "3A"),  # enarmônico de Bb
        ("D", "major", "10B"),
        ("E", "minor", "9A"),
        ("Ab", "minor", "1A"),
        ("G#", "minor", "1A"),  # enarmônico de Ab
        ("G", "major", "9B"),
    ],
)
def test_to_camelot(nota, escala, esperado):
    assert to_camelot(nota, escala) == esperado


def test_to_camelot_idempotente():
    assert to_camelot("8A", "") == "8A"
    assert to_camelot("12B", "minor") == "12B"


def test_to_camelot_nota_invalida():
    with pytest.raises(ValueError):
        to_camelot("H", "minor")


@pytest.mark.parametrize(
    "tonality,esperado",
    [
        ("Am", "8A"),
        ("A", "11B"),  # A maior
        ("F#m", "11A"),
        ("Cmaj", "8B"),
        ("Gm", "6A"),
        ("8A", "8A"),  # já em Camelot
        ("Bbm", "3A"),
    ],
)
def test_tonality_rekordbox(tonality, esperado):
    assert _tonality_to_camelot(tonality) == esperado


@pytest.mark.parametrize(
    "vocal,base,esperado",
    [
        ("8A", "8A", 0.0),  # mesma célula
        ("8A", "9A", 0.0),  # vizinho na roda
        ("9A", "8A", 0.0),
        ("8A", "8B", 0.0),  # relativa
        ("1A", "5A", -1.0),  # 1A−1st = 6A, vizinho de 5A (menor |s|)
        ("6A", "8A", 2.0),  # 6A+2st = 8A (mesma célula)
        ("12A", "1A", 0.0),  # vizinhos na fronteira 12↔1
        ("1B", "12B", 0.0),
    ],
)
def test_pitch_shift_para_compatibilizar(vocal, base, esperado):
    assert pitch_shift_para_compatibilizar(vocal, base) == esperado


def test_pitch_shift_resultado_e_minimo():
    # qualquer par: |shift| nunca passa de 3 semitons (sempre há alvo a ≤3 st)
    for nv in range(1, 13):
        for nb in range(1, 13):
            s = pitch_shift_para_compatibilizar(f"{nv}A", f"{nb}A")
            assert abs(s) <= 3.0


def test_pitch_shift_camelot_invalido():
    with pytest.raises(ValueError):
        pitch_shift_para_compatibilizar("13A", "8A")
