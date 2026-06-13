# Experimento subjetivo — painel cego (P4)

> **Protocolo CONGELADO em 2026-06-12.** Definido **antes** da coleta (exigência de
> rigor). Mudanças após a 1ª resposta coletada invalidam o experimento — não editar.

## Problema / motivação

Validar empiricamente as duas hipóteses centrais do Blend AI com ouvintes reais,
às cegas, comparando o método **proposto** (alinhamento estrutura-aware) com o
**baseline** ingênuo.

## Hipóteses e como validar

- **H1 (principal):** mashups com alinhamento estrutura-aware são percebidos como
  **mais musicais** que os com alinhamento ingênuo.
  → **Wilcoxon pareado** (proposto vs baseline) sobre a média por par no eixo
  *musicalidade* (primário). Eixos secundários: qualidade geral, ausência de
  artefatos. Tamanho de efeito: **rank-biserial pareado**. Confirmação:
  **A/B de escolha forçada** por par (teste binomial).
- **H2:** o score de compatibilidade prevê a qualidade percebida.
  → **Spearman** (score × nota média por par), IC por bootstrap, reportando `n`
  e a limitação de potência.
- **H3 (exploratória):** vocais declamados toleram maior distância harmônica.
  → nos pares de `camelot_dist` alto, inspeção descritiva (a transposição ajudou?
  o eletrofunk declamado tolerou o salto?). Sem teste confirmatório (N pequeno).

## Desenho

- **Within-subjects, pareado.** Cada par (A=vocal, B=base) gera **dois** estímulos:
  `baseline` e `proposto`. Pela invariante travada em `pipeline._recorte_vocal`
  (teste `test_h1_invariante_...`), os dois braços usam **o mesmo trecho vocal,
  mesmo stretch e mesmo pitch** — diferem **só na colocação** sobre B. Isso isola
  a manipulação de H1 (escolha de seção + ancoragem) de confundidores.
- **Cego:** cada estímulo recebe um ID aleatório; o gabarito condição↔ID fica num
  CSV separado. A ordem de apresentação é randomizada por avaliador (seed fixo,
  registrado).

## Estímulos

- **Domínio:** tech house × tech house, **|ΔBPM| ≤ 3** (controla o tempo, isola a
  estrutura). Fonte: 11 faixas em `data/raw/bases/` (tom/BPM em
  `data/rekordbox/groundtruth.csv`). O caso funk × house (eletrofunk) fica como
  **demo/robustez (H3)**, fora do painel principal (sem `.mp3` coletado ainda).
- **N ≈ 12 pares**, **estratificados por quartil do score de compatibilidade**
  (garante espalhamento de score para H2 ter variação no eixo x).
- **Excerto ~30 s** centrado na entrada do vocal de cada condição (lead-in de 1
  compasso), **loudness normalizado** (RMS alvo comum) para o volume não enviesar.

## Painel

- **≥ 8 avaliadores** (mistura de DJs/produtores e ouvintes leigos).
- Por estímulo, **Likert 1–5** em 3 eixos: qualidade geral, **musicalidade**
  (primário p/ H1), ausência de artefatos.
- Por par, **A/B de escolha forçada**: "qual dos dois encaixa melhor?".

## Estatística (o que reportar)

- **H1:** Wilcoxon pareado (musicalidade) → `W`, `p`, `n_pares`, **rank-biserial**;
  idem para qualidade e artefatos como secundários. A/B → proporção que prefere
  proposto + `p` binomial.
- **H2:** Spearman `rho`, `p`, `n`, **IC95% bootstrap**. Reportar a limitação de
  potência com N pequeno (não concluir nulo por p>0.05 sozinho).
- **H3:** tabela descritiva dos pares de alto `camelot_dist`.

## Interface com outros módulos

- Entrada: `data/rekordbox/groundtruth.csv` + `data/raw/bases/*.mp3`.
- Motor: `blend.pipeline.make_mashup(a, b, mode)` (já com a invariante de H1) e
  `blend.compatibility.compatibility_score` (tipos em `src/blend/types.py`).
- Saída: `data/experimento/estimulos/*.wav` (cegos), `data/experimento/gabarito.csv`,
  `data/experimento/ordem_<avaliador>.csv`, e respostas em
  `data/experimento/respostas.csv` (preenchidas pelo painel).

## Critério de pronto

- `eval/gera_estimulos.py` roda e produz 2N excertos + gabarito + ordens (cego).
- `eval/analise.py` roda sobre o gabarito + respostas e cospe H1 (Wilcoxon +
  efeito + A/B), H2 (Spearman + IC) e H3 (descritivo).
- Helpers puros (seleção de pares, casamento de arquivo, excerto, normalização,
  estatística) cobertos por testes em `tests/test_eval.py`.
