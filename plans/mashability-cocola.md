# Plano — Mashability aprendida COCOLA (Fase 2)
> Módulos: P2 (blend-mashup) + P4 (blend-eval) · Spec: specs/mashability-cocola.md

> **Status (verificado em venv arm64/M5, COCOLA mockado):**
> ✅ Tarefa 1 — `mashability()` (H2 + COCOLA direcional; `embed=None` byte-idêntico ao H2) + `EmbedFeatures.sim_ab/sim_ba` ·
> ✅ Tarefa 2 (parcial) — `score_bilinear`, `_preparar_audio` (16 kHz/mono/5 s), `embed_de_audio` (glue) ·
> ✅ Tarefa 3 — cache de embeddings · ✅ Tarefa 7 — `Calibrador` (logística) + `montar_features` · ✅ Tarefa 8 — `comparar_rankers`.
> ⏳ **Pendente (exige Docker+GPU + checkpoint `COCOLA_HP_v1`):** o `_CocolaAdapter` real (carregar pesos + bilinear —
> **seam** não-verificável no Mac), a injeção de `EmbedFeatures` no `make_mashup` (Tarefa 4, depende do COCOLA),
> a validação zero-shot nos pares (Tarefa 5, **gate de risco**) e a coleta de rótulos direcionais (Tarefa 6).

## Objetivo

Adicionar um ranker de mashability **aprendido e assimétrico** (vocal-de-A-sobre-base-de-B ≠ vocal-de-B-sobre-base-de-A) que **convive** com o H2 heurístico sem substituí-lo. A engine é o **COCOLA congelado** (EfficientNet-B0, embedding 512-dim, score bilinear `h₁ᵀW h₂` direcional), só inferência. A fusão final é uma **cabeça de calibração minúscula** (logística/LightGBM) que combina o score COCOLA direcional (dois sentidos) com os componentes já existentes do H2 (`harmonico`, `tempo`, `energia`) e features baratas.

Entrega em três subfases independentemente úteis: **2a** zero-shot (sem rótulos, ranking imediato), **2b** coleta de rótulos pareados reusando a infra do P4, **2c** cabeça calibrada validada por Spearman contra o H2 puro em hold-out.

Invariante de segurança: `mashability(a, b, embed=None)` é **byte-idêntico** a `compatibility_score(a, b)` — o H2 nunca é contaminado.

## Pré-requisitos (Fase 0)

1. **`src/blend/types.py` — estender `ScoreCompat` com 3 campos opcionais (default `None`):**
   ```python
   learned_score: float | None = None       # score de produto direcional A→B (cabeça calibrada)
   learned_score_rev: float | None = None    # direção reversa B→A (diagnóstico de assimetria)
   embed_sim: float | None = None            # similaridade bilinear COCOLA crua (diagnóstico)
   ```
   `ScoreCompat` não é `frozen` e `compatibility_score` constrói por keyword → nenhum construtor existente quebra; `eval/matriz_compatibilidade.py` e `tests/test_compatibility.py` seguem verdes.

2. **`src/blend/types.py` — novo dataclass `EmbedFeatures`** (injeção pelo pipeline, mantém `compatibility.py` puro):
   ```python
   @dataclass
   class EmbedFeatures:
       emb_vocal: list[float]      # embedding COCOLA do vocal isolado (A)
       emb_instr: list[float]      # embedding COCOLA do instrumental (B)
       emb_vocal_b: list[float] | None = None  # vocal de B (direção reversa)
       emb_instr_a: list[float] | None = None  # instrumental de A (direção reversa)
       centroide: float | None = None
       mfcc: list[float] | None = None
       rms_por_stem: dict | None = None
   ```
   (`emb_vocal_b`/`emb_instr_a` para a assimetria A→B vs B→A — confirmar no brainstorming; alternativa: 2ª chamada com `EmbedFeatures` invertido.)

3. **Deps no Docker (`requirements.txt` + `Dockerfile`):** COCOLA usa `torchaudio` (MelSpectrogram), EfficientNet-B0 (`timm`) e o pacote `cocola`. **Confirmar primeiro** se o `cocola` importa `natten` (o encoder normalmente **não** — NATTEN é do AutoMashup): importar num shell do container antes de mexer no Dockerfile. Se houver conflito de torch, **vendorizar** só `contrastive_model/` + `feature_extraction/` (EfficientNet + projeção + MelSpectrogram, deps leves). Adicionar `lightgbm`.

## Tarefas ordenadas

### Fase 2a — COCOLA congelado (zero-shot, sem rótulos)

#### Tarefa 1 — Campos opcionais em `ScoreCompat` + `EmbedFeatures` + `mashability()` reusando `compatibility_score`

**(a) Arquivos:** `src/blend/types.py`; `src/blend/compatibility.py` (nova função pura `mashability`); `tests/test_compatibility.py`.

**(b) Passos TEST-FIRST:**
1. **RED** em `tests/test_compatibility.py`:
   - `test_mashability_sem_embed_identico_ao_h2`: para vários pares (`8A`/`8A`, tritono, tom ausente, com/sem `metricas`), `mashability(a, b, embed=None, metricas=m)` é idêntico campo a campo a `compatibility_score(a, b, m)` **exceto** os 3 novos = `None`.
   - `test_scorecompat_campos_novos_default_none`.
   - `test_mashability_com_embed_preenche_diagnostico`: com `EmbedFeatures` sintético + cabeça fake (retorna `0.42`), `total`/`harmonico`/`tempo` continuam iguais ao H2 e `embed_sim`/`learned_score` são preenchidos.
   - Rodar todo o `test_compatibility.py` original → nenhum antigo quebra.
2. **GREEN** — `mashability(a, b, embed=None, metricas=None, params=None, cabeca=None) -> ScoreCompat`:
   - chama `sc = compatibility_score(a, b, metricas, params)` (reuso);
   - `embed is None` → `return sc` (3 campos ficam `None` → idêntico ao H2);
   - `embed` presente → preencher só `embed_sim` (e `learned_score`/`_rev` se `cabeca`), via `dataclasses.replace`.
   - **`compatibility.py` permanece PURO**: a forma bilinear opera sobre embeddings já calculados; preferência = `embed_sim` **pré-computado** dentro de `EmbedFeatures` por `mashability.py` (espelha `metricas_por_segmento_de_audio` fora do `alignment.py`).

**(c) Verificação:** `pytest tests/test_compatibility.py -q` verde; `python eval/matriz_compatibilidade.py` roda sem erro (retrocompat de `ScoreCompat`).

#### Tarefa 2 — Inferência COCOLA congelada em `src/blend/mashability.py` (NOVO)

**(a) Arquivos:** `src/blend/mashability.py` (NOVO); `tests/test_mashability.py` (NOVO).

**(b) Passos TEST-FIRST (mock do COCOLA — não baixar o modelo nos testes):**
1. **RED** em `tests/test_mashability.py`:
   - `test_preparar_chunk_16k_mono_5s`: `(2, 44100*7)` @44100 → `(1, 16000*5)` mono, 16 kHz, 5 s (`80000` amostras). Resample com `scipy.signal.resample_poly`.
   - `test_score_bilinear_assimetrico`: `W` não-simétrica → `score_bilinear(h1,h2,W) != score_bilinear(h2,h1,W)`.
   - `test_embedder_usa_mock`: monkeypatch do carregador → embed 512-dim + cache consultado.
2. **GREEN** — `mashability.py`:
   - `_carregar_modelo()` lazy singleton (espelha `separation._get_model`): `CoCola.load_from_checkpoint(CKPT)`, `eval()`, `set_embedding_mode(EmbeddingMode.BOTH)`; ckpt via env `COCOLA_CKPT` (default `data/models/COCOLA_HP_v1.ckpt`); HPS opcional.
   - `_feature_extractor()` singleton (`CoColaFeatureExtractor`).
   - `_preparar_audio(samples, sr) -> [1,1,80000]`: mono + resample 16 kHz + 5 s.
   - `embed_de_audio(samples, sr) -> list[float]`: `no_grad`, cuda com fallback CPU (try/except OOM como `separation.separate`).
   - `score_direcional(emb_vocal, emb_instr) -> float` via `model.score(...)` ou bilinear; calcular **nos dois sentidos**.
   - `score_bilinear(h1, h2, W)` puro (numpy) para testes e para `compatibility.py` ler o `embed_sim` pré-computado.

**(c) Verificação:** `pytest tests/test_mashability.py -q` verde (mock). Smoke real (Docker, manual): embeddar 1 par e imprimir `score(A→B)` ≠ `score(B→A)`.

#### Tarefa 3 — Cache de embeddings em `data/embeddings/` (1× por faixa)

**(a) Arquivos:** `src/blend/mashability.py`; `tests/test_mashability.py`.

**(b) Passos TEST-FIRST:**
1. **RED** — `test_cache_chave_por_faixa` (chave = hash do conteúdo + papel vocal|instr + modo; pares que compartilham A reusam); `test_cache_grava_e_le_npy` (`tmp_path`; 2ª chamada não recomputa — monkeypatch conta 1 chamada).
2. **GREEN** — `data/embeddings/<sha1(path)>_<papel>_<modo>.npy`; `np.save`/`np.load`; invalidação por mtime/hash.

**(c) Verificação:** `pytest tests/test_mashability.py -q` verde.

#### Tarefa 4 — Injeção de `EmbedFeatures` pelo pipeline (`make_mashup`)

**(a) Arquivos:** `src/blend/pipeline.py`; `tests/test_smoke.py`.

**(b) Passos TEST-FIRST:**
1. **RED** em `tests/test_smoke.py` com `mashability.embed_de_audio` **mockado**: com a engine COCOLA ligada, `result.score.embed_sim is not None` e `learned_score_rev is not None`; com a engine **desligada** (flag default), `result.score` byte-idêntico ao atual (`embed_sim is None`).
2. **GREEN** — em `make_mashup`, onde já existem `vocal_only` (A) e `stems_base` (B):
   - instrumental de B = soma de `stems_base` menos `vocals`;
   - `emb_vocal_A`/`emb_instr_B` via `embed_cacheado`; direção reversa: `vocal_only_B = stems_base["vocals"]` (já temos!) e instrumental de A (**decisão**: separar A completo ou aproximar pelo mix de A — registrar no brainstorming);
   - `EmbedFeatures(...)` + features baratas (centroide/mfcc/rms);
   - trocar `score = compatibility_score(...)` por `score = mashability(..., embed=ef, cabeca=CABECA)` **atrás de flag** `usar_cocola=False` (default off → zero regressão no experimento H1/H2 da entrega);
   - novo estágio `on_stage("embeddings")`.

**(c) Verificação:** `pytest tests/test_smoke.py -q` verde com mock; manual no Docker com flag on.

#### Tarefa 5 — Validação zero-shot nos 11+ pares (GATE de risco antes de calibrar)

**(a) Arquivos:** `eval/cocola_zeroshot.py` (NOVO; reusa `eval/estimulos.py:selecionar_pares`/`casar_arquivo` + `data/rekordbox/groundtruth.csv`); `tests/test_eval.py` (agregador puro).

**(b) Passos TEST-FIRST:** se houver função pura de agregação (ordenar por `embed_sim`, separação bons/ruins, assimetria média `|A→B − B→A|`), testá-la com dados sintéticos. **GREEN** — tabela `par | embed_sim(A→B) | embed_sim(B→A) | Δassimetria | H2.total` ranqueada.

**(c) Verificação (GATE):** no Docker, confirmar que (1) `embed_sim` **separa** bons de ruins e (2) `A→B ≠ B→A` sistemático; conferência **por ouvido** top vs bottom. **Se não separar em funk×house → registrar e acionar plano B (Stem-JEPA, Fase 3); não prosseguir para 2c.**

### Fase 2b — Rótulos pareados (P4, reusa infra existente)

#### Tarefa 6 — Coleta de rótulos direcionais reusando `eval/` e `respostas_ab.csv`

**(a) Arquivos:** `eval/gera_estimulos.py` (estender p/ pares **direcionais** A→B vs B→A); `eval/estimulos.py` (seleção direcional); `data/experimento/respostas_ab.csv` (formato já lido por `ab_de_df`: `avaliador,par_id,id_preferido`).

**(b) Passos TEST-FIRST:** **RED** — `selecionar_pares_direcionais` (ou flag) emite as **duas direções** por par, priorizando **menor margem** de `embed_sim` (active-learning-lite); asserir contagem e presença das duas direções. **GREEN** — gerar estímulos das duas direções via `make_mashup` trocando `path_vocal`/`path_base`. Os mesmos rótulos servem H1 **e** o ranker. Meta ~150–400 pares direcionais.

**(c) Verificação:** `pytest tests/test_eval.py -q` verde; `python eval/gera_estimulos.py --listar` mostra as direções.

### Fase 2c — Cabeça de calibração

#### Tarefa 7 — Treino da cabeça (logística/LightGBM) sobre features fundidas

**(a) Arquivos:** `src/blend/mashability.py` (classe `Calibrador`: `fit`/`predict`/`salvar`/`carregar`); `eval/treina_cabeca.py` (NOVO); `tests/test_mashability.py`.

**(b) Passos TEST-FIRST:** **RED** — `test_calibrador_aprende_separavel` (features separáveis → ordenação recuperada); `test_calibrador_serializa`; `test_montar_features` (de `EmbedFeatures` + `ScoreCompat` extrai vetor exato `[cocola_AtoB, cocola_BtoA, harmonico, tempo, energia, centroide_diff, mfcc_cos, ...]`, testar ordem e `None`). **GREEN** — `Calibrador` (sklearn logística ou LightGBM ~50–200 árvores); features = bloco da spec + `score_alinhamento_estrutural` (do `plan.nivel_fallback`/seção). **COCOLA congelado** — só a cabeça treina (segundos).

**(c) Verificação:** `pytest tests/test_mashability.py -q` verde; treino real em CPU em segundos.

#### Tarefa 8 — Validação Spearman da cabeça vs. H2 puro em hold-out

**(a) Arquivos:** `eval/analise.py` (reuso de `spearman_h2`; comparativo cabeça vs H2); `eval/treina_cabeca.py` (split treino/hold-out); `tests/test_eval.py`.

**(b) Passos TEST-FIRST:** **RED** — `comparar_rankers(learned, h2, notas)` retorna os dois Spearman + delta (reusa `spearman_h2` com IC95% bootstrap). **GREEN** — comparativo alimentado pelo split.

**(c) Verificação:** `pytest tests/test_eval.py -q` verde. **Critério científico:** `Spearman(cabeça) > Spearman(H2 puro)` em hold-out justifica a cabeça; senão, manter só o zero-shot e documentar (o H2 segue intacto).

## Riscos e mitigação

- **COCOLA treinado em corpora ocidentais/eletrônicos**, não em funk BR. Mitigação: Tarefa 5 é **gate** — validar zero-shot (separação + assimetria + ouvido) **antes** de coletar (2b)/calibrar (2c). Os 11 pares atuais (tech house) são o caso mais favorável. Plano B: Stem-JEPA (Fase 3).
- **`natten`/`torch` no Docker.** Encoder é EfficientNet-B0 (provavelmente sem NATTEN). Mitigação: confirmar deps reais; se conflitar, vendorizar só `contrastive_model/` + `feature_extraction/`. Cache (Tarefa 3) reduz inferência a 1×/faixa.
- **Ranker melhora ranking, não áudio renderizado.** Mitigação: flag `usar_cocola` default **off** → experimento H1/H2 da entrega não muda; ranker é estritamente aditivo, fora do caminho crítico.
- **Contaminação do H2.** Mitigação: teste de identidade byte-a-byte (Tarefa 1) + `compatibility.py` puro (álgebra de `W` e checkpoint só em `mashability.py`).

## Gate de verificação final

- [ ] `mashability(... embed=None)` byte-idêntico a `compatibility_score`; campos novos não quebram `test_compatibility.py` nem `eval/matriz_compatibilidade.py`.
- [ ] `mashability.py` carrega COCOLA, gera embeddings 512-dim e score direcional; **cache em `data/embeddings/` (1×/faixa)**.
- [ ] **Zero-shot (gate):** separa bons/ruins **e** `A→B ≠ B→A`; ouvido confirma top vs bottom.
- [ ] Rótulos pareados/direcionais no P4 (`respostas_ab.csv`); ≥ ~150 direcionais.
- [ ] Cabeça calibrada; **Spearman(cabeça) > Spearman(H2 puro)** em hold-out (senão: zero-shot + documentar).
- [ ] `pytest` **verde** (suíte inteira).

### API COCOLA (verificada)
`CoCola.load_from_checkpoint(ckpt)`; `model.set_embedding_mode(EmbeddingMode.BOTH|HARMONIC|PERCUSSIVE)`; `CoColaFeatureExtractor()`; `features = feature_extractor(x)`; `model.score(features_x, features_y)`; entrada **mono, 16 kHz, 5 s** `[B,1,80000]`; embedding **512-dim**, EfficientNet-B0, similaridade **bilinear** (assimétrica). Checkpoint `COCOLA_HP_v1` via Google Drive → `data/models/`.

### Arquivos críticos
- src/blend/mashability.py (NOVO) · src/blend/compatibility.py · src/blend/types.py · src/blend/pipeline.py · eval/estimulos.py

### Fontes
- github.com/gladia-research-group/cocola · arXiv 2404.16969
