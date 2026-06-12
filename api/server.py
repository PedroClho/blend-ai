"""Blend AI — API HTTP (FastAPI) sobre o pipeline de mashup.

Modelo de execução: a geração leva ~1-2 min (GPU), então POST /api/mashups só
enfileira e devolve um job; a UI faz polling em GET /api/jobs/{id}. Um worker
por vez (lock) — a RTX 2060 (6 GB) não comporta dois Demucs simultâneos.

Rodar (no container torch20):
    uvicorn api.server:app --host 0.0.0.0 --port 8000
A SPA buildada (web/dist) é servida na raiz, quando existir.
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "out" / "api"
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Blend AI API", version="0.1.0")
app.add_middleware(  # dev: Vite roda em :5173; produção: mesma origem
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# --------------------------------------------------------------------------- #
# Jobs em memória (MVP: 1 processo, 1 worker)
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    id: str
    status: str = "na_fila"  # na_fila | processando | concluido | erro
    etapa: str = ""  # carregando | separando | analisando | ...
    modo: str = "proposto"
    nome_a: str = ""
    nome_b: str = ""
    erro: str | None = None
    resultado: dict | None = None
    _paths: dict = field(default_factory=dict, repr=False)


JOBS: dict[str, Job] = {}
_WORKER_LOCK = threading.Lock()  # serializa o uso da GPU

ETAPAS = [
    "carregando",
    "separando",
    "analisando",
    "estimando_tom",
    "alinhando",
    "sintetizando",
]


def _serializar_analise(an) -> dict | None:
    if an is None:
        return None
    return {
        "bpm": round(float(an.bpm), 2),
        "key_camelot": an.key_camelot,
        "n_beats": len(an.beats),
        "n_downbeats": len(an.downbeats),
        "duracao": round(float(an.downbeats[-1]), 2) if an.downbeats else None,
        "segments": [
            {"start": round(s.start, 2), "end": round(s.end, 2), "label": s.label}
            for s in an.segments
        ],
    }


def _rodar_job(job: Job) -> None:
    from blend import io as bio
    from blend.pipeline import make_mashup

    def on_stage(nome: str) -> None:
        job.etapa = nome

    with _WORKER_LOCK:
        job.status = "processando"
        try:
            res = make_mashup(
                job._paths["a"], job._paths["b"], mode=job.modo, on_stage=on_stage
            )
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            wav_path = OUT_DIR / f"{job.id}.wav"
            bio.save_audio(str(wav_path), res.mashup, res.sr)

            seg = res.plan.target_segment
            job.resultado = {
                "audio_url": f"/api/jobs/{job.id}/audio.wav",
                "duracao": round(res.mashup.shape[-1] / res.sr, 2),
                "score": {
                    "total": round(res.score.total, 3),
                    "harmonico": round(res.score.harmonico, 3),
                    "tempo": round(res.score.tempo, 3),
                    "energia": res.score.energia,
                    "camelot_dist": res.score.camelot_dist,
                },
                "plan": {
                    "mode": res.plan.mode,
                    "nivel_fallback": res.plan.nivel_fallback,
                    "secao": {
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "label": seg.label,
                    },
                    "vocal_offset": round(res.plan.vocal_offset, 2),
                    "bpm_ratio": round(res.plan.bpm_ratio, 4),
                    "pitch_shift_semitones": round(res.plan.pitch_shift_semitones, 1),
                    "vocal_in": round(res.plan.vocal_in, 2),
                    "vocal_dur": (
                        round(res.plan.vocal_dur, 2)
                        if res.plan.vocal_dur is not None
                        else None
                    ),
                },
                "analise_vocal": _serializar_analise(res.analise_vocal),
                "analise_base": _serializar_analise(res.analise_base),
            }
            job.status = "concluido"
            job.etapa = "pronto"
        except Exception as e:  # noqa: BLE001 — erro vai pra UI
            job.status = "erro"
            job.erro = f"{type(e).__name__}: {e}"
        finally:
            for p in job._paths.values():
                Path(p).unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Rotas
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "jobs": len(JOBS)}


@app.post("/api/mashups", status_code=202)
async def criar_mashup(
    faixa_a: UploadFile, faixa_b: UploadFile, modo: str = "proposto"
) -> dict:
    if modo not in ("proposto", "baseline"):
        raise HTTPException(422, "modo deve ser 'proposto' ou 'baseline'")

    job = Job(id=uuid.uuid4().hex[:12], modo=modo)
    job.nome_a = faixa_a.filename or "faixa_a"
    job.nome_b = faixa_b.filename or "faixa_b"
    for chave, up in (("a", faixa_a), ("b", faixa_b)):
        suffix = Path(up.filename or "").suffix or ".mp3"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        shutil.copyfileobj(up.file, tmp)
        tmp.close()
        job._paths[chave] = tmp.name

    JOBS[job.id] = job
    threading.Thread(target=_rodar_job, args=(job,), daemon=True).start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def estado_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job não encontrado")
    d = asdict(job)
    d.pop("_paths", None)
    d["etapas"] = ETAPAS
    return d


@app.get("/api/jobs/{job_id}/audio.wav")
def audio_job(job_id: str) -> FileResponse:
    wav = OUT_DIR / f"{job_id}.wav"
    if job_id not in JOBS or not wav.exists():
        raise HTTPException(404, "áudio não encontrado")
    return FileResponse(wav, media_type="audio/wav", filename=f"blend_{job_id}.wav")


# SPA buildada (produção). Em dev, use o Vite (npm run dev) com proxy p/ cá.
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="spa")
