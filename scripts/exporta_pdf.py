#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exporta docs/apresentacao-blend-ai.html para um PDF *idêntico ao HTML*.

Fotografa cada slide com o Chrome/Edge headless (modo ?clean, sem a barra de
navegação) e empacota as imagens num PDF — fica pixel a pixel igual ao deck.
Evita o bug do `--print-to-pdf` do Chrome, que descarta fundos/cores.

Uso:   python scripts/exporta_pdf.py
Requer: Google Chrome (ou Microsoft Edge) instalado + reportlab (pip install reportlab).
Dica:   rode antes `python scripts/gera_slides.py` se tiver editado o conteúdo.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "apresentacao-blend-ai.html"
PDF = ROOT / "docs" / "apresentacao-blend-ai.pdf"

N_SLIDES = 10
SCALE = 2          # 1280x720 -> 2560x1440 por slide (nítido em tela/celular/projetor)
W, H = 1280, 720   # tamanho da página em pontos (mantém o 16:9 do deck)


def achar_navegador() -> str:
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in cands:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "chrome", "chromium", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("Chrome/Edge não encontrado. Instale o Google Chrome.")


def shot(navegador: str, url: str, png: Path, prof: Path) -> bool:
    cmd = [
        navegador, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--force-device-scale-factor={SCALE}", f"--window-size={W},{H}",
        "--virtual-time-budget=4000", f"--user-data-dir={prof}",
        f"--screenshot={png}", url,
    ]
    for _ in range(2):
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if png.exists() and png.stat().st_size > 0:
            return True
        time.sleep(0.4)
    return False


def main() -> None:
    if not HTML.exists():
        sys.exit(f"HTML não encontrado: {HTML}\n  rode antes: python scripts/gera_slides.py")
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError:
        sys.exit("reportlab não instalado.  pip install reportlab")

    navegador = achar_navegador()
    base = HTML.resolve().as_uri()  # file:///...
    tmp = Path(tempfile.mkdtemp(prefix="blend_pdf_"))
    try:
        pngs = []
        for n in range(1, N_SLIDES + 1):
            png = tmp / f"s{n:02d}.png"
            if not shot(navegador, f"{base}?clean#{n}", png, tmp / f"prof{n}"):
                sys.exit(f"falha ao renderizar o slide {n}")
            pngs.append(png)
            print(f"  slide {n}/{N_SLIDES} ok")

        c = canvas.Canvas(str(PDF), pagesize=(W, H))
        for png in pngs:
            c.drawImage(ImageReader(str(png)), 0, 0, width=W, height=H)
            c.showPage()
        c.save()
        kb = PDF.stat().st_size // 1024
        print(f"ok: {N_SLIDES} slides -> {PDF.relative_to(ROOT)}  ({kb} KB)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
