# Resultado — Matriz de compatibilidade (H2)

Saída de `python eval/matriz_compatibilidade.py` sobre o ground truth do Rekordbox
(`data/rekordbox/groundtruth.csv`): **12 faixas, 66 pares**.

Score sem o componente de energia/áudio (esse é injetado pelo pipeline em produção,
a partir dos stems): aqui `score = harmônico (Camelot) + tempo (razão de BPM)`, com os
pesos renormalizados. Serve como demonstração do score de compatibilidade (H2) sobre
**dados reais**, sem precisar de GPU/Docker.

Rótulo das faixas: `Título (Camelot/BPM)`.

## TOP 10 pares mais compatíveis

| score | par | harm · tempo |
|---|---|---|
| 1.000 | Swag (6A/130) + Get Naughty (6A/130) | 1.00 · 1.00 |
| 1.000 | Swag (6A/130) + Lost Eletrofunk (6A/130) | 1.00 · 1.00 |
| 1.000 | All We Got (11A/128) + Hands Up (11A/128) | 1.00 · 1.00 |
| 1.000 | Work Your Body (8A/132) + Bootay (8A/132) | 1.00 · 1.00 |
| 1.000 | Get Naughty (6A/130) + Lost Eletrofunk (6A/130) | 1.00 · 1.00 |
| 0.961 | Stop Talking (6A/131) + Swag (6A/130) | 1.00 · 0.90 |
| 0.961 | Stop Talking (6A/131) + Get Naughty (6A/130) | 1.00 · 0.90 |
| 0.961 | Stop Talking (6A/131) + Lost Eletrofunk (6A/130) | 1.00 · 0.90 |
| 0.833 | Swag (6A/130) + Pokasamba (5A/128) | 0.85 · 0.81 |
| 0.833 | Get Naughty (6A/130) + Pokasamba (5A/128) | 0.85 · 0.81 |

## 10 pares menos compatíveis

| score | par | harm · tempo |
|---|---|---|
| 0.389 | Trust Me (10A/126) + Pokasamba (5A/128) | 0.10 · 0.80 |
| 0.366 | Trust Me (10A/126) + Swag (6A/130) | 0.20 · 0.60 |
| 0.366 | Trust Me (10A/126) + Get Naughty (6A/130) | 0.20 · 0.60 |
| 0.366 | Trust Me (10A/126) + Lost Eletrofunk (6A/130) | 0.20 · 0.60 |
| 0.353 | Stop Talking (6A/131) + All We Got (11A/128) | 0.10 · 0.71 |
| 0.353 | Stop Talking (6A/131) + Hands Up (11A/128) | 0.10 · 0.71 |
| 0.347 | Zero Tolerance (6A/125) + All We Got (11A/128) | 0.10 · 0.70 |
| 0.347 | Zero Tolerance (6A/125) + Hands Up (11A/128) | 0.10 · 0.70 |
| 0.333 | Stop Talking (6A/131) + Trust Me (10A/126) | 0.20 · 0.52 |
| 0.224 | Zero Tolerance (6A/125) + Bad Wolf (1A/131) | 0.10 · 0.40 |

## Melhores bases para o VOCAL do funk — Lost Eletrofunk (6A/130)

Ranking ligado ao caso-guia do produto (vocal de funk sobre base de house):

| score | base | harm · tempo |
|---|---|---|
| 1.000 | Swag (6A/130) | 1.00 · 1.00 |
| 1.000 | Get Naughty (6A/130) | 1.00 · 1.00 |
| 0.960 | Stop Talking (6A/131) | 1.00 · 0.90 |
| 0.833 | Pokasamba (5A/128) | 0.85 · 0.81 |
| 0.802 | Zero Tolerance (6A/125) | 1.00 · 0.52 |

## Leitura

- **Mesmo Camelot + mesmo BPM → score máximo (1.000):** o score reconhece os pares
  triviais de casar (ex.: `Swag` + `Get Naughty`, ambos 6A/130). Coerente com a intuição de DJ.
- **Penalização harmônica domina o fundo da lista:** o pior par (`Zero Tolerance` 6A
  + `Bad Wolf` 1A = 0.224) soma salto de Camelot grande **e** BPM distante — o score
  separa bem os extremos, o que é o pré-requisito para H2 (score prevê qualidade percebida).
- **Conexão com o experimento:** este ranking é o que alimenta a seleção estratificada de
  pares do experimento subjetivo (pares de alta e baixa compatibilidade), de forma que a
  correlação de Spearman (score × nota do painel) tenha espalhamento suficiente.
- **Ressalva:** sem o termo de energia/estrutura (que vem dos stems no pipeline real), então
  os números aqui são a componente harmônico+tempo do score, não o score final de produção.
