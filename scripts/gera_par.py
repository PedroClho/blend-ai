"""Gera os DOIS braços (baseline + proposto) do MESMO par, para o checkpoint.

Vocal de A (separado) sobre o instrumental de B. Roda ``make_mashup`` duas vezes
mudando só o ``mode`` — baseline (alinhamento ingênuo) e proposto (estrutura-aware)
diferem apenas na COLOCAÇÃO do vocal sobre B; o conteúdo vocal é idêntico
(invariante da H1). Salva em ``data/out/`` com nomes descritivos.

Default: caso-guia do produto — vocal do funk 'Lost Eletrofunk' (6A/130) sobre a
base de tech house 'Swag' (6A/130), par de score 1.000 na matriz de compatibilidade.

Uso (dentro do container):
    python scripts/gera_par.py
    python scripts/gera_par.py --vocal <mp3> --base <mp3> --slug funk_x_swag
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from blend import io  # noqa: E402
from blend.pipeline import make_mashup  # noqa: E402

BASES = ROOT / "data" / "raw" / "bases"
FUNKS = ROOT / "data" / "raw" / "funks"
OUT = ROOT / "data" / "out"

VOCAL_DEFAULT = FUNKS / "DJ HUNCHER - Lost Eletrofunk.mp3"
BASE_DEFAULT = BASES / "Diego Bustamante - Swag (Extended Mix) [Glasgow Underground]_pn.mp3"


def _resumo(tag: str, res, dt: float) -> None:
    print(f"\n[{tag}] OK em {dt:.1f}s")
    print(
        f"[{tag}] score total={res.score.total:.3f} "
        f"harm={res.score.harmonico:.3f} tempo={res.score.tempo:.3f} "
        f"camelot_dist={res.score.camelot_dist}"
    )
    print(
        f"[{tag}] plan: ratio={res.plan.bpm_ratio:.4f} "
        f"offset={res.plan.vocal_offset:.2f}s nivel_fallback={res.plan.nivel_fallback} "
        f"secao='{res.plan.target_segment.label}' "
        f"[{res.plan.target_segment.start:.1f}-{res.plan.target_segment.end:.1f}s]"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera baseline + proposto do mesmo par.")
    ap.add_argument("--vocal", default=str(VOCAL_DEFAULT), help="MP3 fonte do VOCAL (A)")
    ap.add_argument("--base", default=str(BASE_DEFAULT), help="MP3 fonte do INSTRUMENTAL (B)")
    ap.add_argument("--slug", default="funk_x_swag", help="prefixo dos arquivos de saida")
    ap.add_argument(
        "--compassos", type=int, default=16,
        help="tamanho do recorte vocal em compassos (16~30s @127bpm; menor p/ vocal curto)",
    )
    ap.add_argument(
        "--modos", default="baseline,proposto",
        help="modos a gerar, separados por virgula (ex.: 'proposto' p/ so um braco)",
    )
    ap.add_argument(
        "--sem-transposicao", action="store_true",
        help="H3: nao transpoe (pitch_shift=0), p/ vocal declamado ou tom mal estimado",
    )
    ap.add_argument("--vocal-in", type=float, default=None, help="override: inicio do vocal em A (segundos)")
    ap.add_argument("--vocal-dur", type=float, default=None, help="override: duracao do vocal em A (segundos)")
    ap.add_argument("--vocal-offset", type=float, default=None, help="override: posicao do vocal na base B (segundos)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    vocal, base = Path(args.vocal), Path(args.base)
    print(f"[gera] vocal = {vocal.name}")
    print(f"[gera] base  = {base.name}")

    transpor = not args.sem_transposicao
    suf = "_nt" if args.sem_transposicao else ""
    print(f"[gera] recorte = {args.compassos} compassos | transpor = {transpor}")
    modos = [m.strip() for m in args.modos.split(",") if m.strip()]
    for modo in modos:
        t0 = time.time()
        res = make_mashup(
            str(vocal), str(base), mode=modo, compassos=args.compassos, transpor=transpor,
            vocal_in=args.vocal_in, vocal_dur=args.vocal_dur, vocal_offset=args.vocal_offset,
        )
        dt = time.time() - t0
        destino = OUT / f"{args.slug}_{modo}_{args.compassos}c{suf}.wav"
        io.save_audio(str(destino), res.mashup, res.sr)
        _resumo(modo, res, dt)
        print(
            f"[{modo}] vocal_in={res.plan.vocal_in:.2f}s vocal_dur={res.plan.vocal_dur:.2f}s "
            f"pitch={res.plan.pitch_shift_semitones:+.1f}st"
        )
        print(f"[{modo}] -> {destino}")

    print(f"\n[gera] pronto. Ouca: data/out/{args.slug}_*_{args.compassos}c{suf}.wav")


if __name__ == "__main__":
    main()
