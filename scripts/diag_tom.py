"""Diagnostico rapido: tom -> Camelot detectado (Essentia) de cada faixa passada.

Sem Demucs/allin1 — so carrega o audio e roda a estimativa de tom. Util pra
checar se a distancia harmonica do score vem de tom real ou de erro de deteccao.

Uso: python scripts/diag_tom.py <a.mp3> <b.mp3> ...
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from blend import io, key  # noqa: E402


def main() -> None:
    for p in sys.argv[1:]:
        try:
            s, _ = io.load_audio(p, sr=44100, mono=False)
            cam = key.estimate_key(s, 44100)
            print(f"{Path(p).name}  ->  Camelot {cam}")
        except Exception as e:  # noqa: BLE001
            print(f"{Path(p).name}  ->  ERRO: {e}")


if __name__ == "__main__":
    main()
