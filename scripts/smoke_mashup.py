"""Smoke ponta-a-ponta: gera um mashup real e salva. Validação interna do pipeline.

Vocal de A (separado) sobre o instrumental de B. Default: duas tech house de
BPM próximo (131 ↔ 132) — o caso controlado do experimento MVP.

Uso (dentro do container): python scripts/smoke_mashup.py [modo]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from blend import io  # noqa: E402
from blend.pipeline import make_mashup  # noqa: E402

BASES = ROOT / "data" / "raw" / "bases"
VOCAL = BASES / "Michael Bibi - Bad Wolf (Extended Mix) [EMPIRE]_pn.mp3"
BASE = BASES / "Joshwa - Work Your Body (Extended Mix) [Catch Release]_pn.mp3"
OUT = ROOT / "data" / "out"


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "proposto"
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"[smoke] vocal={VOCAL.name}")
    print(f"[smoke] base ={BASE.name}")
    print(f"[smoke] modo ={modo}")

    t0 = time.time()
    res = make_mashup(str(VOCAL), str(BASE), mode=modo)
    dt = time.time() - t0

    destino = OUT / f"smoke_mashup_{modo}.wav"
    io.save_audio(str(destino), res.mashup, res.sr)

    print(f"[smoke] OK em {dt:.1f}s -> {destino}")
    print(
        f"[smoke] score total={res.score.total:.3f} "
        f"harm={res.score.harmonico:.3f} tempo={res.score.tempo:.3f} "
        f"camelot_dist={res.score.camelot_dist}"
    )
    print(
        f"[smoke] plan: ratio={res.plan.bpm_ratio:.4f} "
        f"offset={res.plan.vocal_offset:.2f}s nivel_fallback={res.plan.nivel_fallback} "
        f"secao='{res.plan.target_segment.label}' "
        f"[{res.plan.target_segment.start:.1f}–{res.plan.target_segment.end:.1f}s]"
    )
    print(
        f"[smoke] recorte: vocal_in={res.plan.vocal_in:.2f}s "
        f"dur={res.plan.vocal_dur if res.plan.vocal_dur is None else round(res.plan.vocal_dur, 2)}s "
        f"pitch={res.plan.pitch_shift_semitones:+.1f}st"
    )
    print(f"[smoke] mashup shape={res.mashup.shape} sr={res.sr}")


if __name__ == "__main__":
    main()
