# Plano — Sincronização frase-a-frase do vocal (Fase 1a)
> Módulo: P2 (blend-mashup) · Spec: specs/sincronizacao-frases.md

> **Status (parcial, verificado em venv arm64/M5 — 146 testes verdes):**
> ✅ Fase 0 (`AlignmentPlan.phrase_anchors`) · ✅ `_detectar_frases` · ✅ `sincronizar_frases` ·
> ✅ render frase-a-frase (`_render_frases` + ramo em `render`; caminho de âncora única **byte-idêntico**).
> ⏳ **Pendente (exige Docker+GPU):** Tarefa 6 (wiring no `make_mashup`) e os gates de áudio
> (ouvir baseline vs proposto, % de frases em downbeat). As funções puras estão prontas e testadas;
> falta só ligá-las no pipeline e validar com áudio real.

## Objetivo

Fazer com que **cada frase interna** do vocal de A entre num downbeat da base de B (não só a primeira), eliminando a deriva que hoje deixa o vocal "fora da grade" depois da 1ª frase. O ganho é puro DSP determinístico: a base já entrega `downbeats` (P1) e o pipeline já tem o stem vocal isolado (`vocal_only` em `make_mashup`).

A implementação tem três peças:
1. **Detector de frases** sobre o stem vocal de A (gaps de RMS baixo → fronteiras `(início, fim)` em tempo de A).
2. **`sincronizar_frases(...)`** que mapeia cada início de frase ao downbeat mais próximo da base dentro da seção alvo, com snap tolerante, produzindo `plan.phrase_anchors`.
3. **Render frase-a-frase em `synthesis.render`**: itera as frases, recorta/estica/transpõe cada uma e a soma no offset-alvo, preservando HPF (`_passa_altas`), gain-match por RMS e ducking já existentes.

**Invariante de H1 inviolável:** o conteúdo vocal (quais 16 compassos de A, via `_recorte_vocal`/`CLIPE_COMPASSOS=16`) continua idêntico entre os braços. A sincronização só muda **colocação/timing dentro do trecho**, nunca o conteúdo. E `render(..., phrase_anchors=None)` deve ser **byte-idêntico** ao comportamento atual (fallback garantido — baseline e `nivel_fallback=4` nunca usam frases).

## Pré-requisitos

**Fase 0 — campo `phrase_anchors` em `AlignmentPlan` (retrocompatível).**

Em `src/blend/types.py`, `AlignmentPlan` hoje termina em `vocal_dur`. Adicionar, ao final do dataclass, um campo **opcional com default `None`** (mantém todos os call-sites existentes válidos, pois é o último campo e default não-obrigatório):

```python
phrase_anchors: list[tuple[float, float]] | None = None
# (t_no_vocal_s_de_A, t_na_base_s_de_B) — None = âncora única (comportamento atual)
```

Semântica de cada tupla: `t_no_vocal_s` é o início da frase **em tempo de A, relativo ao recorte** (mesmo referencial de `vocal_in`/`_recortar`); `t_na_base_s` é o downbeat-alvo absoluto em tempo de B (mesmo referencial de `vocal_offset`). Essa convenção precisa ser fixada agora porque amarra detector, mapeador e render.

Pré-requisito de ambiente: imagem `blend-ai:torch20` (ou `torch26`), `pytest` rodando dentro do container. O detector e o mapeador são testáveis **sem** rubberband/GPU (sinais sintéticos), igual aos testes atuais de `test_synthesis.py`.

## Tarefas ordenadas

### Tarefa 1 — Campo `phrase_anchors` em `AlignmentPlan` (Fase 0)

**(a) Arquivos:** `src/blend/types.py`; `tests/test_synthesis.py` (adicionar 1 teste de construção).

**(b) Passos TEST-FIRST:**
- Escrever primeiro `test_alignment_plan_phrase_anchors_default_none` em `tests/test_synthesis.py`: constrói um `AlignmentPlan` com os campos atuais (sem `phrase_anchors`) e assevera `plan.phrase_anchors is None`; constrói outro passando `phrase_anchors=[(0.0, 4.0)]` e assevera leitura de volta igual. Esse teste **falha** na coleta antes de existir o campo.
- Implementar: adicionar o campo opcional ao dataclass conforme Fase 0.

**(c) Verificação:** o novo teste passa e **todos** os testes existentes de `test_alignment.py` e `test_synthesis.py` continuam verdes (default não-obrigatório).

### Tarefa 2 — Detector de frases por RMS/silêncio no stem vocal

**(a) Arquivos:** nova função em `src/blend/synthesis.py` (junto dos helpers `_rms`, `_envelope`, `_passa_altas`):
`_detectar_frases(voc, sr, win_s=0.05, silence_db=-40.0, min_gap_s=0.30, min_frase_s=0.50) -> list[tuple[float,float]]` retornando fronteiras `(início, fim)` em **segundos relativos ao array recebido** (o vocal **já recortado**, ver Tarefa 4). `tests/test_synthesis.py`.

**(b) Passos TEST-FIRST** (escrever antes de implementar):
1. `test_detectar_frases_conta_frases_em_sinal_sintetico`: 3 blocos de tom (1 s) separados por 0,5 s de silêncio → `len(frases) == 3`, fronteiras aprox.
2. `test_detectar_frases_funde_frase_curta`: bloco de 0,2 s (< `min_frase_s`) colado a um de 1 s → **uma** frase.
3. `test_detectar_frases_silencio_total_retorna_vazio_ou_frase_unica`: zero → vazio; tudo ativo → 1 frase `[0, dur)`.
4. `test_detectar_frases_ignora_bleed_fraco`: ruído -60 dB + 2 blocos fortes → 2 frases (espelha robustez de `_melhor_janela_vocal` contra vazamento).

Implementação: RMS por janelas de `win_s` (técnica de `_envelope`/`_melhor_janela_vocal`); dB relativo ao pico; "ativo" onde dB > `silence_db`; fronteira fecha com `≥ min_gap_s` de inativo; fundir frases `< min_frase_s`. Determinístico, sem rubberband.

**(c) Verificação:** os 4 testes passam; roda sem GPU. `pytest tests/test_synthesis.py -q` verde.

### Tarefa 3 — Mapeamento início-de-frase → downbeat com snap tolerante (`sincronizar_frases`)

**(a) Arquivos:** nova função pública em `src/blend/synthesis.py`:
`sincronizar_frases(voc_recortado, sr, plan, base_downbeats, snap_tol_compassos=0.5, bpm_base=None, ...) -> list[tuple[float,float]]`. Reusa `_detectar_frases`. `tests/test_synthesis.py`.

**(b) Passos TEST-FIRST:**
1. `test_sincronizar_frases_snap_perto_de_downbeat`: posição derivada `vocal_offset + (t_voc_i − t_voc_0)/bpm_ratio` cai a poucos ms de um downbeat → `t_na_base` = esse downbeat.
2. `test_sincronizar_frases_nao_forca_quando_longe`: a mais de `snap_tol_compassos` → mantém a posição **derivada**.
3. `test_sincronizar_frases_restringe_a_target_segment`: só snapa em downbeats dentro de `[target_segment.start, end)`.
4. `test_sincronizar_frases_sem_downbeats_retorna_vazio`: `base_downbeats=[]` → `[]` (render cai para âncora única).
5. `test_sincronizar_frases_primeira_ancora_e_o_vocal_offset`: 1ª frase ancora em `plan.vocal_offset` (continuidade com o comportamento atual).

Implementação: detecta frases; `p_i = plan.vocal_offset + (t_voc_i − t_voc_0)/plan.bpm_ratio`; downbeat dentro de `target_segment` mais próximo de `p_i`; snap se `|downbeat − p_i| ≤ snap_tol_compassos·bar_s`, senão mantém `p_i`.

**(c) Verificação:** 5 testes passam; função pura. % de frases que recebem snap medível do retorno (insumo do gate final).

### Tarefa 4 — Render frase-a-frase preservando HPF/gain/ducking

**(a) Arquivos:** `src/blend/synthesis.py` — modificar `render` para ramificar em `plan.phrase_anchors`. `tests/test_synthesis.py`.

**(b) Passos TEST-FIRST:**
1. `test_render_frase_a_frase_posiciona_cada_frase`: 2 blocos de tom com `phrase_anchors=[(t0,off0),(t1,off1)]`, instrumental zerado → energia vocal **nos dois offsets** e silêncio entre/fora.
2. `test_render_frase_a_frase_sem_clipping`: vocal+instrumental fortes + `phrase_anchors` → `max(abs(mix)) <= 1.0+1e-6` (normalização de pico única no fim segue valendo).
3. `test_render_frase_a_frase_aplica_hpf_e_gain`: confirmar HPF (grave atenuado) e gain-match por RMS.

Implementação: quando `phrase_anchors` não-vazio: recortar o trecho global 1×; para cada frase recortar o sub-bloco `[t_voc_i, t_voc_{i+1})` (com fades de `_recortar`); `_stretch_pitch` com os **mesmos** `bpm_ratio`/`pitch_shift` globais; montar `voc_montado` posicionando cada frase no offset-alvo; aplicar **HPF, gain-match e ducking ao vocal montado inteiro** (uma referência de RMS, um ducking). Extrair `_montar_vocal(...)` para os dois ramos compartilharem HPF/gain/ducking/normalização — blinda o byte-idêntico (Tarefa 5).

**(c) Verificação:** 3 testes passam; nenhuma regressão nos testes de render existentes.

### Tarefa 5 — Regressão: `render(..., phrase_anchors=None)` byte-idêntico ao atual

**(a) Arquivos:** `tests/test_synthesis.py` (teste de invariante; escrito **antes** da Tarefa 4 para capturar o comportamento atual).

**(b) Passos TEST-FIRST:**
- `test_render_phrase_anchors_none_byte_identico`: vocal+stems sintéticos fixos (seed determinística), `plan` **sem** `phrase_anchors` → após a Tarefa 4, `np.array_equal(mix_none, mix_referencia)` (ramo `None` ≡ caminho legado).
- `test_render_phrase_anchors_vazio_cai_para_ancora_unica`: `phrase_anchors=[]` segue o caminho de âncora única (mesmo resultado que `None`).

Garantia: o ramo `None`/`[]` **não executa código novo**; o helper `_montar_vocal` deve reproduzir a sequência idêntica de operações (`_recortar` → `_stretch_pitch` → `_to_channels` → `_passa_altas` → gain → `_ducking` → soma → normalização).

**(c) Verificação:** `np.array_equal(mix_none, mix_atual) == True`. Falhar bloqueia o merge.

### Tarefa 6 — Ponto de cômputo no pipeline (`make_mashup`)

**(a) Arquivos:** `src/blend/pipeline.py` — entre o passo 6b (recorte) e o passo 7 (síntese). Verificação comportamental no gate.

**(b) Implementação:**
- Após o recorte e os overrides manuais, e **somente no modo proposto com `nivel_fallback != 4`**: `plan.phrase_anchors = synthesis.sincronizar_frases(vocal_only, sr, plan, an_base.downbeats, bpm_base=an_base.bpm)` (passar o stem + `plan.vocal_in/dur` mantém um único ponto de recorte; `render` re-recorta internamente).
- Manter `phrase_anchors = None` para `mode == "baseline"` e `nivel_fallback == 4` (caminho legado byte-idêntico).
- Respeitar overrides manuais (DJ-in-the-loop): se `vocal_offset` foi passado à mão, recalcular âncoras a partir dele (1ª âncora = offset manual).

**(c) Verificação:** geração proposto não levanta exceção; `plan.phrase_anchors` preenchido quando `nivel_fallback == 0` e `None` no baseline (via `MashupResult.plan`).

## Riscos e mitigação

- **Quebrar a invariante de H1 (crítico).** Mitigação: Tarefa 5 (`np.array_equal`). Conteúdo vocal nunca muda (`_recorte_vocal`/`CLIPE_COMPASSOS=16`); só a colocação. Baseline e `nivel_fallback==4` recebem `None`.
- **Divergência numérica sutil no refator de `render`.** Mitigação: `_montar_vocal` reproduz a sequência atual; o teste byte-idêntico falha imediatamente.
- **Detector dispara em bleed da separação.** Mitigação: `silence_db` relativo ao pico + `min_gap_s`/`min_frase_s`; teste `ignora_bleed_fraco`. VAD neural fica para futuro.
- **Snap forçado distorce o ritmo.** Mitigação: snap só dentro de `snap_tol_compassos·bar_s`.
- **Clicks nas emendas.** Mitigação: fades de borda por frase (`_recortar`); normalização de pico única.
- **`bpm_ratio` por frase desalinharia a seguinte.** Mitigação: posição por downbeat-alvo absoluto (sem acúmulo de deriva); ratio global; warp por frase fora do MVP.

## Gate de verificação final

1. **`pytest` verde** no container (`docker run --rm blend-ai:torch20 pytest -q`); ~14 testes novos passam, nenhum existente quebra.
2. **Ouvir:** gerar proposto **com e sem frases** numa dupla tech house × tech house (das 11 bases) e comparar baseline vs proposto-sem-frases vs proposto-com-frases.
3. **% de frases em downbeat (antes vs depois)** a partir de `plan.phrase_anchors`.
4. **Toggle de fallback:** confirmar que `baseline` e `nivel_fallback==4` produzem `phrase_anchors=None` e render byte-idêntico (protege a comparação justa de H1 no painel do P4).

### Arquivos críticos
- src/blend/types.py · src/blend/synthesis.py · src/blend/pipeline.py · tests/test_synthesis.py · eval/gera_estimulos.py
