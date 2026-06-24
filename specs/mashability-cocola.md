# Spec — Mashability aprendida e assimétrica (COCOLA congelado + cabeça de calibração) (Fase 2)

> Módulos: P2 (`blend-mashup`) + P4 (`blend-eval`, rótulos) · Arquivos: `src/blend/compatibility.py`, `src/blend/types.py`, **novo** `src/blend/mashability.py`, `src/blend/pipeline.py`, infra de `eval/` · Status: **ABERTA — proposta de produto (pós-entrega 01/07); requer brainstorming/review da equipe antes de implementar**

## Problema / motivação

O score de compatibilidade atual (H2, `compatibility.py`) é uma heurística **feita à mão e simétrica**: harmônico (tabela Camelot) + tempo (BPM ratio) + energia. Ele é interpretável e bom como baseline científico — mas a literatura 2024–2026 (AutoMashup'25, **COCOLA**, Stem-JEPA) mostra que **mashability é assimétrica**: vocal-de-A-sobre-base-de-B ≠ vocal-de-B-sobre-base-de-A, e o papel funcional de cada faixa (quem é vocal, quem é base) importa. Uma heurística simétrica **não consegue** expressar isso.

A boa notícia (e a resposta à pergunta "treinar um modelo?"): existe um modelo **pré-treinado, com pesos liberados, minúsculo e assimétrico por construção** — o **COCOLA** (EfficientNet-B0, embedding 512-dim, forma bilinear `sim(h₁,h₂)=h₁ᵀW h₂`, com `W` aprendido → direcional). Roda em segundos e cabe folgado na RTX 2060. **Não se treina encoder do zero** (inviável: dados/VRAM): congela-se o COCOLA (só inferência) e treina-se apenas uma **cabeça de calibração minúscula** (regressão logística / LightGBM, ~centenas de params) que funde o score COCOLA direcional com os componentes do H2 já existentes. Este é o **único "modelo treinado" que vale** no roadmap.

## Hipótese (experimento) e como validar

**H-novo (mashability):** um ranker aprendido e **assimétrico** correlaciona melhor com a qualidade percebida do que o score heurístico simétrico (H2). Não substitui o H2 — convive com ele.

**Validação:** Spearman (score × notas do painel) da cabeça calibrada **vs.** o `compatibility_score` puro, em hold-out. Ganho positivo justifica o modelo. Como diagnóstico de assimetria: verificar que `learned_score(A→B) ≠ learned_score(B→A)` e que a direção preferida bate com o ouvido/painel.

## Escopo

**Entra:**
- **2a. COCOLA congelado (entrega zero-shot, sem rótulos):** novo módulo `mashability.py` que carrega o checkpoint `COCOLA_HP_v1`, resample 16 kHz + variante HPS, gera embeddings (vocal de A, instrumental de B) e calcula o score **direcional** bilinear **nos dois sentidos**. Já dá um ranking de produto **antes** de qualquer rótulo (o AutoMashup faz exatamente isto). Cache de embeddings em `data/embeddings/` (1× por faixa, não por par).
- **2b. Rótulos pareados (P4, reusa infra existente):** coleta A/B cego ("qual mashup é mais musical?") usando `eval/gera_estimulos.py`, `eval/analise.py`, `respostas_ab.csv` — os **mesmos rótulos servem para H1 e como alvo de ranking** (custo marginal ~zero). Meta: ~150–400 pares **direcionais**; rotular os mais incertos primeiro (margem do score COCOLA como active-learning-lite).
- **2c. Cabeça de calibração:** logística/LightGBM fundindo features → score de produto. **COCOLA permanece congelado**; só a cabeça treina (segundos–minutos, GPU ou CPU).

**Não entra:**
- Treinar/fine-tunar o encoder COCOLA (ou qualquer encoder) do zero.
- Substituir o `compatibility_score` heurístico — ele **fica intacto** como baseline interpretável e âncora do H2.
- Stem-JEPA (fica como **plano B** de encoder, na Fase 3, se COCOLA decepcionar em funk×house).

## Abordagem técnica (design do modelo)

**Arquitetura recomendada:** COCOLA congelado (engine) + features baratas (auxiliares) + cabeça supervisionada minúscula (fusão).

```
features = [
  cocola(emb_vocal_A, emb_instr_B),   # score direcional A→B  (assimétrico, o diferencial)
  cocola(emb_vocal_B, emb_instr_A),   # direção reversa (diagnóstico / "qual faixa doa o vocal?")
  comp_harmonico, comp_tempo, comp_energia,   # componentes do H2 já existentes (reuso)
  centroide_espectral_diff, mfcc_cos, rms_por_stem,   # features baratas
  score_alinhamento_estrutural,       # do alignment.py (nivel_fallback / score da seção)
]
mashability = calibrador(features)    # logística OU LightGBM (~50–200 árvores)
```

- **Assimetria:** vem (1) da forma bilinear do COCOLA (`h₁ᵀW h₂ ≠ h₂ᵀW h₁`) e (2) de features role-aware ("este vocal assenta nesta base", nunca "estas duas faixas são parecidas"). A direção reversa habilita um recurso de produto novo: sugerir **qual** faixa deve doar o vocal.
- **Onde computar embeddings:** no pipeline (`make_mashup` já separa `vocal_only` de A e os stems de B → tem o instrumental). COCOLA roda fora do `compatibility.py` puro (espelha como `metricas_por_segmento_de_audio` vive fora do `alignment.py` puro).

## Interface (`src/blend/types.py`)

Estender `ScoreCompat` com campos **opcionais e retrocompatíveis** (default `None`) → `eval/matriz_compatibilidade.py` e todos os testes seguem passando:

```python
learned_score: float | None = None       # score de produto direcional A→B (cabeça calibrada)
learned_score_rev: float | None = None    # direção reversa B→A (diagnóstico de assimetria)
embed_sim: float | None = None            # similaridade bilinear COCOLA crua (diagnóstico)
```

Novo dataclass para injeção (mantém `compatibility.py` puro):

```python
@dataclass
class EmbedFeatures:
    emb_vocal: list[float]      # embedding COCOLA do vocal isolado (A)
    emb_instr: list[float]      # embedding COCOLA do instrumental (B)
    centroide: float | None = None
    mfcc: list[float] | None = None
    rms_por_stem: dict | None = None
```

Novas funções:
- `mashability(a, b, embed: EmbedFeatures | None = None, metricas=None, params=None) -> ScoreCompat` em `compatibility.py`: **chama `compatibility_score`** (reuso da espinha dorsal interpretável) e, se `embed` presente, preenche os campos `learned_*`/`embed_sim`. Sem `embed` → idêntico ao H2 atual (puro, testável).
- Inferência COCOLA isolada em `mashability.py` (load/resample/HPS/embed/score bilinear) — fora da função pura.

## Critério de pronto

- [ ] `mashability.py` carrega o checkpoint COCOLA, gera embeddings e score direcional; cache em `data/embeddings/` funciona (1×/faixa).
- [ ] **Validação zero-shot** nos 11+ pares: o score direcional separa pares bons/ruins **e** `A→B ≠ B→A`; plausibilidade conferida por ouvido. (Gate de risco: se COCOLA não separar em funk×house, registrar e acionar plano B Stem-JEPA.)
- [ ] `mashability(... embed=None)` é byte-idêntico ao `compatibility_score` (não contamina o H2); campos novos opcionais não quebram `tests/test_compatibility.py` nem a matriz.
- [ ] Coleta de rótulos pareados rodando na infra do P4 (`respostas_ab.csv`); ≥ ~150 pares direcionais.
- [ ] Cabeça calibrada treinada (logística/LightGBM); **Spearman da cabeça > Spearman do H2 puro** em hold-out (senão, manter só o zero-shot e documentar).
- [ ] Verificação real: ranking de produto pela API/CLI usando `mashability`; gerar e **ouvir** o top vs. bottom.
- [ ] `pytest` verde.

## Riscos

- **COCOLA treinado em corpora ocidentais/eletrônicos** (MUSDB/MoisesDB/Slakh/CocoChorales), não em funk BR → **validar zero-shot antes** de investir na calibração; Stem-JEPA como plano B.
- Dependência `natten==0.17.3+torch220cu121` (AutoMashup/COCOLA): mesma dor de NATTEN/torch já vencida para o `allin1` — orçar atrito no Docker.
- O ranker melhora **sugestão/ranking**, não a qualidade do áudio renderizado (isso é Fase 1a/1b). Não deixar virar distração das melhorias de musicalidade mais baratas.

## Fontes

- COCOLA (arXiv 2404.16969) — `github.com/gladia-research-group/cocola` (pesos `COCOLA_HP_v1`)
- AutoMashup GRETSI'25 — `github.com/ax-le/automashup`
- Stem-JEPA (arXiv 2408.02514) — `github.com/SonyCSLParis/Stem-JEPA`
