# Blend AI — imagem com allin1 (stack legada exigida pelo allin1)
#
# POR QUE torch 2.0: o allin1 (modelo DiNAT, allin1/models/dinat.py) importa a
# API antiga do NATTEN (`natten1dav` / `natten2dav`), que só existe em NATTEN
# < 0.15. E NATTEN 0.14.x suporta torch ~2.0. É uma geração atrás da stack ideal
# (torch 2.6), mas é o preço de usar o allin1 — a estrutura rotulada
# (intro/verso/refrão/drop) que a H1 precisa.
#
# NATTEN compilado do SOURCE (imagem `devel` tem nvcc) para casar EXATO com o
# torch instalado e evitar o ABI mismatch de wheel (que custou caro no torch 2.6).
# TORCH_CUDA_ARCH_LIST=7.5 = NVIDIA RTX 2060 (a GPU validada na máquina).
#
# >>> AINDA NÃO BUILDADO/VALIDADO (2026-06-07). Rodar `docker compose build`
#     quando houver tempo (baixa imagem ~9 GB + compila o natten, ~10-20 min).
#     Pontos a validar no 1º build: (a) compilação do natten 0.14.6 em cuda 11.7;
#     (b) compat de numpy<1.24 com madmom/allin1; (c) import de allin1 + GPU.
#     Fallback validado (torch 2.6, GPU OK, sem allin1): Dockerfile.torch26-fallback.

FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    TORCH_CUDA_ARCH_LIST=7.5

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg rubberband-cli git build-essential ninja-build \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# numpy<1.24 (madmom + mir_eval) + cython, antes de compilar natten/madmom
RUN pip install "numpy<1.24" cython

# NATTEN 0.14.x — única faixa com a API `natten2dav` que o allin1 importa.
# --no-binary força COMPILAR do source (casa com torch 2.0.1+cu117 da imagem),
# evitando o ABI mismatch de wheel. Se falhar, tentar o wheel pré-compilado:
#   pip install natten==0.14.6 -f https://shi-labs.com/natten/wheels/
# MAX_JOBS=2: nvcc paralelo demais estoura a RAM do WSL (~8 GB) e mata o build.
RUN MAX_JOBS=2 pip install natten==0.14.6 --no-binary natten

# madmom do git (beat/downbeat; usado pelo allin1)
RUN pip install "git+https://github.com/CPJKU/madmom"

# Demais dependências (allin1 puxa demucs/librosa/hydra; essentia, rubberband...)
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0"]
