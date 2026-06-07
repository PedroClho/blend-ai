"""Matriz de compatibilidade (H2) sobre o ground truth do Rekordbox.

Demonstra o score de compatibilidade com dados **reais** (BPM + Camelot das
faixas), sem precisar de áudio/Docker — o componente de energia fica de fora
(injetado pelo pipeline em produção). Lê `data/rekordbox/groundtruth.csv`.

Uso: ``python eval/matriz_compatibilidade.py``
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from blend.compatibility import compatibility_score  # noqa: E402
from blend.types import TrackAnalysis  # noqa: E402

CSV = ROOT / "data" / "rekordbox" / "groundtruth.csv"


def carregar() -> list[dict]:
    faixas: list[dict] = []
    with open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            titulo = r["titulo"].split(" (")[0].split(" [")[0]
            faixas.append(
                {
                    "rotulo": f'{titulo} ({r["camelot"]}/{float(r["bpm"]):.0f})',
                    "titulo": titulo,
                    "bpm": float(r["bpm"]),
                    "camelot": r["camelot"],
                    "genero": r["genero"],
                }
            )
    return faixas


def track(fx: dict) -> TrackAnalysis:
    return TrackAnalysis(path=fx["titulo"], sr=44100, bpm=fx["bpm"], key_camelot=fx["camelot"])


def main() -> None:
    faixas = carregar()
    n = len(faixas)
    pares = []  # score simétrico em harmônico+tempo → pares não-ordenados
    for i in range(n):
        for j in range(i + 1, n):
            sc = compatibility_score(track(faixas[i]), track(faixas[j]))
            pares.append((sc.total, faixas[i], faixas[j], sc))
    pares.sort(key=lambda x: -x[0])

    print(f"\n=== Matriz de compatibilidade (H2) — {n} faixas, {len(pares)} pares ===")
    print("(sem energia/áudio: score = harmônico + tempo, pesos renormalizados)\n")

    print("TOP 10 pares mais compatíveis:")
    for total, a, b, sc in pares[:10]:
        print(f"  {total:.3f}  {a['rotulo']}  +  {b['rotulo']}   (harm {sc.harmonico:.2f} · tempo {sc.tempo:.2f})")

    print("\n10 pares menos compatíveis:")
    for total, a, b, sc in pares[-10:]:
        print(f"  {total:.3f}  {a['rotulo']}  +  {b['rotulo']}   (harm {sc.harmonico:.2f} · tempo {sc.tempo:.2f})")

    funk = next((fx for fx in faixas if fx["genero"].lower().startswith("eletrofunk")), None)
    if funk:
        print(f"\nMelhores bases para o VOCAL do funk — {funk['rotulo']}:")
        ranking = []
        for fx in faixas:
            if fx is funk:
                continue
            sc = compatibility_score(track(funk), track(fx))
            ranking.append((sc.total, fx, sc))
        ranking.sort(key=lambda x: -x[0])
        for total, fx, sc in ranking[:5]:
            print(f"  {total:.3f}  -> {fx['rotulo']}   (harm {sc.harmonico:.2f} · tempo {sc.tempo:.2f})")


if __name__ == "__main__":
    main()
