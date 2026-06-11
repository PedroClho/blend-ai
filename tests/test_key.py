"""Testes da conversão de tom → Camelot (lógica pura, sem áudio)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

from blend.key import _tonality_to_camelot, to_camelot  # noqa: E402


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
