"""Gera os estímulos do experimento subjetivo (P4) — em lote, cego e resumível.

Para N pares (A=vocal × B=base, |ΔBPM|≤3, estratificados por score), gera os dois
braços (baseline + proposto), excerta ~30 s na entrada do vocal, normaliza o
loudness e salva com ID aleatório. Escreve o gabarito (condição↔ID), um template
de respostas e ordens de apresentação randomizadas por avaliador.

Uso:
    python eval/gera_estimulos.py --listar         # só lista os pares (sem GPU)
    python eval/gera_estimulos.py --n 12 --dur 30  # gera tudo (GPU, ~2 min/braço)
Ver `specs/experimento-subjetivo.md`.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from eval.estimulos import (  # noqa: E402
    carregar_groundtruth,
    casar_arquivo,
    excerto,
    normalizar_rms,
    selecionar_pares,
)

DIR_EXP = ROOT / "data" / "experimento"
DIR_WAV = DIR_EXP / "estimulos"


def _escrever_csv(path: Path, campos: list[str], linhas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera estímulos do experimento (P4)")
    ap.add_argument("--n", type=int, default=12, help="nº de pares")
    ap.add_argument("--dur", type=float, default=30.0, help="duração do excerto (s)")
    ap.add_argument("--avaliadores", type=int, default=10, help="nº de ordens cegas")
    ap.add_argument("--seed", type=int, default=20260612)
    ap.add_argument("--listar", action="store_true", help="só lista os pares e sai")
    args = ap.parse_args()

    faixas = carregar_groundtruth()
    pares = selecionar_pares(faixas, n=args.n)
    if not pares:
        print("[gera] nenhum par elegível (cheque data/raw/bases e o groundtruth).")
        return

    print(f"[gera] {len(pares)} pares selecionados (|ΔBPM|≤3, estratificados por score):")
    for i, par in enumerate(pares):
        a, b, sc = par["a"], par["b"], par["score"]
        print(f"  par{i+1:02d}  score={sc.total:.2f}  camelot_dist={sc.camelot_dist}  "
              f"ΔBPM={abs(a['bpm']-b['bpm']):.0f}  | {a['nucleo']} ({a['camelot']}) "
              f"× {b['nucleo']} ({b['camelot']})")
    if args.listar:
        return

    from blend import io as bio
    from blend.pipeline import make_mashup

    DIR_WAV.mkdir(parents=True, exist_ok=True)
    unidades = [
        (f"par{i+1:02d}", par, cond)
        for i, par in enumerate(pares)
        for cond in ("baseline", "proposto")
    ]
    ids = [f"est_{k+1:02d}" for k in range(len(unidades))]
    random.Random(args.seed).shuffle(ids)  # ID não revela a condição

    gab: list[dict] = []
    for (par_id, par, cond), est_id in zip(unidades, ids):
        a, b, sc = par["a"], par["b"], par["score"]
        pa, pb = casar_arquivo(a), casar_arquivo(b)
        wav_out = DIR_WAV / f"{est_id}.wav"
        if pa is None or pb is None:
            print(f"[gera] {est_id} {par_id}: arquivo faltando, pulando")
            continue
        if not wav_out.exists():
            res = make_mashup(str(pa), str(pb), mode=cond)
            ex = normalizar_rms(
                excerto(res.mashup, res.sr, centro_s=res.plan.vocal_offset, dur_s=args.dur)
            )
            bio.save_audio(str(wav_out), ex, res.sr)
            print(f"[gera] {est_id}  {par_id}  {cond:9s}  {a['nucleo']} × {b['nucleo']}")
        else:
            print(f"[gera] {est_id} já existe — pulando")
        gab.append(
            {
                "estimulo_id": est_id,
                "par_id": par_id,
                "condicao": cond,
                "vocal": a["nucleo"],
                "base": b["nucleo"],
                "score": round(sc.total, 4),
                "camelot_dist": sc.camelot_dist,
            }
        )

    _escrever_csv(
        DIR_EXP / "gabarito.csv",
        ["estimulo_id", "par_id", "condicao", "vocal", "base", "score", "camelot_dist"],
        sorted(gab, key=lambda r: r["estimulo_id"]),
    )
    # template de respostas (Likert 1–5) — uma linha por (avaliador, estímulo)
    _escrever_csv(
        DIR_EXP / "respostas_template.csv",
        ["avaliador", "estimulo_id", "qualidade", "musicalidade", "artefatos"],
        [{"avaliador": "ex_dj1", "estimulo_id": gab[0]["estimulo_id"],
          "qualidade": "", "musicalidade": "", "artefatos": ""}] if gab else [],
    )
    # ordens de apresentação cegas, uma por avaliador
    for k in range(args.avaliadores):
        ordem = [r["estimulo_id"] for r in gab]
        random.Random(args.seed + 1 + k).shuffle(ordem)
        _escrever_csv(
            DIR_EXP / f"ordem_avaliador_{k+1:02d}.csv",
            ["posicao", "estimulo_id"],
            [{"posicao": p + 1, "estimulo_id": eid} for p, eid in enumerate(ordem)],
        )

    print(f"\n[gera] {len(gab)} estímulos + gabarito + {args.avaliadores} ordens "
          f"em {DIR_EXP}")


if __name__ == "__main__":
    main()
