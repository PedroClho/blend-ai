# Blend AI — imagem de desenvolvimento (GPU NVIDIA)
#
# ATENÇÃO (validar na Semana 1): as versões de torch / NATTEN / allin1 são o ponto
# frágil do build. NATTEN distribui wheels por combinação (torch, CUDA) específica —
# se trocar a imagem base, ajuste a linha do natten para a combinação correspondente.
#   NATTEN wheels: https://shi-labs.com/natten/
#   allin1:        https://github.com/mir-aidj/all-in-one
#   essentia:      pip install essentia (wheel manylinux)

FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Libs de sistema: ffmpeg (decodificar mp3), rubberband-cli (pyrubberband), build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    rubberband-cli \
    git \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NATTEN casado com torch 2.2.0 + cu121 (ajuste a tag se mudar a base):
RUN pip install --no-cache-dir natten==0.17.1+torch220cu121 \
    -f https://shi-labs.com/natten/wheels/ || \
    echo ">> AJUSTAR versao do NATTEN para a combinacao torch/cuda desta base"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0"]
