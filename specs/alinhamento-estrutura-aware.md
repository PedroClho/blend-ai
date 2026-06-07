# Spec — Alinhamento estrutura-aware (H1)

> Módulo: P2 (`blend-mashup`) · Arquivo: `src/blend/alignment.py` · Status: **FECHADA — pronta para implementar** (decisões 1–3 + ajustes da crítica adversarial fechados no review 2026-06-07)

## Problema / motivação

Inserir o vocal de A sobre a base de B exige decidir **onde** (em que ponto da base) e **como** o vocal entra. O jeito ingênuo — empurrar o vocal a partir do 1º downbeat da faixa — costuma cair sobre a intro ou um breakdown, quebrando a ilusão musical. A hipótese do trabalho é que usar a **estrutura musical** (escolher uma seção de groove e ancorar o vocal nos downbeats dela) gera mashups mais musicais. Este é o núcleo da contribuição.

## Hipótese (H1) e como validar

**H1:** o alinhamento estrutura-aware produz mashups avaliados como mais musicais do que o baseline ingênuo.

A feature **não testa** H1 sozinha — ela **expõe os dois modos** (`baseline` e `proposto`) para que o P4 (`blend-eval`) gere as duas versões e rode o experimento subjetivo às cegas (Wilcoxon). O critério aqui é: os dois caminhos existem, são reproduzíveis e diferem **apenas** no que define a hipótese (seção + ancoragem), mantendo o resto igual (mesma separação, mesmo stretch/pitch) para um teste justo. **O experimento inicial usa pares tech house × tech house (BPM com 1–3 de diferença)** para controlar a variável tempo e isolar o efeito da estrutura; funk × house (gap grande de BPM) fica para teste de robustez futuro.

## Escopo

**Baseline (`mode='baseline'`):**
1. Casar BPM (time-stretch do vocal) e tom (pitch-shift).
2. Vocal entra no **1º downbeat da base**. Sem escolha de seção, sem ancoragem por frase.

**Proposto (`mode='proposto'`):**
1. Mesmo casamento de BPM e tom.
2. **Escolher uma seção de groove** da base (não intro/outro/break).
3. **Ancorar o início do vocal ao 1º downbeat dessa seção.**
4. *(incremento — fora do MVP, confirmado)* sincronizar **cada frase vocal** a um downbeat da seção.

**Não entra nesta feature:** separação (P1), análise/segments (P1), o time-stretch/pitch em si (fica em `synthesis.py`), o experimento estatístico (P4). Aqui produzimos só o **plano** (`AlignmentPlan`); a síntese o executa.

## Abordagem técnica (decisões de design)

1. **Casar BPM (half/double-time fica para o futuro).** Escolher o fator `f ∈ {0.5, 1, 2}` que deixa `f · bpm_vocal` mais próximo de `bpm_base`; `bpm_ratio = bpm_base / (f · bpm_vocal)`. No MVP **tech house × tech house** (BPM 1–3 de diferença) o stretch é < ~3% e `f = 1` sempre — sem gargalo. A regra de half/double-time e o limiar `max_stretch_pct` existem para o caso futuro **funk × house** (ex.: 150 × 126), onde o stretch grande deve ser penalizado no score (H2).
2. **Escolher a seção de groove.** Score composto por candidata, com **headroom vocal** — ver a "Decisão do agente `blend-mashup`" abaixo para o critério detalhado, fallback e parâmetros.
3. **Transposição com regra H3.** Transpor o vocal para o tom da base **só se** a distância Camelot exceder um limiar; abaixo dele, deixar sem transpor (vocais declamados de funk toleram — H3). Limiar é parâmetro.
4. **Segmentar o vocal em frases** *(parte do incremento)*: detecção de silêncio (gaps de baixa energia RMS) no stem vocal → fronteiras de frase. Ancorar o início de cada frase ao downbeat mais próximo na seção de destino.

## Interface (`src/blend/types.py`)

`align(vocal: TrackAnalysis, base: TrackAnalysis, mode='proposto') -> AlignmentPlan`

O `AlignmentPlan` ganha o campo de diagnóstico **`nivel_fallback: int = 0`** (0 = caminho principal; 1–4 = degraus do fallback) — o P4 usa para auditar quantos planos `proposto` degradaram para baseline (nível 4); sem isso, H1 fica enviesada sem que se saiba. Os demais campos (`target_segment`, `bpm_ratio`, `pitch_shift_semitones`, `vocal_offset`, `mode`) cobrem o MVP. Para a sincronização por frase (incremento), **propor estender** com:

```python
phrase_anchors: list[tuple[float, float]] = []  # (t_no_vocal_s, t_na_base_s)
```

Detectar frases precisa do **áudio do vocal** (não só da análise). Como a sincronização por frase é incremento (fora do MVP), o `phrase_anchors` fica como extensão futura: quando entrar, `align` recebe também os samples do vocal (ou um passo separado produz os anchors).

> **Onde a energia é computada:** `align` **não lê áudio** — preserva o contrato (`TrackAnalysis` apenas) e a testabilidade 100% sintética. As métricas por segmento (groove + headroom vocal) são computadas por um helper no **pipeline** (`make_mashup`, que já carrega os stems da base para a síntese) e **injetadas** na função pura de escolha de seção.

## Parâmetros (transversais)

- `max_stretch_pct = 8` — acima disso, baixa compatibilidade (futuro funk × house).
- `camelot_transpose_threshold = 2` — distância Camelot a partir da qual transpõe (H3).

> Os parâmetros da **escolha de seção** (pesos do score, `min_segment_bars`, `groove_labels`, etc.) estão na Decisão do agente abaixo.

## Critério de pronto

- [ ] `align` implementado para os dois modos, diferindo só em seção + ancoragem.
- [ ] **Função pura** `escolher_secao_groove(...)` testável com `TrackAnalysis` sintético (sem áudio): score, empates determinísticos, e **um teste por nível de fallback** (sem candidata groove; só intro/outro; todos `unknown`; sem downbeats; `bpm` inválido).
- [ ] Teste de **paridade determinística**: com as métricas de áudio ausentes (`None`), a escolha é reproduzível entre execuções (requisito do experimento P4).
- [ ] Testes: `bpm_ratio` (half/double); `pitch_shift` respeitando o limiar H3; seção escolhida = groove esperado; `vocal_offset` = downbeat da seção (+1 compasso) vs 1º downbeat (baseline).
- [ ] Verificação real: gerar baseline + proposto numa dupla **tech house × tech house** e **ouvir** a diferença.

## Decisões do review (2026-06-07)

1. **Domínio inicial = tech house × tech house** (vocal de uma faixa sobre a base de outra), com **BPM 1–3 de diferença**. Controla a variável tempo (stretch < ~3%, sem half/double) e isola o efeito da estrutura para testar H1 limpo, usando as 11 bases já em `data/raw/bases/`. **funk × house fica como visão/teste de robustez futuro** (gap grande de BPM). A regra de half/double-time e o `max_stretch_pct` permanecem na spec para esse futuro, mas não são gargalo no MVP.
2. **Sincronização frase-a-frase = incremento confirmado** (fora do MVP). MVP do proposto = **seção de groove + ancoragem no 1º downbeat da seção**. `phrase_anchors` (+ samples do vocal) fica como extensão futura.

### Decisão do agente `blend-mashup` (2026-06-07) — critério de escolha da seção de groove **[FECHADA]**

**Critério:** **score composto por candidata**, numa **função pura** `escolher_secao_groove(segments, downbeats, bpm, metricas_por_segmento=None, params) -> (Segment, nivel_fallback)`. Nenhum critério isolado serve (maior energia → drop curto saturado; mais longa → intro/break; primeira verse/drop → depende do rótulo ruidoso do allin1; mais repetida → loop curto). `align` **não lê áudio** — recebe as métricas por segmento já computadas pelo pipeline, mantendo a testabilidade 100% sintética.

**Energia + headroom vocal (computados pelo pipeline, injetados).** `Segment` só tem `(start, end, label)`. O pipeline (`make_mashup`, que já carrega os stems da base para a síntese) computa por segmento:
- `groove_rel` — RMS de **drums+bass** (kick/baixo = groove cheio), normalizado pelo máximo da faixa → [0,1].
- `headroom_rel` — quão **livre** está a banda vocal (~200 Hz–4 kHz): RMS nessa banda do conteúdo melódico da base (stem `other`, ou mix), **invertido** e normalizado → [0,1] (mais espaço = maior). Ataca o **mascaramento espectral** — o trecho mais cheio costuma ser o que mais mascara o vocal; aqui o vocal precisa de groove pleno **e** médios livres.
- `vocal_fit_rel = groove_rel · headroom_rel` — alto **só** quando há groove **e** espaço (produto). É o termo dominante do score.

Tudo opcional: se `metricas_por_segmento is None` (sem stems / teste sintético), o termo de `vocal_fit` sai e seu peso é redistribuído proporcionalmente → o critério degrada para "maior seção de groove recente", puro e determinístico. **Em produção, com stems disponíveis, nunca é `None`** (usa o mix se faltar `other`); o P4 marca execuções degradadas para não contaminar o Wilcoxon.

**Pipeline de seleção (`proposto`):**
1. `bar_s = 4·60/bpm_base` (sempre o BPM da **base** — não o do vocal nem o pós-stretch); `dur_min_s = min_segment_bars · bar_s`. **Guarda:** se `bpm_base ≤ 0`/None ou há `end ≤ start`, pular direto ao fallback (sem exceção). Normalizar rótulos (lower/strip + sinônimos `instrumental→inst`, `refrão→chorus`, `breakdown→break`; vazio→`unknown`). **Fundir segmentos adjacentes de mesmo rótulo** antes de filtrar (o allin1 fragmenta tech house em 4–8 compassos e zeraria candidatas).
2. **Filtrar candidatas GROOVE:** `label ∈ groove_labels` **e** `dur ≥ dur_min_s`. Descartar `edge_labels`.
3. **Pontuar** (termos normalizados entre candidatas):
   - `0.45 · vocal_fit_rel` — groove pleno **com** banda vocal livre (ver acima).
   - `0.25 · recencia_inversa` — `1 − rank_por_start/(n−1)`; a 1ª seção cheia após a intro (onde o DJ solta o vocal).
   - `0.20 · duracao_rel` — `dur/maior_dur`; proxy estável da seção principal, desempata.
   - `0.10 · repeticao` — rótulo igual + `vocal_fit` ~igual (±`repeticao_tol`), normalizado. **Peso baixo de propósito**: em tech house homogêneo é fraco discriminante.
   - **Bônus** `+0.05` se `label ∈ {chorus, drop}` — cético, porque o rótulo do allin1 é ruidoso.
4. **Escolher** `argmax(score)`. Empates determinísticos: `|Δscore| < score_eps` → maior `vocal_fit_rel` (médios mais livres); depois maior duração; depois menor `start`.
5. **Ancorar:** `vocal_offset` = 1º downbeat da base `≥ target_segment.start`; **+1 compasso (`bar_s`)** quando a seção é longa o bastante (`≥ min_segment_bars+1`), para não jogar a 1ª frase em cima do riser/crash de transição da fronteira. Se nenhum downbeat cai na seção, o mais próximo do `start`; se `downbeats` vazio, o próprio `start`.

**Fallback em cascata determinística** (parar no 1º que resolver; **gravar `nivel_fallback`** no plano):
- **Nível 1** — sem candidata GROOVE: ignorar rótulos, todos os não-borda com `dur ≥ dur_min_s`, pontuar por `vocal_fit + recência + duração` (sem bônus). `break/bridge` voltam como candidatas de **2ª classe** se tiverem groove (`groove_rel` acima da mediana) — recupera o breakdown-com-beat sem reabilitar breakdown vazio.
- **Nível 2** — só segmentos curtos: relaxar `dur_min_s → dur_min_s/2`; senão o não-borda mais longo.
- **Nível 3** — `segments` vazio/só borda: janela deslizante de `min_segment_bars` compassos a partir de `fallback_skip_intro_frac` da faixa; escolher a de maior `vocal_fit` sustentado (ou a 1ª pós-skip sem energia); ancorar no downbeat dela.
- **Nível 4** — sem downbeats / nada acima: `vocal_offset = downbeats[0]` (ou `0.0`), seção sintética = faixa inteira. **Equivale ao baseline** (`mode='proposto'`, `nivel_fallback=4`) — garante que o proposto **nunca fica pior que o baseline** (teste justo de H1).

**Baseline (`mode='baseline'`):** seção sintética cobrindo a faixa, `vocal_offset = downbeats[0]` (ou `0.0`). Não passa pela escolha de seção. Baseline e proposto diferem **só** em seção + ancoragem.

**Parâmetros (defaults a calibrar no painel):** `w_vocalfit/w_recencia/w_duracao/w_repeticao = 0.45/0.25/0.20/0.10`; `bonus_label = 0.05` (chorus/drop); `min_segment_bars = 8`; `groove_labels = {verse, chorus, drop, inst}`; `edge_labels = {intro, outro, break, bridge, build, start_loop, end_loop, silence, fadein, fadeout}`; `vocal_band_hz = (200, 4000)`; `energy_source = drums+bass` (headroom de `other`/mix); `rms_win_s = 1.0`; `repeticao_tol = 0.15`; `score_eps = 0.02`; `tie_eps_s = 0.5`; `fallback_skip_intro_frac = 0.10`.

> **Trabalho futuro registrado (da crítica adversarial):** repetição via self-similarity de chroma/MFCC (em vez de `|Δenergia|`); validar candidata única contra o fallback nível 1 quando ela vence só pelo bônus de rótulo; recência não-monotônica (janela central, penalizando intro e outro).
