"""Cache de análises por hash de conteúdo do arquivo (camada da API).

A análise (allin1 + Essentia) é cara (~GPU) e é função pura do ARQUIVO — cacheável
por sha256 do conteúdo. O cache atende dois fluxos:

* ``POST /api/analyses`` — análise prévia de uma faixa (base do "ver + ancorar");
* job de mashup — mesma faixa já analisada pula ``analyze()``/``estimate_key()``.

Só análises COMPLETAS (com seções do allin1) são salvas: o fallback madmom
(``segments=[]``, allin1 indisponível/OOM) nunca congela no cache — na próxima
tentativa a análise roda de novo e pode recuperar as seções.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from blend.types import Segment, TrackAnalysis

VERSAO = 1  # subir invalida o cache (mudou o formato ou a própria análise)


def hash_arquivo(path: str | Path) -> str:
    """sha256 (24 hex) do conteúdo — chave do cache, estável entre uploads."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:24]


def analise_para_dict(an: TrackAnalysis) -> dict:
    return {
        "sr": an.sr,
        "bpm": an.bpm,
        "key_camelot": an.key_camelot,
        "beats": an.beats,
        "downbeats": an.downbeats,
        "segments": [{"start": s.start, "end": s.end, "label": s.label} for s in an.segments],
    }


def analise_de_dict(d: dict) -> TrackAnalysis:
    return TrackAnalysis(
        path="",  # o path original (upload temporário) não sobrevive ao cache
        sr=int(d["sr"]),
        bpm=float(d["bpm"]),
        beats=[float(b) for b in d["beats"]],
        downbeats=[float(x) for x in d["downbeats"]],
        segments=[
            Segment(float(s["start"]), float(s["end"]), str(s["label"]))
            for s in d["segments"]
        ],
        key_camelot=d.get("key_camelot"),
    )


class CacheAnalises:
    """Um JSON por faixa em `raiz/<hash>.json`. Leituras corrompidas = cache miss."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = Path(raiz)

    def _arquivo(self, chave: str) -> Path:
        return self.raiz / f"{chave}.json"

    def carregar(self, chave: str) -> TrackAnalysis | None:
        p = self._arquivo(chave)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("versao") != VERSAO:
                return None
            return analise_de_dict(d["analise"])
        except Exception:
            return None

    def salvar(self, chave: str, an: TrackAnalysis) -> bool:
        """Salva se a análise está completa (tem seções). Retorna se salvou."""
        if not an.segments:
            return False
        self.raiz.mkdir(parents=True, exist_ok=True)
        payload = {"versao": VERSAO, "analise": analise_para_dict(an)}
        self._arquivo(chave).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return True
