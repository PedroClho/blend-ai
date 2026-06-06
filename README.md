# Blend AI

Gerador automático de **mashups** guiado por compatibilidade e estrutura musical: pega o vocal de uma faixa e o encaixa sobre o instrumental de outra, casando tempo, tom e estrutura. Caso-guia: vocal de funk sobre tech house.

Trabalho final de **PAV (Processamento de Áudio e Voz) — UFG**. Equipe de 4. Ver `CLAUDE.md` para escopo, hipóteses, stack e fluxo; proposta detalhada em `designs/proposta-automashup.html`.

## Estrutura

```
src/blend/      motor: separação, análise, tom, score, alinhamento, síntese, pipeline
app/            interface Streamlit (MVP)
eval/           avaliação científica: métricas + experimento + stats
data/           áudio e ground truth (não versionado)
specs/          specs de feature (spec-driven)
tests/          pytest (test gate)
designs/        mockups + proposta (norte visual)
.claude/agents/ agentes por módulo (P1–P4)
```

## Rodar (Docker)

```bash
docker compose build
docker compose up            # Streamlit em http://localhost:8501
# shell interativo:
docker compose run --rm blend bash
```

Requer GPU NVIDIA (Docker Desktop + WSL2 + nvidia-container-toolkit). Coloque o áudio em `data/raw/bases/` (house) e `data/raw/funks/` (funk), e o `rekordbox.xml` em `data/rekordbox/`. As pastas `data/benchmarks/` e `output/` são criadas em runtime.

## Equipe

- **P1 — Separação & Análise** (agente `blend-audio`)
- **P2 — Motor de Mashup** (agente `blend-mashup`)
- **P3 — Produto & Interface** (agente `blend-app`)
- **P4 — Avaliação & Dados** (agente `blend-eval`)
