# Plano — Backend de separação Mel-Band RoFormer (Fase 1b)
> Módulo: P1 (blend-audio) · Spec: specs/separacao-roformer.md

> **Status (verificado em venv arm64/M5, com mocks):**
> ✅ Tarefa 1 — dispatch por `BLEND_SEP_BACKEND` (default `htdemucs`; `htdemucs` byte-equivalente; inválido → `ValueError`) ·
> ✅ Tarefa 2 — `_write_tmp_wav`/`_read_stem_wav` (roundtrip) · ✅ Tarefa 4 — `_mapear_2stem` (2-stem → 4 chaves).
> ⏳ **Pendente (exige Docker+GPU + `audio-separator`):** `_rodar_roformer` (chamada real ao Separator —
> implementado como **seam**, não-verificável no Mac), o caminho 4-stem (Tarefa 4b), o fallback OOM real (Tarefa 5),
> e o SDR em MUSDB18 + deps/pesos no Dockerfile (Tarefa 6).

## Objetivo

Adicionar um segundo backend de separação (**Mel-Band RoFormer** via `python-audio-separator`) **atrás da interface estável** `separate(samples, sr) -> dict[str, np.ndarray]`, selecionável por env var `BLEND_SEP_BACKEND` (`htdemucs` default | `roformer`). Stems mais limpos (vocal de A, instrumental de B) com menos vazamento, sem tocar em `pipeline.py`, `synthesis.py` nem `alignment.py`. Default permanece `htdemucs` (caminho garantido na RTX 2060 + 16 GB de RAM); RoFormer é opt-in até provar ganho de SDR sem regressão de viabilidade.

Restrição-chave (pesquisa): a API do `audio-separator` é **file-based** (lê um `.wav`, escreve stems em disco, retorna paths) e **não expõe arrays NumPy in-memory**. Nossa interface é in-memory `(canais, amostras) float32`. O adapter faz a ponte via arquivos temporários (escrever entrada, ler saídas, limpar) — coração da Tarefa 3 e maior ponto de atrito.

Modelos confirmados:
- Default da lib: `model_bs_roformer_ep_317_sdr_12.9755.ckpt` / `model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt` (ambos **2-stem**: vocals/instrumental).
- Mel-Band RoFormer de vocais recomendado: `vocals_mel_band_roformer.ckpt` (Kim, SDR ~12.6) — **2-stem**.
- RoFormer **não tem 4-stem** maduro na lib; 4 stems continuam Demucs. Isso força a decisão 2-stem vs 4-stem (Tarefa 4).
- Arquitetura na lib: **MDXC**; `mdxc_params = {segment_size, override_model_segment_size, batch_size, overlap, pitch_shift}`. Para 6 GB: `batch_size=1`, reduzir `segment_size` se OOM. GPU via `audio-separator[gpu]` (onnxruntime-gpu + CUDA 11.8/12.2).

## Pré-requisitos (Fase 0)

**0.1 — Switch de backend (refactor sem mudança de comportamento).** Generalizar `separation.py` para que o caminho atual vire o backend `"htdemucs"`, com `_MODEL`/`_get_model()` virando cache por backend (`_BACKEND` lido de `BLEND_SEP_BACKEND`, default `"htdemucs"`). `separate()` despacha para `_separate_htdemucs()` / `_separate_roformer()`. (Tarefa 1.)

**0.2 — Deps `audio-separator` no Dockerfile.** Adicionar `audio-separator` ao `requirements.txt`:
- Imagem `Dockerfile` (torch 2.0.1 + cu117): `audio-separator[gpu]` moderno espera torch/CUDA mais novos — **provável conflito** com a stack legada do allin1. Decisão: instalar `audio-separator` **na imagem fallback `Dockerfile.torch26-fallback`** (torch 2.6 + cu126), sem o lock do allin1. Documentar que `BLEND_SEP_BACKEND=roformer` é suportado na `blend-ai:torch26`.
- Pin de `onnxruntime-gpu` compatível com a CUDA da imagem; `numpy` segue pinado.

**0.3 — Pesos assados na imagem.** Os checkpoints baixam de HuggingFace/UVR em runtime. Espelhar a decisão A3 (allin1/Demucs assados): pré-download no build para `BLEND_SEP_MODEL_DIR`. (Tarefa 6.)

## Tarefas ordenadas

### Tarefa 1 — Dispatch por backend em `separation.py` (refactor, comportamento idêntico)

**(a) Arquivos:** `src/blend/separation.py`; `tests/test_separation.py` (novo).

**(b) Passos TEST-FIRST:**
1. `tests/test_separation.py` com cabeçalho padrão (`sys.path.insert(0, .../ "src")`):
   - `test_backend_default_eh_htdemucs`: sem env var → `"htdemucs"`.
   - `test_separate_despacha_para_htdemucs`: `monkeypatch` em `_separate_htdemucs` retornando dict fake `{vocals,drums,bass,other}` `(2,N) float32`; `separate(samples, sr)` devolve exatamente esse dict.
   - `test_backend_invalido_levanta`: `BLEND_SEP_BACKEND=xyz` → `ValueError`.
   - **RED.**
2. Implementar: extrair o corpo atual de `separate()` para `_separate_htdemucs` (idêntico, inclusive fallback OOM e normalização mean/std). Novo `separate()` lê `BLEND_SEP_BACKEND` (helper `_backend()`, default `"htdemucs"`) e despacha. `_separate_roformer` stub `NotImplementedError` por ora.

**(c) Verificação:** `pytest tests/test_separation.py -q` verde; `pytest` completo verde; diff de `separate()` htdemucs byte-equivalente (revisar normalização, `apply_model(split=True, overlap=0.25)`, `try/except OOM`).

### Tarefa 2 — Contrato in-memory ↔ file-based isolado (adapter de I/O temporário)

**(a) Arquivos:** `src/blend/separation.py` (`_write_tmp_wav`, `_read_stem_wav`); `tests/test_separation.py`.

**(b) Passos TEST-FIRST:**
1. Testes (só `soundfile`/`scipy`):
   - `test_roundtrip_tmp_wav`: array `(2,N) float32` → write → read reconstrói shape/dtype com tolerância; confirma orientação `(canais,amostras)`↔`(amostras,canais)`.
   - `test_tmp_cleanup`: temporários removidos (`tempfile.TemporaryDirectory`).
   - **RED.**
2. Implementar `_write_tmp_wav`/`_read_stem_wav` em `(canais,amostras) float32` num context manager. Reusar `soundfile`.

**(c) Verificação:** `pytest tests/test_separation.py -k tmp_wav -q` verde; nada deixado em `/tmp`.

### Tarefa 3 — Backend RoFormer (`_separate_roformer`), mockando o modelo pesado

**(a) Arquivos:** `src/blend/separation.py`; `tests/test_separation.py`.

**(b) Passos TEST-FIRST:**
1. Contrato com `Separator` **mockado** (import dentro da função, monkeypatch em `audio_separator.separator.Separator`):
   - mock de `separate()` escreve dois `.wav` fake (vocals + instrumental) e retorna paths; adapter lê e devolve dict.
   - `test_roformer_retorna_chaves_4stems`: dict com **exatamente** `{"vocals","drums","bass","other"}` (chaves consumidas por `synthesis.render`: `for k,v in base_stems.items() if k != "vocals"`).
   - `test_roformer_shape_dtype`: `(canais,amostras) float32`, mesmo nº de amostras (±1 frame).
   - `test_roformer_soma_instrumental`: `drums+bass+other` reconstrói o instrumental (política da Tarefa 4).
   - **RED.**
2. Implementar `_separate_roformer`: `Separator(output_dir=tmpdir, model_file_dir=env, mdxc_params={segment_size, batch_size:1, overlap:8, override_model_segment_size:True})`; `load_model(model_filename=env BLEND_SEP_ROFORMER_MODEL default "vocals_mel_band_roformer.ckpt")` com cache (`_MODEL`/`_BACKEND`); escrever entrada via `_write_tmp_wav`, `separate(path)`, ler stems, mapear (Tarefa 4), limpar; reamostrar para 44100 e casar comprimento.

**(c) Verificação:** `pytest tests/test_separation.py -k roformer -q` verde (mockado). Sem import de `audio_separator` no topo do módulo (lazy, como `demucs`).

### Tarefa 4 — Decisão 2-stem vs 4-stem (mapeamento de saída)

**Contexto (código real):** `synthesis.render` só usa `vocals` vs "tudo menos vocals" (soma `drums+bass+other`) → 2 stems bastam para a síntese. `alignment.py` usaria `drums+bass` (`groove_rel`) e `other` (`headroom_rel`), mas via `metricas_por_segmento_de_audio`, que é **stub de propósito** (ainda não injeta métricas). Hoje só a síntese consome os stems.

**Decisão recomendada (ratificar no review):** RoFormer **2-stem** mapeado para 4 chaves: `vocals = vocal_stem`, `other = instrumental`, `drums = bass = zeros` (soma "tudo menos vocals" reconstrói o instrumental — único uso real). Caminho **4-stem opcional** atrás de `BLEND_SEP_ROFORMER_STEMS=4`: RoFormer para o vocal + Demucs `htdemucs` só para `drums/bass/other` do instrumental (2 inferências; ligar só quando o consumidor de drums/bass existir).

**(a) Arquivos:** `src/blend/separation.py`; `tests/test_separation.py`.

**(b) Passos TEST-FIRST:**
- `test_mapeamento_2stem`: 4 chaves; `drums`/`bass` zeros; `other == instrumental`.
- `test_mapeamento_4stem` (`BLEND_SEP_ROFORMER_STEMS=4`, ambos mockados): vocal do RoFormer, drums/bass/other do Demucs sobre o instrumental.
- **RED → GREEN.**

**(c) Verificação:** `pytest tests/test_separation.py -k mapeamento -q` verde; conferir que zeros em drums/bass não introduzem NaN/clipping na soma de `synthesis.render`.

### Tarefa 5 — Fallback de memória espelhando o padrão OOM atual

**Padrão a espelhar (htdemucs):** `try cuda → except RuntimeError "out of memory" → empty_cache → cpu`. Para RoFormer: **reduzir `segment_size` em degraus** antes de cair para CPU.

**(a) Arquivos:** `src/blend/separation.py`; `tests/test_separation.py`.

**(b) Passos TEST-FIRST:**
- `test_roformer_oom_reduz_segment`: mock OOM na 1ª chamada e sucesso na 2ª (segment menor); assert reconstrução do `Separator` com `segment_size` menor.
- `test_roformer_oom_cai_para_cpu`: todos os degraus GPU falham → última tentativa força CPU.
- `test_oom_real_reraise`: `RuntimeError` sem "out of memory" propaga (igual ao htdemucs).
- **RED → GREEN.**

Implementação: degraus `BLEND_SEP_SEGMENT_STEPS` (default `[256,128,64]`) → CPU; reinstanciar `Separator` por degrau; `torch.cuda.empty_cache()` entre tentativas.

**(c) Verificação:** `pytest tests/test_separation.py -k oom -q` verde. Documentar que segment menor = menos RAM/VRAM (o chunking limita o pico de host RAM — o que matou `htdemucs_ft`).

### Tarefa 6 — Deps e pesos no Dockerfile (reprodutibilidade)

**(a) Arquivos:** `requirements.txt`; `Dockerfile.torch26-fallback` (alvo primário); `Dockerfile` (best-effort).

**(b) Passos (build é a verificação):**
1. `requirements.txt`: `audio-separator` (pinado, ex. `==0.44.x`) + `onnxruntime-gpu` compatível com a CUDA do fallback.
2. `Dockerfile.torch26-fallback`: após `pip install`, **assar os pesos** (`RUN python -c "from audio_separator.separator import Separator; ... download/load 'vocals_mel_band_roformer.ckpt'"`) e `ENV BLEND_SEP_MODEL_DIR=/opt/blend/models`.
3. `Dockerfile` (torch20/allin1): tentar; documentar no topo que pode não fechar por conflito torch 2.0/cu117 × audio-separator moderno → RoFormer só na `blend-ai:torch26`.

**(c) Verificação (gate de build):** `docker build -f Dockerfile.torch26-fallback ...` conclui; no container, `BLEND_SEP_BACKEND=roformer` separa um clipe sem baixar nada (pesos assados) e sem OOM; `audio-separator --env_info` mostra `CUDAExecutionProvider`.

## Riscos e mitigação

- **RAM de sistema 16 GB (matou `htdemucs_ft`).** `batch_size=1`, `segment_size` modesto + degraus (Tarefa 5); medir pico. Default continua `htdemucs`.
- **Conflito de stack Docker** (torch 2.0/cu117 × audio-separator + onnxruntime-gpu). Alvo primário é a imagem `torch26`; RoFormer é independente do allin1 (separação ≠ beat/estrutura).
- **API file-based.** Custo de I/O por faixa; `tempfile.TemporaryDirectory` (tmpfs no WSL) + cleanup garantido; overhead pequeno vs. inferência.
- **2-stem ≠ 4-stem reais.** Caminho `BLEND_SEP_ROFORMER_STEMS=4` previsto; hoje 2-stem basta (só a síntese consome).
- **Nome/SDR do checkpoint instável.** `BLEND_SEP_ROFORMER_MODEL` com default explícito + pesos pinados/assados; SDR medido, não assumido.
- **onnxruntime vs PyTorch.** Tratar OOM dos dois mundos no fallback; validar no 1º build.

## Gate de verificação final

- [ ] **`pytest` verde** (todo `tests/`, incl. `test_separation.py` com mocks — sem GPU/modelo).
- [ ] **Contrato preservado:** `roformer` retorna `{vocals,drums,bass,other}`, `(canais,amostras) float32`, mesma sr; default htdemucs byte-equivalente. `pipeline.py`/`synthesis.py`/`alignment.py` **inalterados** (`git diff --stat`).
- [ ] **Cabe em 6 GB:** faixa de ~3 min na RTX 2060; medir VRAM/RAM de pico e tempo; fallback de `segment_size` evita OOM.
- [ ] **SDR em MUSDB18** RoFormer vs htdemucs (tabela em `docs/`/`eval/`, reusar `museval`); aceite = ganho sem regressão de viabilidade.
- [ ] **Fallback** sem GPU/OOM → degrada sem exceção.
- [ ] **Ouvir:** mashup ponta-a-ponta com cada backend — vocal mais limpo, menos vazamento.
- [ ] **Pesos assados** (separação offline).

### Arquivos críticos
- src/blend/separation.py · tests/test_separation.py (novo) · Dockerfile.torch26-fallback · requirements.txt · src/blend/synthesis.py (consumidor, referência do contrato)

### Fontes
- github.com/nomadkaraoke/python-audio-separator · github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model
