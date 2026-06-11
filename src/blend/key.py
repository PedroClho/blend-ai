"""Estimação de tom (Essentia, perfil EDMA), mapeamento Camelot e leitura do Rekordbox.

A roda de Camelot: sufixo **A = menor**, **B = maior**; o número anda em quintas.
`to_camelot` é função pura (testável sem áudio). `estimate_key` usa Essentia.
`read_rekordbox_keys` lê o atributo Tonality de um rekordbox.xml.
"""
from __future__ import annotations

import numpy as np

# nota → pitch class (0..11), com enarmônicos
_NOTE_PC = {
    "C": 0, "B#": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3,
    "E": 4, "FB": 4, "F": 5, "E#": 5, "F#": 6, "GB": 6, "G": 7,
    "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11, "CB": 11,
}
# pitch class → Camelot (anda em quintas a partir de C=8B / Am=8A)
_PC_MAJOR = {0: "8B", 7: "9B", 2: "10B", 9: "11B", 4: "12B", 11: "1B",
             6: "2B", 1: "3B", 8: "4B", 3: "5B", 10: "6B", 5: "7B"}
_PC_MINOR = {9: "8A", 4: "9A", 11: "10A", 6: "11A", 1: "12A", 8: "1A",
             3: "2A", 10: "3A", 5: "4A", 0: "5A", 7: "6A", 2: "7A"}

_MINOR_TOKENS = {"MINOR", "MIN", "M", "AEOLIAN"}
_MAJOR_TOKENS = {"MAJOR", "MAJ", "", "IONIAN"}


def to_camelot(key: str, scale: str) -> str:
    """Converte tom musical (ex.: 'A', 'minor') para Camelot (ex.: '8A').

    Aceita também entrada já em Camelot ('8A') — devolve normalizada.
    Levanta ValueError se a nota for desconhecida.
    """
    k = (key or "").strip()
    # já é Camelot? (ex.: '8A', '12B')
    up = k.upper().replace(" ", "")
    if len(up) >= 2 and up[:-1].isdigit() and up[-1] in ("A", "B"):
        return f"{int(up[:-1])}{up[-1]}"

    # normaliza nota: primeira letra maiúscula + sufixo de acidente
    note = up
    if note and note[0] in "ABCDEFG":
        note = note[0] + note[1:].replace("♯", "#").replace("♭", "B")
    if note not in _NOTE_PC:
        raise ValueError(f"Nota desconhecida: {key!r}")
    pc = _NOTE_PC[note]

    s = (scale or "").strip().upper()
    if s in _MINOR_TOKENS:
        return _PC_MINOR[pc]
    if s in _MAJOR_TOKENS:
        return _PC_MAJOR[pc]
    raise ValueError(f"Escala desconhecida: {scale!r}")


def _tonality_to_camelot(tonality: str) -> str | None:
    """Interpreta o campo Tonality do Rekordbox ('Am', 'F#m', 'C', '8A', ...)."""
    t = (tonality or "").strip()
    if not t:
        return None
    up = t.upper().replace(" ", "")
    if len(up) >= 2 and up[:-1].isdigit() and up[-1] in ("A", "B"):
        return f"{int(up[:-1])}{up[-1]}"
    # modo: 'Am' / 'F#m' / 'min' → menor; 'maj' ou sem sufixo → maior
    if "MIN" in up:
        up, is_minor = up.replace("MIN", ""), True
    elif "MAJ" in up:
        up, is_minor = up.replace("MAJ", ""), False
    elif up.endswith("M"):
        up, is_minor = up[:-1], True
    else:
        is_minor = False
    try:
        return to_camelot(up, "minor" if is_minor else "major")
    except ValueError:
        return None


def read_rekordbox_keys(xml_path: str) -> dict[str, str]:
    """Lê o tom (atributo Tonality) por faixa de um rekordbox.xml → {Nome: Camelot}.

    Ground truth / atalho de tom no domínio-alvo (silver standard).
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    out: dict[str, str] = {}
    for track in tree.iter("TRACK"):
        name = track.get("Name")
        tonality = track.get("Tonality")
        if not name:
            continue
        cam = _tonality_to_camelot(tonality or "")
        if cam:
            out[name] = cam
    return out


def estimate_key(samples: np.ndarray, sr: int) -> str:
    """Estima o tom com Essentia (perfil EDMA) e retorna em Camelot (ex.: '8A').

    `samples` em (canais, amostras) ou (amostras,); converte para mono internamente.
    """
    import essentia.standard as es

    y = np.asarray(samples, dtype=np.float32)
    if y.ndim == 2:  # (canais, amostras) → mono
        y = y.mean(axis=0)
    y = np.ascontiguousarray(y, dtype=np.float32)

    key, scale, _strength = es.KeyExtractor(profileType="edma")(y)
    return to_camelot(key, scale)
