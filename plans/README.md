# Planos de implementação — Blend AI (branch `produto`)

Roadmap de **evolução de produto** do Blend AI, fora do escopo da entrega acadêmica (vive só na branch `produto`). Análise vs. SOTA 2026 e o veredito da pergunta *"melhorar só com dados ou treinando um modelo?"*:

> Maior ROI = **dados melhores + modelos prontos melhores + engenharia de DSP**. Não se treina encoder do zero (inviável: dados/VRAM). O **único modelo que vale "treinar"** é uma **cabeça de calibração minúscula** sobre o **COCOLA congelado** (mashability assimétrica) — e mesmo assim só depois do gate zero-shot.

Specs em `specs/` (problema/escopo/interface/critério); planos TDD executáveis aqui.

| Fase | Plano | Módulo | Tipo |
|---|---|---|---|
| 1a | [`sincronizacao-frases.md`](sincronizacao-frases.md) | P2 `blend-mashup` | DSP, **sem modelo** (maior ganho de musicalidade) |
| 1b | [`separacao-roformer.md`](separacao-roformer.md) | P1 `blend-audio` | troca de modelo pronto (Mel-Band RoFormer) |
| 2 | [`mashability-cocola.md`](mashability-cocola.md) | P2 + P4 | COCOLA congelado + cabeça calibrada (o modelo que vale) |

## Fase 0 — Fundação (scaffolding, NÃO muda comportamento)

Mudanças **aditivas e retrocompatíveis** que desbloqueiam as três features. Todas com default = comportamento atual; nenhum teste existente pode quebrar. É o pré-requisito comum.

- **`src/blend/types.py`:**
  - `AlignmentPlan.phrase_anchors: list[tuple[float, float]] | None = None`
  - `ScoreCompat`: `learned_score`, `learned_score_rev`, `embed_sim` (todos `float | None = None`)
  - novo dataclass `EmbedFeatures`
- **`src/blend/separation.py`:** dispatch por `BLEND_SEP_BACKEND` (default `htdemucs`); corpo atual extraído para `_separate_htdemucs` (byte-equivalente).
- **`src/blend/pipeline.py`:** feature flags (`usar_cocola=False`, etc.) — caminho default idêntico ao atual.
- **Testes de regressão (guardiões):** campos novos default `None`; `render(... phrase_anchors=None)` byte-idêntico (`np.array_equal`); `mashability(embed=None)` ≡ `compatibility_score`.

## Ordem de execução e dependências

1. **Fase 0** — pré-requisito de tudo.
2. **Em paralelo** (módulos/pessoas independentes): **Fase 1a** (frases, P2) ‖ **Fase 1b** (RoFormer, P1).
3. **Fase 2** (mashability, P2+P4): **2a zero-shot** (entrega valor sem rótulos; é um **GATE** de risco) → **2b rótulos** → **2c cabeça**. 2a só depende da Fase 0.
4. **Fase 3** (fronteira, opcional): Stem-JEPA como plano B se 2a falhar em funk×house; refino de tom; generativo (transição/re-voicing) só como spike.

## Isolamento em git worktree

Uma worktree por feature, a partir de `produto` (metodologia superpowers `using-git-worktrees`):

```sh
git worktree add -b feat/frases   ../blend-frases   produto
git worktree add -b feat/roformer ../blend-roformer produto
git worktree add -b feat/cocola   ../blend-cocola   produto
```

Cada feature: TDD (RED → GREEN → REFACTOR) → `pytest` verde no container → verificação real (ouvir / SDR / Spearman) → merge de volta em `produto`. Remover a worktree ao concluir (`git worktree remove`).

## Mapa feature → agente do projeto (`.claude/agents/`)

- **Fase 1a** (frases) → `blend-mashup` (P2)
- **Fase 1b** (RoFormer) → `blend-audio` (P1)
- **Fase 2** (mashability) → `blend-mashup` (P2, motor) + `blend-eval` (P4, rótulos/estatística)
- **Exposição do ranking na UI** (quando houver) → `blend-app` (P3)

## Restrições de ambiente

Tudo roda no **Docker + CUDA** do projeto (RTX 2060, 6 GB VRAM / 16 GB RAM), não no host. `pytest` e a verificação por áudio rodam dentro do container (`blend-ai:torch20` ou `:torch26`). Os planos são test-first justamente porque a maior parte da lógica (detector de frases, fusão de score, dispatch de backend, cabeça calibrada) é testável com sinais sintéticos/mocks, **sem** GPU nem modelos pesados — só o gate final exige o ambiente completo.
