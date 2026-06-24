"""Mashability aprendida (Fase 2) — inferência COCOLA congelada + cabeça calibrada.

Mantido **fora** de `compatibility.py` (que permanece puro/sintético): aqui vivem o
carregamento do encoder COCOLA, a preparação de áudio (16 kHz/mono/5 s), a forma
bilinear assimétrica `h₁ᵀW h₂`, o cache de embeddings e a cabeça de calibração. O
COCOLA é **congelado** (só inferência); só a cabeça treina. As funções puras
(`score_bilinear`, `_preparar_audio`) não dependem de GPU/checkpoint.

O carregamento real do checkpoint (`_carregar_modelo`/`embed_de_audio`) exige o
ambiente Docker+GPU (torch + pacote `cocola` + pesos `COCOLA_HP_v1`); por isso o
encoder é injetável/mockável e tudo ao redor é testável sem ele.
"""
from __future__ import annotations

import math

import numpy as np


def score_bilinear(h1, h2, W) -> float:
    """Similaridade bilinear direcional `h₁ᵀ W h₂` (assimétrica quando `W` não é simétrica).

    `h1`, `h2`: embeddings (1-D). `W`: matriz aprendida (2-D) do COCOLA. A ordem
    importa — é o que captura a assimetria vocal-de-A-sobre-base-de-B ≠ reverso.
    """
    a = np.asarray(h1, dtype=np.float64)
    b = np.asarray(h2, dtype=np.float64)
    M = np.asarray(W, dtype=np.float64)
    return float(a @ M @ b)


def _preparar_audio(samples, sr, alvo_sr: int = 16000, dur_s: float = 5.0) -> np.ndarray:
    """Prepara o áudio para o COCOLA: mono, `alvo_sr` (16 kHz), exatamente `dur_s` (5 s).

    Estéreo → média; resample por `resample_poly`; recorta ou faz zero-pad para
    `dur_s·alvo_sr` amostras (80000 por padrão). Retorna 1-D float32.
    """
    from scipy.signal import resample_poly

    y = np.asarray(samples, dtype=np.float32)
    if y.ndim == 2:
        y = y.mean(axis=0)
    if int(sr) != int(alvo_sr):
        g = math.gcd(int(alvo_sr), int(sr))
        y = resample_poly(y, alvo_sr // g, sr // g).astype(np.float32)
    n_alvo = int(dur_s * alvo_sr)
    if len(y) >= n_alvo:
        y = y[:n_alvo]
    else:
        y = np.pad(y, (0, n_alvo - len(y)))
    return np.ascontiguousarray(y, dtype=np.float32)


# --------------------------------------------------------------------------- #
# Cache de embeddings (1× por faixa, não por par)
# --------------------------------------------------------------------------- #
def _chave(track_id: str, papel: str, modo: str) -> str:
    import hashlib

    h = hashlib.sha1(str(track_id).encode()).hexdigest()[:16]
    return f"{h}_{papel}_{modo}"


def caminho_cache(track_id: str, papel: str, modo: str, cache_dir: str):
    """Caminho `.npy` do embedding, único por (faixa, papel vocal|instr, modo)."""
    from pathlib import Path

    return Path(cache_dir) / f"{_chave(track_id, papel, modo)}.npy"


def embed_cacheado(
    track_id: str,
    papel: str,
    embedder,
    cache_dir: str = "data/embeddings",
    modo: str = "both",
) -> np.ndarray:
    """Embedding de uma faixa, com cache em disco — computa via `embedder()` no miss.

    `embedder` é um thunk sem args (ex.: `lambda: embed_de_audio(samples, sr)`),
    para o cache ser independente da fonte do áudio e o COCOLA rodar 1× por faixa.
    """
    p = caminho_cache(track_id, papel, modo, cache_dir)
    if p.exists():
        return np.load(p)
    emb = np.asarray(embedder(), dtype=np.float32)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, emb)
    return emb


# --------------------------------------------------------------------------- #
# Encoder COCOLA congelado — embed_de_audio (glue testável) + adapter (seam)
# --------------------------------------------------------------------------- #
def embed_de_audio(samples, sr, modo: str = "both") -> list[float]:
    """Embedding COCOLA (512-dim) de um áudio. Prepara (16 kHz/mono/5 s) e delega
    ao encoder congelado retornado por `_carregar_modelo` (`.embed(x)`)."""
    x = _preparar_audio(samples, sr)
    modelo = _carregar_modelo(modo)
    return np.asarray(modelo.embed(x), dtype=np.float32).ravel().tolist()


_MODELO = None


def _carregar_modelo(modo: str = "both"):
    """Carrega o encoder COCOLA congelado (singleton).

    SEAM NÃO-VERIFICÁVEL NESTE AMBIENTE: exige torch + pacote `cocola` + checkpoint
    `COCOLA_HP_v1` (env `COCOLA_CKPT`), só disponível no Docker+GPU. Implementado
    contra a API pesquisada do COCOLA; **validar no ambiente completo**. Os testes
    mockam esta função, então o restante do módulo é exercitado sem o modelo.
    """
    global _MODELO
    if _MODELO is None:
        _MODELO = _CocolaAdapter(modo)
    return _MODELO


class _CocolaAdapter:  # pragma: no cover — exige torch+cocola+checkpoint (Docker)
    """Adapter fino sobre o COCOLA expondo `.embed(x_16k_5s) -> np.ndarray` (512-dim)."""

    def __init__(self, modo: str = "both"):
        import os

        import torch
        from contrastive_model import constants
        from contrastive_model.cocola import CoCola
        from feature_extraction.feature_extraction import CoColaFeatureExtractor

        ckpt = os.environ.get("COCOLA_CKPT", "data/models/COCOLA_HP_v1.ckpt")
        self._torch = torch
        self._model = CoCola.load_from_checkpoint(ckpt).eval()
        self._model.set_embedding_mode(
            {
                "both": constants.EmbeddingMode.BOTH,
                "harmonic": constants.EmbeddingMode.HARMONIC,
                "percussive": constants.EmbeddingMode.PERCUSSIVE,
            }.get(modo, constants.EmbeddingMode.BOTH)
        )
        self._fx = CoColaFeatureExtractor()

    def embed(self, x) -> np.ndarray:
        t = self._torch.tensor(x, dtype=self._torch.float32).reshape(1, 1, -1)
        with self._torch.no_grad():
            emb = self._model(self._fx(t))
        return emb.squeeze().cpu().numpy()


# --------------------------------------------------------------------------- #
# Cabeça de calibração (Fase 2c) — funde H2 + COCOLA direcional; só ela treina
# --------------------------------------------------------------------------- #
def montar_features(embed, sc, reverso: bool = False) -> list[float]:
    """Vetor de features p/ a cabeça: COCOLA direcional + componentes do H2.

    `[sim_ab, sim_ba, harmonico, tempo, energia, centroide]`. `reverso=True` troca
    `sim_ab`↔`sim_ba` (direção B→A). Campos ausentes (None) viram 0.0.
    """
    sim_ab = embed.sim_ab if embed.sim_ab is not None else 0.0
    sim_ba = embed.sim_ba if embed.sim_ba is not None else 0.0
    if reverso:
        sim_ab, sim_ba = sim_ba, sim_ab
    energia = sc.energia if sc.energia is not None else 0.0
    centroide = embed.centroide if embed.centroide is not None else 0.0
    return [sim_ab, sim_ba, sc.harmonico, sc.tempo, energia, centroide]


class Calibrador:
    """Cabeça de calibração minúscula (regressão logística) sobre `montar_features`.

    O COCOLA permanece **congelado**; só esta cabeça treina (segundos). Duck-type
    consumido por `compatibility.mashability(cabeca=...)`: expõe `pontuar(embed, sc)`
    devolvendo `(score A→B, score B→A)`.
    """

    def __init__(self, modelo=None):
        self._m = modelo

    def fit(self, X, y) -> "Calibrador":
        from sklearn.linear_model import LogisticRegression

        self._m = LogisticRegression(max_iter=1000).fit(
            np.asarray(X, dtype=float), np.asarray(y)
        )
        return self

    def _prob(self, f) -> float:
        return float(self._m.predict_proba(np.asarray(f, dtype=float).reshape(1, -1))[0, 1])

    def pontuar(self, embed, sc) -> tuple[float, float]:
        return (
            self._prob(montar_features(embed, sc)),
            self._prob(montar_features(embed, sc, reverso=True)),
        )

    def salvar(self, path) -> None:
        import pickle

        with open(path, "wb") as fh:
            pickle.dump(self._m, fh)

    @classmethod
    def carregar(cls, path) -> "Calibrador":
        import pickle

        with open(path, "rb") as fh:
            return cls(pickle.load(fh))
