# Relatório de Auditoria Técnica — Blend AI
**Data:** 2026-06-12 · **Deadline:** 2026-07-01 (~19 dias) · **Escopo:** 6 dimensões, cada uma com análise original + desafio adversarial · **Hardware:** RTX 2060 6GB / 16GB RAM / Docker Desktop + WSL2

---

## 1. Sumário executivo

**A stack está certa.** Nenhum componente do motor de áudio precisa ser trocado: Demucs v4 `htdemucs`, allin1 (torch 2.0.1+cu117+NATTEN 0.14.6), Essentia EDMA e Rubber Band sobrevivem ao desafio adversarial — em todos os casos as alternativas estado-da-arte 2025/2026 (BS-RoFormer +3,7 dB SDR em vocais, SongFormer 0.807 vs 0.740 no HarmonixSet) foram corretamente rejeitadas porque o ganho não justifica 1–5 dias de troca e risco de OOM/regressão a 2,5 semanas do deadline, e porque H1/H2 são experimentos **relativos** (mesma separação/análise nos dois braços = constante experimental). A única troca confirmada é o frontend (Streamlit → FastAPI + Vite/React), que já está ~60% implementada no repo (`api/server.py` completo, `web/src/` em andamento) — custo restante ~2 dias, não greenfield. **Os dois achados realmente críticos não são de stack, são de execução:** (1) um **confundidor fatal em H1** — `pipeline.py` faz o baseline sobrepor o vocal por quase a faixa inteira com trecho vocal diferente do braço proposto (`dur_na_base = target_segment.end - vocal_offset` + `_melhor_janela_vocal` dependente de `dur_s`), o que invalidaria o experimento se o painel (recurso não-repetível) fosse coletado hoje; (2) **irreprodutibilidade do ambiente** — imagem base marcada "scheduled for DELETION", NATTEN só compila do source (índice de wheels com TLS expirado), pesos do allin1 baixados em runtime de repo HF de mantenedor único, `requirements.txt` sem um único pin, e a imagem atual contém **áudio comercial completo** (`/app/playlist_atv/musicas/*.mp3` + stems) que proíbe qualquer push a registry público. Custo total do plano: **~9–10 dias-pessoa distribuídos em 4 pessoas** — cabe no prazo.

---

## 2. Tabela de vereditos

| # | Dimensão | Veredito | Ação principal | Custo (dias) |
|---|---|---|---|---|
| 1 | Separação de fontes | **Manter** | htdemucs intocado no caminho crítico; vocal BS-RoFormer via MVSEP.com/UVR **só para a demo**, injetado via `vocal_stem_path` (~1h), nunca no experimento | 0 (+0,5 opcional) |
| 2 | Análise rítmica/estrutural | **Manter** | Congelar artefato: fix `.dockerignore` → rebuild → warm-up de pesos baked → `pip freeze` lock → `docker save` em **canal privado** (nunca registry público) | ~1 |
| 3 | Tom e Síntese | **Ajustar** | Passada única RB com `-F` (com branches anti-bug `rate==1.0`); `key_override` Rekordbox no experimento; calibração de tom 11 faixas; RB 3.3/R3 timeboxed em layer final | ~2 |
| 4 | Infra/Ambiente | **Ajustar** | `.wslconfig` (10GB/swap 16GB); ordem freeze→save→prune; `TORCH_CUDA_ARCH_LIST="7.5;8.6+PTX"` (nunca 8.9 em nvcc 11.7); prune ~50GB | ~1,5 |
| 5 | Frontend | **Trocar** | Terminar SPA FastAPI+Vite/React já iniciada; gate e2e no dia 2 com fallback Streamlit; sem multi-stage Docker; commitar untracked após pytest | ~2–2,5 (teto 4) |
| 6 | Rigor científico (P4) | **Ajustar** | `eval/gera_estimulos.py` (vocal idêntico nos 2 braços, ~30s, loudness normalizado); protocolo congelado; itens estratificados por quartil de score p/ H2; A/B forced choice adicional; H3 exploratória | ~2,5–3 |

---

## 3. Análise por dimensão

### 3.1 Separação de fontes — MANTER

**Estado atual.** Demucs v4 `htdemucs` (modelo único; `htdemucs_ft` foi removido em cc92448 porque o bag de 4 modelos estourava RAM/VRAM e derrubava o daemon Docker). Vocal SDR ~8,18 dB (multisong/MVSEP) — bleed audível do instrumental de A no vocal extraído.

**Análise.** BS-RoFormer (ep_317, 2025.07) faz 11,89 dB em vocais — ganho real de +3,7 dB. Mas: (a) não cabe na imagem torch20 (audio-separator exige torch recente; conflito com numpy<1.24/NATTEN 0.14.6); (b) o allin1 usa Demucs internamente, então Demucs é irremovível; (c) a separação **não é a contribuição científica** — idêntica nos dois braços, é constante experimental; bleed é teto de polimento, não viés. Voltar ao `_ft` (+0,15 dB) não vale a RAM já comprovadamente insuficiente.

**Desafio adversarial.** Sustentou o "manter", mas refutou o plano B: o spike de 1 dia com `audio-separator[gpu]` + 2 imagens Docker é a via **cara** para meia dúzia de stems — MVSEP.com (free tier, BS-RoFormer 2025.07) ou UVR GUI no host entregam o mesmo a custo ~0 e zero risco de OOM. E achou um **bug no desenho** "arquivo-entra/arquivo-sai": substituir o vocal direto faria `analyze()`/`estimate_key()` rodarem sobre a acapella (madmom/Essentia degradam muito em vocal isolado, pior em funk declamado).

**Recomendação final calibrada.**
1. **Nada muda no caminho crítico.** Todos os estímulos do painel (baseline E proposto) usam htdemucs — regra de higiene experimental explícita no protocolo.
2. Se sobrar folga pós-congelamento do experimento: separar as 2–4 faixas da demo no **MVSEP.com ou UVR GUI** (não audio-separator local) e injetar via parâmetro opcional **`vocal_stem_path` em `make_mashup`** que substitui apenas `vocal_only` no passo de síntese, mantendo análise e tom sobre o mix completo de A (~1h de código + 1 teste).

---

### 3.2 Análise rítmica/estrutural — MANTER (allin1) + congelar artefato

**Estado atual.** allin1 entrega beat+downbeat+BPM+seções **rotuladas** (insumo direto do filtro `groove_labels` da H1) na stack legada torch 2.0.1+cu117+NATTEN 0.14.6 compilado do source. Validado e2e em 2026-06-12, 107 testes verdes. Fallback madmom + cascata níveis 0–4 em `alignment.py` já implementado.

**Análise.** Nenhuma alternativa entrega o pacote completo: beat_this (ISMIR 2024) não rotula estrutura; MSAF/SSM dão clusters sem rótulos funcionais (quebraria H1); SongFormer (arXiv 2510.02797) rotula melhor (0.807 vs 0.740; HR.5F 0.807 vs 0.596) mas **não faz beat/downbeat/BPM**, usa MuQ+MusicFM com VRAM não validada na 2060, e custaria 3–5 dias sem mudar a validade de H1 (experimento relativo). O risco real é o **rebuild**, não o runtime: índice de wheels do NATTEN com TLS expirado (compilar do source é o único caminho), e a imagem base imprime "THIS IMAGE IS DEPRECATED and is scheduled for DELETION" a cada start.

**Desafio adversarial.** Sustentou a direção, refutou a execução em 3 pontos obrigatórios:
1. **NÃO publicar em registry público:** a imagem contém fonogramas comerciais completos (`/app/playlist_atv/musicas/*.mp3`, stems em `/app/demix/htdemucs/`) — o `.dockerignore` usa `*.mp3`/`*.wav` que na semântica Go só casa na **raiz**, e não lista `demix/`, `playlist_atv/`, `spec/`. Publicar exporia 4 alunos da UFG.
2. **`docker save` não captura volumes:** os pesos do allin1 (HF `taejunkim/allinone`, mantenedor único — mesma classe de risco do índice da shi-labs) e do Demucs (`dl.fbaipublicfiles.com`) baixam em runtime para `/root/.cache`; o volume atual do compose tem só 80MB de Demucs e **zero** pesos do allin1. Congelar a imagem sem os pesos mantém intacto o modo de falha que motivou o congelamento.
3. Custo honesto: **~1 dia**, não 0,5.

**Recomendação final calibrada.**
1. Corrigir `.dockerignore` (`**/*.mp3`, `**/*.wav`, `**/*.flac`, `demix`, `playlist_atv`, `spec`) → rebuild incremental (só a camada `COPY . .`, ~662MB; cache do NATTEN preservado).
2. Adicionar **warm-up de pesos no Dockerfile**: `snapshot_download('taejunkim/allinone')` + download do htdemucs, para os pesos ficarem **dentro** da imagem congelada.
3. `docker run --rm blend-ai:torch20 pip freeze > requirements.lock.txt` commitado + fixar base por digest (`FROM pytorch/pytorch@sha256:...`).
4. `docker save` → **.tar em canal privado da equipe** (Drive UFG/HD externo). Registry público só depois de auditar o conteúdo, se um dia fizer sentido.
5. Citar SongFormer no relatório como estado-da-arte/trabalho futuro. Refinamento opcional (não-bug): `vocal_fit` médio ponderado por duração em `_fundir_adjacentes` (a fusão de adjacentes é comportamento correto — o README oficial do allin1 mostra segmentos consecutivos de mesmo rótulo).

---

### 3.3 Tom e Síntese — AJUSTAR

**Estado atual.** `synthesis.py:21–24` encadeia `pyrb.time_stretch` + `pyrb.pitch_shift` = **duas resínteses** independentes, dobrando artefatos no vocal. `rubberband --version` na imagem = **1.8.2** (engine 2018, sem R3; tem `-F/--formant`, hoje não usado). Tom: Essentia EDMA com divergência já observada vs Rekordbox numa faixa real; `pipeline.py:93–94` estima tom com `except: pass` — erro silencioso injeta até ±6 st de transposição desnecessária e contamina H2 (score usa distância Camelot).

**Análise.** Verificado no fonte do pyrubberband 0.4.0 instalado: rbargs com valor vazio vira flag pura (`-F`, `--fine` passáveis sem patch). R3 (Rubber Band ≥3.0) é documentado pelo projeto como "almost always better than R2... especially vocals and soft onsets" — exatamente o material julgado pelo painel. madmom `CNNKeyRecognitionProcessor` já instalado na imagem (zero dependência nova), ~71–73,5% weighted no GiantSteps vs ~67–70 dos perfis Essentia.

**Desafio adversarial.** Sustentou com 4 correções:
1. **Bug de falha silenciosa na one-liner proposta:** `pyrb.time_stretch` tem `if rate == 1.0: return y` **antes** de processar rbargs — com ratio 1.0, `--pitch` e `-F` seriam descartados sem erro, contaminando o experimento. Implementar com **dois branches**: stretch+pitch → `time_stretch` com `rbargs={'--pitch': str(st), '-F': ''}`; só-pitch (|ratio−1|≤1e-4) → `pitch_shift` com `rbargs={'-F': ''}` + teste de regressão.
2. Build do RB 3.3 em **layers novas ao final do Dockerfile** — nunca tocar a linha apt do topo (invalidaria o cache da compilação do NATTEN, 10–20 min sensível à RAM do WSL). Timebox 1 dia; plano B = `-F` + passada única no 1.8.2 (já entrega ~80% do ganho).
3. Modelo shipped do madmom é o genre-agnostic (ISMIR 2018), não o EDM-specialized de 74,3% — em 11 faixas, 5 pontos ≈ meia faixa. Critério: concordância com Rekordbox; empate → manter Essentia.
4. `make_mashup` não tem hook de tom: adicionar **`key_override`** opcional (~1h).

**Recomendação final calibrada.** Ordem de execução: (1) passada única + `-F` com branches + teste (0,5 dia) e (2) `key_override` + **Rekordbox como silver standard nas faixas do experimento** (elimina o confound de H2 a custo ~zero) — primeiro; (3) calibração de tom nas 11 faixas (edma/bgate/braw × madmom CNN, mix completo e sem bateria) — 0,5 dia; (4) RB 3.3/R3 compilado em layer final — timeboxed, por último. Descartados pelos motivos certos: pylibrb (render é offline), librosa phase-vocoder (pior em vocal), stretch neural (não cabe em 6GB nem no prazo).

---

### 3.4 Infra/Ambiente — AJUSTAR

**Estado atual.** **Não existe `.wslconfig`** na máquina → VM WSL no default 8GB RAM/4GB swap — exatamente o teto documentado no próprio repo como causa de dois OOMs (Dockerfile linha 41; `separation.py:7–9`). `docker system df`: 45,5GB de imagens (torch26==latest, 14,1GB duplicados) + 21,2GB de build cache; 54GB livres em C:. NATTEN compilado só para sm_75 sem +PTX; madmom de git HEAD; `requirements.txt` sem pins.

**Análise.** `.wslconfig` com `memory=10GB`, `swap=16GB`, `sparseVhd=true` ataca a causa documentada dos crashes (evitar `autoMemoryReclaim=gradual` — bug conhecido com Docker, WSL #11066; usar `dropcache` ou omitir). O lote do P4 (11 faixas → ~1h de GPU com cache por faixa; 20–40 mashups em CPU; ~10GB de saída) cabe no hardware **após** o prune. Consolidar em torch 2.6 + all-in-one-fix fica como plano B documentado — migrar o componente mais frágil a 2,5 semanas do deadline viola a regra de ouro.

**Desafio adversarial.** Sustentou com 4 correções:
1. **Bug factual:** `TORCH_CUDA_ARCH_LIST="7.5;8.6;8.9+PTX"` **quebra o build** — nvcc 11.7 não suporta compute_89. Usar **`"7.5;8.6+PTX"`** (RTX 40xx roda via JIT do PTX).
2. **Ordem obrigatória:** `pip freeze` → `docker save` → **só então** `docker builder prune -a` — o prune destrói a única camada de compilação do NATTEN; rebuild pós-prune com requirements sem pin é loteria.
3. `docker save` **não** cobre GPUs não-Turing (cubin sm_75-only viaja dentro da imagem). Versão 80%-do-ganho: ARG no Dockerfile (5 min), distribuir a imagem sm_75 como está, e só rebuildar multi-arch **se** o inventário de GPUs dos colegas (uma mensagem no grupo) revelar NVIDIA não-Turing — o lote e a demo rodam na máquina do Pedro; as frentes dos colegas são CPU-only.
4. Prune: remover apenas `blend-ai:torch26`/`latest` (mesmo ID) + danglings; imagens de outros projetos (~3GB) só com confirmação do Pedro. `memory=10GB` deixa 6GB pro Windows — fechar navegador/IDE durante o lote, ou recuar para 9GB.

**Recomendação final calibrada.** Executar o pacote na ordem travada acima (~1,5 dia, nada toca código nem imagem validada). Lote do P4 via `docker compose run` CLI sequencial com cache de análise por faixa — **nunca via Streamlit/SPA**.

---

### 3.5 Frontend — TROCAR (Streamlit → FastAPI + Vite/React)

**Estado atual.** O adversarial corrigiu a premissa central: **não é greenfield**. `api/server.py` (191 linhas, untracked) está completo — `POST /api/mashups` (202+job_id), `GET /api/jobs/{id}` com progresso por etapa via hook `on_stage` já integrado em `pipeline.py` (diff aditivo não commitado), `GET /api/jobs/{id}/audio.wav`, `threading.Lock` serializando a GPU, StaticFiles servindo `web/dist`. `web/src/` tem 5 componentes React + cliente de API (Vite+React19+TS+Tailwind4; Node 24 no host). `app/app.py` (Streamlit) intacto como fallback.

**Análise.** Streamlit não realiza o mockup (`designs/02-automashup.html`): componentes vivem em iframes sandboxed sem layout livre — confirmado na doc oficial. Next.js corretamente descartado (sem SEO, sem páginas públicas, runtime Node = RAM extra numa máquina onde o daemon já caiu). Consenso 2025/2026: Vite SPA para ferramenta local. Trabalho restante real: ~1,5–2,5 dias (App/main.tsx, `npm build`, e2e no container).

**Desafio adversarial.** Sustentou o "trocar" com 6 calibrações — as decisivas:
1. **Sem multi-stage Docker pré-deadline:** o volume `./:/app` do compose já entrega `web/dist` buildado no host para dentro do container; única mudança é o `command` (streamlit→uvicorn). Rebuild da torch20 (NATTEN) é o risco de calendário a evitar.
2. A claim "porta 1:1" é falsa no detalhe: o mockup é CSS custom com Inter; o `web/` real já é redesign (Unbounded/Instrument Sans/IBM Plex Mono). Aceitar o redesign; waveforms e anel SVG são polish pós-fluxo — **proibir caça a pixel-fidelity**.
3. **Gate duro no dia 2:** upload→job→player e2e, ou a demo cai no Streamlit.
4. **Commitar `api/` + `web/` + diff do pipeline após pytest verde no container torch20** — hoje tudo está fora do git (risco de perda).

**Recomendação final calibrada.** Terminar a SPA iniciada (manter 4 dias só como teto duro; estimativa ~2–2,5). API mínima de 3 endpoints, jobs em memória, polling ~2s — sem Celery/Redis/WebSocket. Nit aceito: `JOBS` em memória sem bound — ok para demo localhost.

---

### 3.6 Rigor científico (P4) — AJUSTAR

**Estado atual.** Framework (Likert às cegas + Wilcoxon pareado para H1, Spearman para H2) está **alinhado à literatura** (AutoMashUpper, TASLP 2014; ISMIR 2013/2015 usaram exatamente esse desenho). Mas: **confundidor fatal em H1** — em `pipeline.py` (linhas 109–114), `dur_na_base = plan.target_segment.end - plan.vocal_offset` faz o baseline (target = faixa inteira) sobrepor o vocal por quase toda a música enquanto o proposto cobre uma seção; e `_melhor_janela_vocal` escolhe **trechos vocais diferentes** por braço (argmax depende de `dur_s`). Os braços diferem em conteúdo vocal, duração e ganho — qualquer efeito no Wilcoxon poderia ser "quantidade de vocal", não "estrutura". Protocolo (`eval/protocolo-experimento.md`) ainda não existe; `align` roda sem `metricas_por_segmento` e o score sem energia.

**Desafio adversarial.** Sustentou o diagnóstico (verificável no código, fatal se não corrigido — o painel é não-repetível em 19 dias), mas refutou 3 pontos, **baixando o custo de ~4 para ~2,5–3 dias**:
1. **Não mexer no default de `make_mashup`** (caminho do e2e validado e da UI): implementar **`eval/gera_estimulos.py`** que chama separation/analyze/align/render diretamente, forçando `vocal_in`/`vocal_dur` **idênticos** nos dois braços, excertos de ~25–30s a partir da entrada do vocal, loudness normalizado (pyloudnorm). Zero toque no produto, 107 testes intactos.
2. **"Restrição de variância" em H2 é empiricamente falsa:** `eval/matriz_compatibilidade.py` executado nos dados reais mostra score 0.224–1.000 nos 66 pares (componente harmônico domina — tonalidades 1A/5A/6A×4/8A×2/10A/11A×2). Não gerar pares ruins novos: **selecionar N≥16 itens estratificados por quartil de score** e reusar as notas do braço proposto para o Spearman — um painel só.
3. Promover **A/B forced choice (teste de sinal)** de alternativa para **pergunta adicional obrigatória** no formulário — custo ~0, maior potência em N pequeno, análise de sensibilidade pré-registrada.

**Recomendação final calibrada.**
- **Congelar `eval/protocolo-experimento.md` antes de coletar:** musicalidade como desfecho primário (Holm nas 3 escalas), N≥16 itens disjuntos (coletar +5–8 faixas, ~0,5 dia) × 15–20 avaliadores, análise primária por item (mediana) e secundária por avaliador (nunca pooling — pseudoreplicação), rank-biserial + IC bootstrap do rho, exclusão pré-registrada de `nivel_fallback=4`, ordem aleatorizada, âncora de atenção.
- Implementar `energia_a/energia_b` global no score (RMS dBFS, ~10 linhas + teste); `metricas_por_segmento` opcional — se apertar, pré-registrar que o "proposto" testado é a variante determinística.
- Métricas objetivas reduzidas: **citar SDR publicado do Demucs** (não rodar museval/MUSDB18 na 2060 — dias de compute e risco de daemon); validar beat/tom só no dataset próprio vs Rekordbox + subset GiantSteps.
- **H3 rebaixada a análise exploratória explícita** (sem dataset de funk coletado, não é testável como hipótese confirmatória).

---

## 4. Plano de ação priorizado (2,5 semanas)

### Bloco A — Imediato (dias 1–3): blindar o que existe
| Ordem | Tarefa | Dono | Custo |
|---|---|---|---|
| A1 | `.wslconfig` (memory=10GB, swap=16GB, sparseVhd; **sem** autoMemoryReclaim=gradual) + restart + smoke test GPU | Pedro | 1h |
| A2 | `pip freeze` do container → `requirements.lock.txt` commitado; digest da base no `FROM`; pin do madmom; `TORCH_CUDA_ARCH_LIST` como ARG = `"7.5;8.6+PTX"` | P1 | 2h |
| A3 | Fix `.dockerignore` (`**/*.mp3`, `**/*.wav`, `**/*.flac`, `demix`, `playlist_atv`, `spec`) + warm-up de pesos (allin1 HF + htdemucs) no Dockerfile → rebuild incremental | P1 | 0,5 d |
| A4 | `docker save` → .tar em **Drive UFG/HD privado** (nunca registry público) + smoke test do load | Pedro | horas (não-assistido) |
| A5 | **Só depois de A4:** `docker builder prune -a` + remover `blend-ai:torch26`/`latest`; outras imagens só com OK do Pedro | Pedro | 0,5h |
| A6 | `synthesis.py`: passada única com branches (anti early-return `rate==1.0`) + `-F` + teste de regressão | P2 | 0,5 d |
| A7 | `key_override` em `make_mashup` (~1h) + decisão: Rekordbox como tom nas faixas do experimento | P2 | 2h |
| A8 | Inventário de GPUs dos colegas (mensagem no grupo) — rebuild multi-arch só se houver NVIDIA não-Turing | todos | 5 min |

### Bloco B — Experimento (dias 3–10): o caminho crítico da nota
| Ordem | Tarefa | Dono | Custo |
|---|---|---|---|
| B1 | `eval/gera_estimulos.py` — vocal_in/vocal_dur idênticos nos 2 braços, excertos ~30s, pyloudnorm; htdemucs em **todos** os estímulos | P2 | 0,5–1 d |
| B2 | `eval/protocolo-experimento.md` congelado (N≥16 itens estratificados por quartil de score, 15–20 avaliadores, desfecho primário, Holm, por-item + por-avaliador, A/B forced choice adicional, exclusão fallback=4) + formulário | P4 | 1–1,5 d |
| B3 | Coleta de +5–8 faixas tech house (BPM 1–3 de diferença) | P1/P4 | 0,5 d |
| B4 | `energia_a/energia_b` no score (RMS dBFS) + teste | P2 | 2h |
| B5 | Calibração de tom: 11 faixas, edma/bgate/braw × madmom CNN vs Rekordbox (mir_eval); empate → manter Essentia | P1 | 0,5 d |
| B6 | Scripts de estatística (Wilcoxon + rank-biserial, sinal, Spearman + IC bootstrap) com testes | P4 | 1 d |
| B7 | Recrutamento do painel em paralelo desde já (risco de calendário, não de dev) | P4 | contínuo |

### Bloco C — Produto (dias 3–7, paralelo): SPA
| Ordem | Tarefa | Dono | Custo |
|---|---|---|---|
| C1 | Terminar SPA (App/main.tsx, build, e2e no container via volume `./:/app`; command do compose → uvicorn) | P3 | 1,5–2,5 d (teto 4) |
| C2 | **Gate dia 2:** upload→job→player e2e, ou demo cai no Streamlit (intacto) | P3 | — |
| C3 | Commitar `api/` + `web/` + diff do `pipeline.py` **após** pytest verde no container torch20 | P3 | 2h |

### Bloco D — Semana final: coleta, análise, polish condicional
- Gerar estímulos + rodar painel + estatística + relatório (citar SongFormer e BS-RoFormer como estado-da-arte/trabalho futuro; declarar limitações).
- **Condicional a folga:** RB 3.3/R3 em layer final do Dockerfile (timebox 1 dia; plano B já entregue em A6); vocal BS-RoFormer via MVSEP.com/UVR **só para a demo**, via `vocal_stem_path`.

### O que explicitamente NÃO fazer
- **Não** trocar htdemucs por BS-RoFormer/SCNet/MDX23C no pipeline; **não** voltar ao `htdemucs_ft`.
- **Não** migrar allin1 → SongFormer nem → all-in-one-fix (fica documentado como plano B).
- **Não** publicar a imagem em registry público (áudio comercial dentro dela).
- **Não** fazer `docker builder prune` antes de freeze+save.
- **Não** tocar a linha `apt-get` do topo do Dockerfile (cache do NATTEN).
- **Não** usar `TORCH_CUDA_ARCH_LIST` com 8.9 (nvcc 11.7 não compila).
- **Não** rodar museval/MUSDB18 completo na 2060.
- **Não** Next.js, **não** Celery/Redis/WebSocket, **não** multi-stage Docker pré-deadline, **não** caça a pixel-fidelity (waveforms/anel SVG = polish).
- **Não** MUSHRA/CLMM (overkill); **não** pooling de notas num único Wilcoxon (pseudoreplicação).
- **Não** rodar o lote do P4 via UI — só CLI sequencial com cache.
- **Não** misturar separadores entre estímulos do painel.

---

## 5. Riscos aceitos conscientemente

| Risco | Por que é aceito | Mitigação residual |
|---|---|---|
| Bleed no vocal (htdemucs ~8,2 dB SDR) pode rebaixar notas de "ausência de artefatos" | Constante entre braços — não ameaça validade de H1/H2; teto de polimento, não viés | `_melhor_janela_vocal` já mitiga; MVSEP só na demo |
| Lock-in na stack legada torch 2.0.1+cu117 (base "scheduled for DELETION", NATTEN sem wheels) | Já pago e validado; nenhuma alternativa entrega beat+downbeat+BPM+rótulos num pacote | .tar privado + pesos baked + lockfile (Bloco A) |
| NATTEN sm_75-only — colegas com GPU não-Turing não rodam a imagem | Lote e demo rodam na máquina do Pedro; frentes dos colegas são CPU-only (bus-factor, não bloqueador) | ARG multi-arch pronto; rebuild condicional ao inventário (A8) |
| Tom Essentia pode divergir no **produto** (fora do experimento) | No experimento usa-se Rekordbox (silver standard); calibração B5 quantifica o erro | Ensemble madmom como sinal de confiança, se vencer |
| H3 sem dataset de funk coletado | Rebaixada a exploratória declarada — evita promessa furada no relatório | Demo funk×house como ilustração qualitativa |
| Itens do painel compartilham faixas (não independentes) | Inevitável com 16–19 faixas; padrão na literatura de mashup | Declarar como limitação no relatório |
| `JOBS` em memória sem bound na API; fila segura thread | Demo localhost, single-user | — |
| Recrutamento de 15–20 avaliadores na semana final | Risco de calendário, não de desenvolvimento | Iniciar recrutamento já (B7); análise por item funciona com menos avaliadores |
| `metricas_por_segmento` (vocal_fit_rel) pode não entrar | O "proposto" testado é a variante determinística — pré-registrado no protocolo | Implementar se sobrar tempo do P2 |
| RB 1.8.2 (sem R3) se a build do 3.3 estourar o timebox | Passada única + `-F` já elimina a dupla resíntese (maior parte do ganho) | Item condicional do Bloco D |

---

**Veredito final:** stack validada — manter o motor, congelar o ambiente, corrigir o desenho experimental ANTES de gastar o painel, terminar a SPA já iniciada. O trabalho das próximas 2,5 semanas é de **execução e blindagem**, não de troca de tecnologia.