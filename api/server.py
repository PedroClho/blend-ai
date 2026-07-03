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

from .analysis_cache import CacheAnalises, hash_arquivo

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "out" / "api"
WEB_DIST = ROOT / "web" / "dist"
CACHE_ANALISES = CacheAnalises(ROOT / "data" / "cache" / "analises")

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
    transpor: bool = True
    ancoras: dict | None = None  # {vocal_in, vocal_dur, vocal_offset} — modo manual
    bpm_alvo: float | None = None  # BPM final: base + vocal esticados p/ o alvo
    erro: str | None = None
    resultado: dict | None = None
    _paths: dict = field(default_factory=dict, repr=False)


@dataclass
class AnaliseJob:
    """Análise prévia de UMA faixa (grade p/ o modo manual da UI)."""

    id: str
    status: str = "na_fila"  # na_fila | processando | concluido | erro
    etapa: str = ""
    nome: str = ""
    erro: str | None = None
    resultado: dict | None = None
    _path: str = field(default="", repr=False)


JOBS: dict[str, Job] = {}
ANALISES: dict[str, AnaliseJob] = {}
_WORKER_LOCK = threading.Lock()  # serializa o uso da GPU

ETAPAS = [
    "carregando",
    "separando",
    "analisando",
    "estimando_tom",
    "alinhando",
    "sintetizando",
]
ETAPAS_ANALISE = ["carregando", "analisando", "estimando_tom"]


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

    # cache por hash: faixa já analisada (análise prévia ou mashup anterior) pula
    # allin1/Essentia dentro do make_mashup — leitura leve, fora do lock da GPU
    hashes = {k: hash_arquivo(p) for k, p in job._paths.items()}
    an_a = CACHE_ANALISES.carregar(hashes["a"])
    an_b = CACHE_ANALISES.carregar(hashes["b"])

    anc = job.ancoras or {}
    with _WORKER_LOCK:
        job.status = "processando"
        try:
            res = make_mashup(
                job._paths["a"],
                job._paths["b"],
                mode=job.modo,
                on_stage=on_stage,
                transpor=job.transpor,
                vocal_in=anc.get("vocal_in"),
                vocal_dur=anc.get("vocal_dur"),
                vocal_offset=anc.get("vocal_offset"),
                bpm_alvo=job.bpm_alvo,
                analise_vocal=an_a,
                analise_base=an_b,
            )
            if res.analise_vocal is not None:
                CACHE_ANALISES.salvar(hashes["a"], res.analise_vocal)
            if res.analise_base is not None:
                CACHE_ANALISES.salvar(hashes["b"], res.analise_base)
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
                    "base_ratio": round(res.plan.base_ratio, 4),
                    "bpm_alvo": res.plan.bpm_alvo,
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


def _rodar_analise(job: AnaliseJob) -> None:
    """Análise prévia de uma faixa: mesmos passos do make_mashup, com cache.

    Cache hit resolve SEM o lock da GPU (só hash + JSON) — uma faixa já analisada
    devolve a grade na hora mesmo com um mashup ocupando a GPU.
    """
    from blend import io as bio
    from blend import key as bkey
    from blend.analysis import analyze

    try:
        chave = hash_arquivo(job._path)
        an = CACHE_ANALISES.carregar(chave)
        em_cache = an is not None
        if an is None:
            with _WORKER_LOCK:
                job.status = "processando"
                job.etapa = "carregando"
                samples, sr = bio.load_audio(job._path, sr=44100, mono=False)
                job.etapa = "analisando"
                an = analyze(job._path, samples, sr)
                job.etapa = "estimando_tom"
                if an.key_camelot is None:
                    try:
                        an.key_camelot = bkey.estimate_key(samples, sr)
                    except Exception:
                        pass
                CACHE_ANALISES.salvar(chave, an)
        job.resultado = {**(_serializar_analise(an) or {}), "cache": em_cache}
        job.resultado["downbeats"] = [round(d, 3) for d in an.downbeats]
        job.status = "concluido"
        job.etapa = "pronto"
    except Exception as e:  # noqa: BLE001 — erro vai pra UI
        job.status = "erro"
        job.erro = f"{type(e).__name__}: {e}"
    finally:
        Path(job._path).unlink(missing_ok=True)


def _validar_ancoras(
    vocal_in: float | None, vocal_dur: float | None, vocal_offset: float | None
) -> None:
    """Âncoras em segundos: tempos não-negativos, duração positiva e limitada.

    Comparações com NaN são falsas → NaN cai no `raise` naturalmente.
    """
    for nome, v in (("vocal_in", vocal_in), ("vocal_offset", vocal_offset)):
        if v is not None and not (0.0 <= v <= 36000.0):
            raise HTTPException(422, f"{nome} deve estar em [0, 36000] segundos")
    if vocal_dur is not None and not (0.05 <= vocal_dur <= 600.0):
        raise HTTPException(422, "vocal_dur deve estar em [0.05, 600] segundos")


def _validar_bpm_alvo(bpm_alvo: float | None) -> None:
    """BPM final em faixa de DJ (40–220); NaN cai no raise (comparação falsa)."""
    if bpm_alvo is not None and not (40.0 <= bpm_alvo <= 220.0):
        raise HTTPException(422, "bpm_alvo deve estar em [40, 220]")


def _salvar_upload(up: UploadFile) -> str:
    suffix = Path(up.filename or "").suffix or ".mp3"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    shutil.copyfileobj(up.file, tmp)
    tmp.close()
    return tmp.name


# --------------------------------------------------------------------------- #
# Rotas
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "jobs": len(JOBS)}


@app.post("/api/mashups", status_code=202)
async def criar_mashup(
    faixa_a: UploadFile,
    faixa_b: UploadFile,
    modo: str = "proposto",
    transpor: bool = True,
    vocal_in: float | None = None,
    vocal_dur: float | None = None,
    vocal_offset: float | None = None,
    bpm_alvo: float | None = None,
) -> dict:
    """Enfileira um mashup. Âncoras manuais (opcionais) em segundos: `vocal_in` e
    `vocal_dur` no tempo de A; `vocal_offset` no tempo de B. `transpor=false`
    pula a transposição harmônica (H3 — vocal declamado). `bpm_alvo` estica as
    DUAS faixas para o BPM final escolhido antes do merge (tom preservado)."""
    if modo not in ("proposto", "baseline"):
        raise HTTPException(422, "modo deve ser 'proposto' ou 'baseline'")
    _validar_ancoras(vocal_in, vocal_dur, vocal_offset)
    _validar_bpm_alvo(bpm_alvo)

    ancoras = {
        k: v
        for k, v in (
            ("vocal_in", vocal_in),
            ("vocal_dur", vocal_dur),
            ("vocal_offset", vocal_offset),
        )
        if v is not None
    }
    job = Job(
        id=uuid.uuid4().hex[:12],
        modo=modo,
        transpor=transpor,
        ancoras=ancoras or None,
        bpm_alvo=bpm_alvo,
    )
    job.nome_a = faixa_a.filename or "faixa_a"
    job.nome_b = faixa_b.filename or "faixa_b"
    for chave, up in (("a", faixa_a), ("b", faixa_b)):
        job._paths[chave] = _salvar_upload(up)

    JOBS[job.id] = job
    threading.Thread(target=_rodar_job, args=(job,), daemon=True).start()
    return {"job_id": job.id}


@app.post("/api/analyses", status_code=202)
async def criar_analise(faixa: UploadFile) -> dict:
    """Enfileira a análise prévia de UMA faixa (bpm, tom, downbeats, seções) —
    a grade que o modo manual da UI usa para ancorar. Cache por hash do arquivo."""
    job = AnaliseJob(id=uuid.uuid4().hex[:12], nome=faixa.filename or "faixa")
    job._path = _salvar_upload(faixa)
    ANALISES[job.id] = job
    threading.Thread(target=_rodar_analise, args=(job,), daemon=True).start()
    return {"analysis_id": job.id}


@app.get("/api/analyses/{analysis_id}")
def estado_analise(analysis_id: str) -> dict:
    job = ANALISES.get(analysis_id)
    if job is None:
        raise HTTPException(404, "análise não encontrada")
    d = asdict(job)
    d.pop("_path", None)
    d["etapas"] = ETAPAS_ANALISE
    return d


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
