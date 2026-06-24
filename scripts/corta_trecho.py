"""Corta um trecho [ini, fim] (em segundos) de um .wav. Sem GPU/Demucs.

Util pra gerar um excerto curto de um mashup (ex.: ~45s em torno da entrada do
vocal) para enviar/avaliar sem rolar o arquivo inteiro.

Uso: python scripts/corta_trecho.py <entrada.wav> <ini_s> <fim_s> [saida.wav]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from blend import io  # noqa: E402


def main() -> None:
    src = sys.argv[1]
    ini, fim = float(sys.argv[2]), float(sys.argv[3])
    dst = sys.argv[4] if len(sys.argv) > 4 else src.replace(".wav", "_trecho.wav")

    samples, sr = io.load_audio(src, sr=44100, mono=False)  # (canais, amostras)
    a, b = int(ini * sr), int(fim * sr)
    clip = samples[..., a:b]
    io.save_audio(dst, clip, sr)
    print(f"[corta] {ini:.1f}s–{fim:.1f}s ({(b - a) / sr:.1f}s) -> {dst}  shape={clip.shape}")


if __name__ == "__main__":
    main()
