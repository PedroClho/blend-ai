"""Separação de fontes com Demucs v4 (htdemucs)."""
from __future__ import annotations

import numpy as np

_MODEL = None
# htdemucs (modelo único) em vez de htdemucs_ft (bag de 4 modelos): ~4x menos
# RAM/VRAM. Essencial na RTX 2060 (6 GB) + WSL (~8 GB): o _ft estourava a memória
# e derrubava o daemon do Docker. Voltar p/ "htdemucs_ft" só com mais recursos.
_MODEL_NAME = "htdemucs"


def _get_model():
    global _MODEL
    if _MODEL is None:
        from demucs.pretrained import get_model

        _MODEL = get_model(_MODEL_NAME)
        _MODEL.eval()
    return _MODEL


def separate(samples: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Separa em stems: 'vocals', 'drums', 'bass', 'other'.

    Entrada/saída em (canais, amostras) float32, na sr do modelo (44100).
    Usa GPU se disponível; cai para CPU em caso de falta de memória (RTX 2060 = 6 GB).
    """
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
