# Blend AI — Trabalho Final de PAV (Processamento de Áudio e Voz) · UFG

## Projeto: **Blend AI** ✅

Entre os 4 conceitos que estavam em brainstorm (Vocal Studio, AutoMashup, Sample Forge, Smart Crate),
**a equipe escolheu o conceito de mashup automático** (codinome de brainstorm: "AutoMashup") e o
batizou de **Blend AI**. Este é o trabalho final oficial. Os outros três conceitos permanecem em
`designs/` apenas como referência histórica do brainstorm — não são mais candidatos.

**Blend AI** = geração automática de mashups guiada por compatibilidade e estrutura musical.
Pega o vocal de uma faixa e o encaixa sobre o instrumental de outra, casando tempo, tom e — o
diferencial — a **estrutura musical**.

**Caso de uso-guia (demo):** *"tenho um funk com vocal interessante e um tech house; quero o vocal
do funk sobre o tech house."* Vocal de funk × instrumental de house/tech house — um estilo próprio
nos sets brasileiros.

> Proposta detalhada (fonte de verdade do escopo): [`designs/proposta-automashup.html`](designs/proposta-automashup.html)
> Mockup da interface: [`designs/02-automashup.html`](designs/02-automashup.html)
> (Os arquivos em `designs/` mantêm o codinome "AutoMashup" do brainstorm; o produto agora se chama **Blend AI**.)

## Contexto e restrições

- **Disciplina:** PAV (Processamento de Áudio e Voz), UFG. Trabalho final.
- **Tipo:** produto (aplicação real) **+** avaliação científica (hipótese clara + métricas).
- **Equipe:** 4 pessoas.
- **Prazo:** ~4 semanas. Deadline por volta de **2026-07-01**.
- **Infra:** 1 GPU de consumo (favorece inferência/fine-tuning, não treino do zero de modelos generativos grandes).
- **Artigo:** sem intenção de submeter (abrimos mão do bônus de 10 pts).
- **Exigências do enunciado** (`instrucoes.md`): nível de desafio real (projetos triviais como
  classificação em dataset trivial são rejeitados) **e** rigor científico (planejamento, execução, análise).

O **cerne de PAV é o motor de áudio** (separação + análise + alinhamento + síntese). A camada de
**prompt em linguagem natural via LLM** é casca fina / diferencial de demo — **opcional**, não deve
virar trabalho de NLP nem entrar no caminho crítico.

## Hipóteses (o que valida o rigor científico)

- **H1 (principal):** inserir o vocal com **detecção de estrutura musical** (escolher a seção certa do
  instrumental + sincronizar as frases vocais) produz mashups avaliados como mais musicais do que um
  **alinhamento ingênuo** (só BPM + tom + primeiro downbeat). → testada por experimento subjetivo às
  cegas (Wilcoxon).
- **H2:** um **score de compatibilidade** (distância harmônica Camelot + razão de BPM + similaridade de
  energia/estrutura) prevê a qualidade percebida. → validada por correlação de Spearman.
- **H3:** vocais declamados (típicos do funk) toleram maior distância harmônica, dispensando transposição
  em alguns casos. → análise dos casos com salto harmônico elevado.

A contribuição central do trabalho está no **alinhamento estrutura-aware** e na **previsão de
compatibilidade** — não em reinventar separação/beatmatch/transposição, que são base já resolvida na literatura.

## Pipeline técnico

```
Faixa A (vocal) + Faixa B (base)
  → Separação de fontes ............. Demucs v4 (htdemucs)
  → Beat & downbeat ................. beat-this / madmom
  → Tom → Camelot ................... Essentia / librosa
  → Seções musicais ................. allin1 / MSAF
  → [★] Score de compatibilidade .... Camelot dist. + BPM ratio + energia
  → [★] Alinhamento estrutura-aware . escolha de seção + sincronização de frases
  → Síntese ......................... time-stretch + pitch-shift (Rubber Band)
  → Saída ........................... .wav mixado + 4 stems
```

`[★]` = contribuição central (onde o método proposto se diferencia do baseline).

Onde há "/" eram alternativas em aberto; ver decisões travadas abaixo.

## Stack — decisões travadas (2026-06-05)

- **Separação:** Demucs v4 `htdemucs_ft`.
- **Beat + downbeat + estrutura:** **`allin1`** — um pacote só cobre as três etapas e entrega segmentação **com rótulos** (intro/verso/refrão/drop), insumo direto do alinhamento estrutura-aware (H1). Reaproveita o Demucs por dentro.
- **Síntese:** Rubber Band via `pyrubberband` (time-stretch + pitch-shift).
- **Ambiente:** **Docker** com imagem base CUDA, única para os 4 — resolve a build do NATTEN (dependência do `allin1`) e garante reprodutibilidade. GPU via `nvidia-container-toolkit` (Docker Desktop + backend WSL2 no Windows).
- **Tom → Camelot:** detecção automática com **Essentia (perfil EDMA)** no produto; **tom do Rekordbox usado como ground truth de validação (silver standard)** no domínio-alvo (eletrofunk + house). Atalho permitido nas primeiras semanas: usar o tom do Rekordbox como _input_ até a detecção automática ficar pronta. Extração via `rekordbox.xml` (atributo `Tonality`) ou `pyrekordbox`.
- **Interface (P3):** **Streamlit** para o MVP — sobe em horas e mantém o foco no motor de áudio (o cerne de PAV). Os mockups HTML em `designs/` ficam como norte visual / trabalho futuro.

## Escopo

**MVP (entregar em 4 semanas):**
- Separação + análise completa (BPM, Camelot, downbeats, estrutura de seções).
- Score de compatibilidade entre faixas.
- Alinhamento estrutura-aware (casar BPM/tom + downbeats + inserir vocal numa seção de groove detectada).
- Síntese com Rubber Band (time-stretch + pitch-shift de qualidade).
- Interface estruturada: seleção de A e B, modo "vocal de A sobre B", preview, export.
- Experimento baseline vs. proposto + demo ao vivo funk × tech.

**Visão (trabalhos futuros, fora do MVP):** prompt em linguagem natural via LLM; corte/seleção de
frases vocais mais sofisticado; transição/crossfade inteligente; sidechain/mix/master automáticos.

**Visão de produto (longo prazo):** o mashup automático é a **1ª funcionalidade do Blend AI**, pensado
como uma **suíte extensível** para DJs/produtores, reaproveitando o mesmo motor de análise
(separação + BPM/tom/estrutura) para, depois, organização automática de biblioteca (a antiga ideia
"Smart Crate"), setlists, extração de stems e criação de samples.

## Divisão da equipe

- **P1 — Separação & Análise:** Demucs, beat/downbeat, tom→Camelot, allin1. Entrega features estruturadas.
- **P2 — Motor de Mashup (cérebro):** score de compatibilidade, alinhamento, Rubber Band, mixagem final.
- **P3 — Produto & Interface:** UI no padrão dos mockups, upload/preview/export, integração; LLM (se entrar).
- **P4 — Avaliação & Dados:** dataset, protocolo experimental, coleta do painel, estatística (Wilcoxon/Spearman), docs.

Integração entre módulos e decisões de arquitetura: em conjunto.

## Datasets

- **Demonstração / experimento MVP:** **tech house × tech house** — vocal de uma faixa sobre a base de outra, com **BPM próximo (1–3 de diferença)**, usando as **11 faixas já coletadas** em `data/raw/bases/`. Controla a variável tempo e isola o efeito da estrutura para testar H1 de forma limpa. O caso-guia do produto **funk × house** (lado A = eletrofunk BR, a coletar) fica como **demo/visão e teste de robustez** (gap grande de BPM — ver `specs/alinhamento-estrutura-aware.md`). Faixas comerciais (selos reais — Solid Grooves, Diynamic, EMPIRE…) → ok para uso educacional interno; ressalva ao publicar/distribuir.
- **Ground truth (validar a análise):** MUSDB18 (separação — SDR), GiantSteps (tom/tempo),
  Harmonix Set (downbeats/estrutura), GTZAN (gênero/tempo).
- **Subjetivo:** painel de DJs e ouvintes, avaliação às cegas, escala Likert 1–5.

## Avaliação científica

- **Objetivas:** SI-SDR/SDR (MUSDB18), F-measure de beat/downbeat (Harmonix), acurácia/MIREX de tom
  (GiantSteps), erro de downbeat (ms) + % beats alinhados.
- **Subjetivas:** qualidade geral, musicalidade percebida, ausência de artefatos (Likert 1–5).
- **Experimento:** N mashups por baseline (alinhamento ingênuo) vs. método proposto (estrutura-aware),
  avaliados às cegas. Wilcoxon testa H1; Spearman (score × notas) testa H2.

## Estado atual do repositório

- Fase: **estrutura criada — pronto para a Semana 1 (implementação).**
- Nome do produto: **Blend AI** (definido 2026-06-05). Stack travado (ver acima).
- `instrucoes.md` — enunciado oficial do trabalho.
- `designs/` — mockups dos 4 conceitos do brainstorm + capa + `proposta-automashup.html` (escopo/hipóteses/pipeline/equipe/cronograma — fonte de verdade do escopo).
- `src/blend/`, `app/`, `eval/`, `tests/`, `specs/`, `.claude/agents/` — esqueleto de código + agentes (stubs com `NotImplementedError`).
- **Ambiente Docker (allin1 validado 2026-06-12):** imagem principal **`blend-ai:torch20`** (`torch 2.0.1 + cuda11.7 + NATTEN 0.14.6 compilado com FORCE_CUDA=1 + numpy<1.24 resolvido junto com o requirements`) — **allin1 rodando na RTX 2060 com seções rotuladas** (intro/chorus/verse/outro) → alinhamento proposto opera em `nivel_fallback=0`. Armadilhas documentadas no `Dockerfile` (FORCE_CUDA, MAX_JOBS=2, pin do numpy na mesma resolução do pip). Fallback sem allin1 (torch 2.6 + cuda12.6, GPU OK): `blend-ai:torch26` / `Dockerfile.torch26-fallback`. Separação usa `htdemucs` (modelo único): o `_ft` estoura os 16 GB de RAM da máquina.
- Próximos passos (Semana 1): validar Docker/GPU, implementar separação+análise (P1) nas 11 bases, montar dataset e baseline ingênuo.

## Convenções

- **Idioma:** PT-BR em toda a documentação, UI e comunicação.
- **Design:** tema claro/minimal, alta fidelidade (ver mockups em `designs/`).
- **Plataforma:** desenvolvimento em **Docker** (imagem CUDA Linux) rodando no Windows via Docker Desktop + WSL2. Não assumir libs de áudio instaladas no Windows nativo.

## Fluxo de desenvolvimento

Projetos grandes seguem um fluxo **spec-driven** reusando as skills do **superpowers** (sem skill orquestradora custom — calibrado para 4 semanas):

```
spec em specs/  →  brainstorming  →  writing-plans (com tasks)  →  implementação
   →  requesting-code-review  →  test gate (pytest)  →  verification-before-completion
```

- **Spec primeiro:** feature não-trivial começa por um doc curto em `specs/<nome>.md` (problema, hipótese se aplicável, escopo, interface entre módulos, critério de pronto). Ver `specs/README.md`.
- **Dispatch por módulo:** trabalho pesado vai para o agente especializado do módulo (ver Agentes do projeto). 4 pessoas ↔ 4 módulos ↔ 4 agentes, podendo rodar em paralelo.
- **Test gate (leve):** todo código com lógica testável (score de compatibilidade, conversão Camelot, alinhamento, BPM ratio, half/double-time) ganha teste em `tests/`. Rodar `pytest` antes de integrar. TDD recomendado nos pontos críticos.
- **Verificação antes de concluir:** nada de "feito" sem rodar. Para o motor de áudio, "rodar" inclui gerar um mashup ponta-a-ponta e **ouvir**.
- **Tudo em PT-BR:** specs, docs, comentários user-facing e UI.

## Agentes do projeto

`.claude/agents/` tem **4 agentes**, um por módulo da equipe, disparáveis via `subagent_type: <name>` (build mode — tools Read/Write/Edit/Bash/Glob/Grep):

| Agente | Módulo | Dono | Cobre |
|---|---|---|---|
| `blend-audio` | Separação & Análise | P1 | Demucs (stems), allin1 (beat/downbeat/estrutura), Essentia→Camelot, leitura do Rekordbox |
| `blend-mashup` | Motor de Mashup | P2 | score de compatibilidade, alinhamento estrutura-aware, síntese Rubber Band, mixagem |
| `blend-app` | Produto & Interface | P3 | Streamlit, upload/preview/export, integração dos módulos |
| `blend-eval` | Avaliação & Dados | P4 | dataset, métricas objetivas (SDR/F-measure/MIREX), experimento subjetivo, stats (Wilcoxon/Spearman) |

**Mapping task → agente** (por palavra-chave): separação/stem/demucs/beat/downbeat/estrutura/tom/camelot/rekordbox → `blend-audio`; score/compatibilidade/alinhamento/stretch/pitch/rubberband/mix → `blend-mashup`; streamlit/ui/upload/preview/export → `blend-app`; dataset/métrica/sdr/wilcoxon/spearman/experimento/avaliação → `blend-eval`. Ambíguo → `general-purpose`.

---

# superpowers

Use o plugin **superpowers** (https://github.com/obra/superpowers) como metodologia padrão de desenvolvimento. O plugin impõe um fluxo estruturado: brainstorming → aprovação de design → git worktree → planning → implementação com code review → conclusão, com ênfase em TDD, debugging sistemático e verificação antes de declarar sucesso.

**Skills do gstack podem ser usadas livremente quando o Pedro pedir explicitamente** (ex: `/design-shotgun`, `/design-review`, `/qa`, `/ship`, `/codex`). Não invocar gstack proativamente como padrão — só quando pedido.

Instalação (rodar no Claude Code uma vez):

```
/plugin install superpowers@claude-plugins-official
```

Skills disponíveis no plugin superpowers:

**Testing:**
- `test-driven-development` — ciclo RED-GREEN-REFACTOR

**Debugging:**
- `systematic-debugging` — análise de causa raiz em 4 fases
- `verification-before-completion`

**Collaboration:**
- `brainstorming`
- `writing-plans`
- `executing-plans`
- `dispatching-parallel-agents`
- `requesting-code-review`
- `receiving-code-review`
- `using-git-worktrees`
- `finishing-a-development-branch`
- `subagent-driven-development`

**Meta:**
- `writing-skills`
- `using-superpowers`
