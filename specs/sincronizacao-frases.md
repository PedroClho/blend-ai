# Spec — Sincronização frase-a-frase do vocal (Fase 1a)

> Módulo: P2 (`blend-mashup`) · Arquivos: `src/blend/alignment.py`, `src/blend/synthesis.py`, `src/blend/types.py`, `src/blend/pipeline.py` · Status: **ABERTA — proposta de produto (pós-entrega 01/07); requer brainstorming/review da equipe antes de implementar**

> Incremento já antecipado em [`alinhamento-estrutura-aware.md`](alinhamento-estrutura-aware.md) ("sincronização frase-a-frase = incremento confirmado, fora do MVP") e em `Trabalhos Futuros` do roadmap de produto. Esta spec o destrava.

## Problema / motivação

Hoje o `proposto` ancora **o vocal inteiro** num único downbeat da seção de groove escolhida (`AlignmentPlan.vocal_offset`) e a síntese (`synthesis.render`) o solta de uma vez. Funciona, mas as **frases internas** do vocal vão derivando: depois da 1ª frase, as entradas seguintes raramente caem em downbeat da base, e o ouvido percebe o vocal "fora da grade" mesmo com BPM casado. É o maior ganho de musicalidade ainda na mesa — e é **pura engenharia de DSP** (não precisa de modelo): a base já entrega `beats`/`downbeats`/`segments` (P1), e o pipeline já tem o **stem vocal isolado** de A (`vocal_only` em `make_mashup`).

## Hipótese (se experimento) e como validar

Não é uma hipótese nova; **reforça H1** (alinhamento estrutura-aware > ingênuo). Pode entrar no experimento de dois jeitos (decidir no review):

- **(a) Dobrado no `proposto`:** o braço proposto passa a incluir seção + frases-no-downbeat. H1 fica mais forte, mas mistura dois fatores.
- **(b) Terceiro braço:** `baseline` < `proposto-seção` < `proposto-seção+frases`, isolando o efeito da sincronização de frases (Friedman/Wilcoxon pareado entre os três).

**Validação direta:** % de inícios de frase que caem a ≤ ε ms de um downbeat da base (antes vs. depois); e A/B cego no painel (reusa a infra do P4 em `eval/`).

## Escopo

**Entra:**
1. **Detecção de frases no stem vocal de A** por gaps de baixa energia RMS (silêncios) → fronteiras `(início, fim)` de cada frase, em tempo de A. (A spec de alinhamento já prevê isto: "detecção de silêncio (gaps de baixa energia RMS) no stem vocal → fronteiras de frase".)
2. **Mapeamento de cada início de frase ao downbeat mais próximo** da base dentro da seção alvo, gerando `phrase_anchors`.
3. **Renderização frase-a-frase** em `synthesis.render`: cada frase recortada, esticada/transposta (mesmos `bpm_ratio`/`pitch_shift` do plano) e colocada no seu downbeat-alvo, com os fades de borda já existentes (`_recortar`).

**Não entra:**
- Quantização que **reordene** frases ou altere o conteúdo vocal além de micro-ajustes de timing (preserva a invariante de conteúdo da H1 — ver abaixo).
- Esticamento por frase com `ratio` diferente do global (no MVP desta feature, micro-stretch só para encaixar o início no downbeat; warp interno fica para futuro).
- Troca do detector de silêncio por modelo aprendido (VAD neural) — futuro, se RMS falhar em vocais muito processados.

## Abordagem técnica

1. **Frases (em tempo de A):** RMS por janela curta (~`win_s`); fronteira de frase onde a energia cai abaixo de `silence_db` por ≥ `min_gap_s` e volta. Frases curtas demais (< `min_frase_s`) fundem com a vizinha. Determinístico e testável com sinal sintético (impulsos/silêncios).
2. **Âncoras:** para cada frase `i` com início `t_voc_i` (tempo de A), o alvo é `downbeat_base mais próximo de (vocal_offset + (t_voc_i − t_voc_0)/bpm_ratio)` **dentro** de `target_segment`. Snap só se o deslocamento for ≤ `snap_tol_compassos` (senão mantém a posição derivada — não força encaixe que distorça).
3. **Render:** itera as frases; cada uma vira um bloco `[t_voc_i, t_voc_{i+1})` recortado, `_stretch_pitch` aplicado, somado no `mix` no offset-alvo. Mantém HPF/gain-match/ducking já existentes, aplicados ao vocal montado.

## Interface (`src/blend/types.py`)

Estender `AlignmentPlan` **exatamente como a spec de alinhamento já propôs** (campo opcional, retrocompatível):

```python
phrase_anchors: list[tuple[float, float]] | None = None  # (t_no_vocal_s_de_A, t_na_base_s_de_B)
```

- `align(...)` continua sem ler áudio (contrato `TrackAnalysis`): **não** preenche `phrase_anchors`.
- Nova função (P2), computada onde há o stem vocal — no **pipeline** (`make_mashup`, já tem `vocal_only`):
  `sincronizar_frases(vocal_samples, sr, an_vocal, plan, base_downbeats, params) -> list[tuple[float,float]]`.
- `synthesis.render`: se `plan.phrase_anchors is None` → comportamento atual (âncora única) — **fallback garantido**. Se preenchido → render frase-a-frase.

> **Invariante de H1 preservada:** o conteúdo vocal (quais 16 compassos de A) continua escolhido por `_recorte_vocal` (`pipeline.py`), idêntico entre braços. A sincronização de frases só muda **colocação/timing dentro do trecho**, nunca o conteúdo — e cai para âncora única quando `phrase_anchors` é `None` (baseline e nível_fallback 4 nunca usam frases).

## Critério de pronto

- [ ] `sincronizar_frases` implementada; detector de frases testável com sinal sintético (silêncios/impulsos): nº de frases, fronteiras, fusão de frases curtas.
- [ ] Âncoras: teste de snap (frase perto de downbeat encaixa; frase longe não é forçada além de `snap_tol_compassos`); âncoras vazias quando não há downbeats → `render` cai para âncora única.
- [ ] `synthesis.render` com `phrase_anchors=None` produz **byte-idêntico** ao comportamento atual (regressão — protege a invariante de H1).
- [ ] Render frase-a-frase: cada frase soma no offset-alvo; sem clipping (normalização de pico já existe); fades de borda preservados.
- [ ] **Verificação real:** gerar `proposto` com e sem frases numa dupla tech house × tech house e **ouvir**; medir % de frases em downbeat (antes/depois).
- [ ] `pytest` verde — nenhum teste existente de `alignment`/`synthesis` quebra (campo novo é opcional).
