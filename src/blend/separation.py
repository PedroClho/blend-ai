"""Separação de fontes — backend selecionável por `BLEND_SEP_BACKEND`.

`htdemucs` (Demucs v4, default, caminho garantido na RTX 2060) ou `roformer`
(Mel-Band RoFormer via `python-audio-separator`, opt-in; ver specs/separacao-roformer.md).
A interface pública `separate(samples, sr) -> dict{vocals,drums,bass,other}` é estável:
`pipeline.py`/`synthesis.py`/`alignment.py` não mudam ao trocar de backend.
"""
from __future__ import annotations

import os

import numpy as np

_MODEL = None
# htdemucs (modelo único) em vez de htdemucs_ft (bag de 4 modelos): ~4x menos
# RAM/VRAM. Essencial na RTX 2060 (6 GB) + WSL (~8 GB): o _ft estourava a memória
# e derrubava o daemon do Docker. Voltar p/ "htdemucs_ft" só com mais recursos.
_MODEL_NAME = "htdemucs"


def _backend() -> str:
    """Backend ativo (env `BLEND_SEP_BACKEND`, default `htdemucs`)."""
    return os.environ.get("BLEND_SEP_BACKEND", "htdemucs").strip().lower()


def separate(samples: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Separa em stems: 'vocals', 'drums', 'bass', 'other'.

    Entrada/saída em (canais, amostras) float32. Despacha pelo backend ativo;
    backend desconhecido levanta `ValueError` (antes de qualquer import pesado).
    """
    b = _backend()
    if b == "htdemucs":
        return _separate_htdemucs(samples, sr)
    if b == "roformer":
        return _separate_roformer(samples, sr)
    raise ValueError(
        f"BLEND_SEP_BACKEND inválido: {b!r} (use 'htdemucs' ou 'roformer')"
    )


# --------------------------------------------------------------------------- #
# Backend htdemucs (Demucs v4) — comportamento original, preservado
# --------------------------------------------------------------------------- #
def _get_model():
    global _MODEL
    if _MODEL is None:
        from demucs.pretrained import get_model

        _MODEL = get_model(_MODEL_NAME)
        _MODEL.eval()
    return _MODEL


def _separate_htdemucs(samples: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Demucs v4 (htdemucs). GPU com fallback p/ CPU em OOM (RTX 2060 = 6 GB)."""
    import torch
    from demucs.apply import apply_model
    from demucs.audio import convert_audio

    model = _get_model()
    wav = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32))
    if wav.ndim == 1:
        wav = wav.unsqueeze(0)
    wav = convert_audio(wav, sr, model.samplerate, model.audio_channels)

    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    wav = (wav - mean) / std

    def _apply(device: str):
        model.to(device)
        with torch.no_grad():
            return apply_model(
                model, wav[None].to(device), split=True, overlap=0.25, progress=False
            )[0]

    try:
        sources = _apply("cuda" if torch.cuda.is_available() else "cpu")
    except RuntimeError as e:  # provável CUDA OOM
        if "out of memory" not in str(e).lower():
            raise
        torch.cuda.empty_cache()
        sources = _apply("cpu")

    sources = (sources * std + mean).cpu().numpy().astype(np.float32)
    return {name: sources[i] for i, name in enumerate(model.sources)}


# --------------------------------------------------------------------------- #
# Ponte in-memory ↔ API file-based do audio-separator
# --------------------------------------------------------------------------- #
def _write_tmp_wav(arr: np.ndarray, sr: int, path) -> str:
    """Escreve (canais, amostras) float32 num .wav (PCM float, sem perda)."""
    import soundfile as sf

    y = np.asarray(arr, dtype=np.float32)
    if y.ndim == 1:
        y = y[np.newaxis, :]
    sf.write(str(path), y.T, sr, subtype="FLOAT")  # soundfile espera (amostras, canais)
    return str(path)


def _read_stem_wav(path) -> np.ndarray:
    """Lê um .wav e devolve (canais, amostras) float32."""
    import soundfile as sf

    y, _sr = sf.read(str(path), dtype="float32", always_2d=True)  # (amostras, canais)
    return np.ascontiguousarray(y.T, dtype=np.float32)


# --------------------------------------------------------------------------- #
# Backend RoFormer (2-stem) → mapeado p/ o contrato de 4 chaves
# --------------------------------------------------------------------------- #
def _mapear_2stem(vocals: np.ndarray, instrumental: np.ndarray) -> dict[str, np.ndarray]:
    """Mapeia a saída 2-stem do RoFormer (vocal/instrumental) p/ {vocals,drums,bass,other}.

    `synthesis.render` consome só `vocals` vs "tudo menos vocals" (soma drums+bass+other);
    pôr o instrumental em `other` e zerar `drums`/`bass` reconstrói o instrumental na soma,
    sem regressão na síntese. (4-stem real fica atrás de `BLEND_SEP_ROFORMER_STEMS=4`.)
    """
    vocals = np.asarray(vocals, dtype=np.float32)
    instrumental = np.asarray(instrumental, dtype=np.float32)
    return {
        "vocals": vocals,
        "drums": np.zeros_like(instrumental),
        "bass": np.zeros_like(instrumental),
        "other": instrumental,
    }


def _separate_roformer(samples: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Separa com Mel-Band RoFormer (2-stem) e mapeia p/ o contrato de 4 chaves."""
    vocals, instrumental = _rodar_roformer(samples, sr)
    return _mapear_2stem(vocals, instrumental)


def _rodar_roformer(samples, sr):  # pragma: no cover — exige audio-separator + pesos (Docker)
    """SEAM NÃO-VERIFICÁVEL NESTE AMBIENTE: roda o RoFormer via `python-audio-separator`.

    API file-based (escreve .wav, separa, lê stems). Memória controlada por
    `segment_size`/`batch_size`; fallback de `segment_size` → CPU em OOM, espelhando
    o htdemucs. Implementado contra a API pesquisada; **validar no Docker+GPU**. Os
    testes mockam `_rodar_roformer`/`_separate_roformer`, então o resto é exercitado.
    """
    import tempfile

    from audio_separator.separator import Separator

    model_dir = os.environ.get("BLEND_SEP_MODEL_DIR", None)
    model_name = os.environ.get("BLEND_SEP_ROFORMER_MODEL", "vocals_mel_band_roformer.ckpt")
    segments = [int(s) for s in os.environ.get("BLEND_SEP_SEGMENT_STEPS", "256,128,64").split(",")]

    with tempfile.TemporaryDirectory() as td:
        entrada = _write_tmp_wav(samples, sr, os.path.join(td, "in.wav"))
        ultimo_erro = None
        for seg in segments:  # reduz segment_size antes de cair p/ CPU
            try:
                sep = Separator(
                    output_dir=td,
                    model_file_dir=model_dir,
                    mdxc_params={"segment_size": seg, "batch_size": 1, "overlap": 8,
                                 "override_model_segment_size": True},
                )
                sep.load_model(model_filename=model_name)
                saidas = sep.separate(entrada)
                stems = [_read_stem_wav(os.path.join(td, p)) for p in saidas]
                vocals = stems[0]
                instrumental = stems[1] if len(stems) > 1 else np.zeros_like(vocals)
                return vocals, instrumental
            except RuntimeError as e:
                if "out of memory" not in str(e).lower():
                    raise
                ultimo_erro = e
        raise ultimo_erro if ultimo_erro else RuntimeError("RoFormer falhou")
