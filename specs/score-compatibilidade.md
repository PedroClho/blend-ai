# Spec — Score de compatibilidade (H2)

> Módulo: P2 (`blend-mashup`) · Arquivo: `src/blend/compatibility.py` · Status: **refinada / FECHADA em 2026-06-07** (agente `blend-mashup`, lente prática de DJ)

## Problema / motivação

Dado duas faixas (A = vocal, B = base) e suas análises (`TrackAnalysis`), prever num **índice único `[0,1]`** quão bem elas combinam num mashup. Usos:
1. **Rankear/sugerir** pares (quais das N faixas combinam melhor com X).
2. **Sinalizar casos ruins** antes de gastar síntese (gap grande de BPM, salto harmônico).
3. **Testar H2** — é a 2ª contribuição do trabalho, ao lado do alinhamento estrutura-aware (H1).

## Hipótese (H2) e como validar

**H2:** o score prevê a qualidade percebida do mashup. → correlação de **Spearman** entre o score e as notas do painel (P4). A feature **entrega o score** (e o breakdown por componente); o P4 **calibra os pesos** e roda o Spearman. Por isso o score deve expor não só o número final, mas **os componentes** (pra correlacionar cada um separadamente).

## Escopo

**Entra:** `camelot_distance`, componente harmônico, componente de tempo (BPM com half/double-time), componente de energia/estrutura, combinação em `[0,1]` + breakdown.
**Não entra:** a coleta de notas e o Spearman (P4); a detecção de tom/BPM/estrutura (P1, vem pronto no `TrackAnalysis`).

## Componentes do score

A lente é a **prática de DJ**: o que faz duas faixas se encaixarem na pista é (1) **harmonia** (não soar "fora de tom"), (2) **tempo** (poder beatmatchar sem rasgar o áudio) e (3) **energia/vibe** (não colidir uma faixa densa com uma rarefeita). A ordem de tolerância do ouvido é a base de tudo abaixo: **o ouvido perdoa muito mais um deslize de energia do que um choque harmônico, e perdoa o harmônico mais do que um stretch agressivo de tempo** (que vira artefato audível). Daí os pesos do Q3.

1. **Harmônico (Camelot)** — `camelot_distance(a, b)` + mapeamento `comp_harmonico(a, b) -> [0,1]`. **[PURO]**
   - Roda Camelot: 12 números (1–12) num círculo, cada um com `A` (menor) e `B` (maior). Ex.: `8B` = C maior, `8A` = A menor (relativo).
   - Resolvido no **Q1** (curva de decaimento por tabela de movimentos da roda).
2. **Tempo (BPM)** — **[PURO]**. Escolher `f ∈ {0.5, 1, 2}` que minimiza o stretch (reusa `_escolher_bpm_ratio` do `alignment.py`); componente decai com `|stretch − 1|`; acima de `max_stretch_pct` → componente baixo. No domínio MVP (tech house × tech house, 1–3 BPM) este componente é quase sempre ~1. Resolvido no **Q3** (forma do decaimento).
3. **Energia / estrutura** — similaridade da **densidade/vibe** entre as faixas. **[depende de features de áudio — OPCIONAL]**. Segue o padrão do alinhamento: métricas **injetadas** pelo pipeline; sem elas o componente sai e os pesos se redistribuem (score = harmônico + tempo renormalizados), mantendo `compatibility_score` testável de forma pura. Resolvido no **Q2**.

## Interface (`src/blend/compatibility.py`)

```python
camelot_distance(a: str, b: str) -> int          # passos de incompatibilidade na roda (DECIDIDO: int)
comp_harmonico(a: str, b: str) -> float           # [0,1] via tabela do Q1
comp_tempo(bpm_a: float, bpm_b: float) -> float    # [0,1] via Q3
compatibility_score(
    a: TrackAnalysis, b: TrackAnalysis,
    metricas: dict | None = None,                  # energia injetada (OPCIONAL); ver Q2
    params: ParamsScore | None = None,
) -> ScoreCompat
```

**Decisão:** `camelot_distance` retorna `int` (passos de incompatibilidade — testável de forma crua e reusável), e o mapeamento `int → [0,1]` fica no `comp_harmonico` (tabela do Q1). Os dois ficam expostos: o P4 pode correlacionar tanto a distância crua quanto o componente.

`ScoreCompat` (dataclass nova em `types.py`):

```python
@dataclass
class ScoreCompat:
    total: float                 # [0,1], combinação ponderada
    harmonico: float             # [0,1]
    tempo: float                 # [0,1]
    energia: float | None        # [0,1] ou None quando 'metricas' ausente
    camelot_dist: int            # passos crus na roda (auditoria/Spearman)
    bpm_ratio: float             # fator de stretch escolhido (f∈{.5,1,2} aplicado)
    pesos: dict[str, float]      # pesos efetivos (já renormalizados) — auditoria P4
```

O P4 precisa do breakdown separado **e** dos pesos efetivos (que mudam quando `energia=None`) para o Spearman por componente e para auditar a renormalização.

## Parâmetros (`ParamsScore`, dataclass frozen — defaults a calibrar via Spearman — P4)

- `w_harmonico=0.50 / w_tempo=0.35 / w_energia=0.15` — pesos da combinação (ver **Q3**). Sem energia, renormaliza-se harmônico+tempo (≈ 0.588/0.412).
- `max_stretch_pct = 8` — consistente com a spec do alinhamento; acima disso `comp_tempo → 0`.
- `key_ausente_neutro = 0.5` — quando `key_camelot` é `None` num dos lados, o harmônico não pode afirmar nem negar: vale neutro (não penaliza nem premia). Determinístico.

## Decisões do refinamento (lente: prática de DJ) — Q1–Q4 FECHADAS

### Q1 — `camelot_distance` → `[0,1]` (curva harmônica)

**Por que tabela e não fórmula.** A roda Camelot não é uma métrica linear: o ouvido não trata "2 passos pela borda" igual a "1 passo de número + 1 de letra". A intuição de pista tem **classes discretas de movimento** (é assim que DJ pensa: "subir uma casa", "ir pro relativo", "energy boost"). Modelamos por **tabela de movimentos**, calculada de forma determinística a partir de `(Δnúmero mod 12, mesma_letra?)`.

`camelot_distance(a, b) -> int` = **número mínimo de passos** na roda, contando troca de número (±1 = 1 passo, pela menor direção no círculo de 12) **e** troca de letra (A↔B = 1 passo). É a distância crua para auditoria do P4; não codifica a "qualidade" — isso é o `comp_harmonico`.

`comp_harmonico(a, b) -> [0,1]` usa uma **tabela de qualidade por classe de movimento** (a tradução da prática de DJ), com `key_ausente_neutro=0.5` quando falta tom:

| Movimento (da roda Camelot) | Δnúmero (mod 12) | Letra | `comp_harmonico` | Leitura de pista |
|---|---|---|---|---|
| **Mesma chave** | 0 | igual | **1.00** | tom idêntico — encaixe perfeito |
| **Relativo** (maior↔menor) | 0 | troca | **0.90** | troca de cor sem brigar; clássico |
| **Vizinho** (±1, quinta/quarta) | ±1 | igual | **0.85** | o pilar do harmonic mixing |
| **Vizinho diagonal** | ±1 | troca | **0.55** | funciona com cuidado; some um pouco |
| **Energy boost / drop** (+2 / −2) | ±2 | igual | **0.55** | sobe/baixa energia mantendo afinidade |
| **±3 mesma letra** | ±3 | igual | **0.35** | já soa "puxado", mas usável em build |
| **Salto médio** | demais Δ, igual letra | — | **0.20** | tensão perceptível |
| **Salto médio diagonal** | Δ≠0,±1,±2, troca | — | **0.15** | idem, pior |
| **Tritono / oposto** | ±6 (qualquer letra) | — | **0.05** | choque máximo; quase nunca funciona |

Implementação: `dnum = min(|na−nb|, 12−|na−nb|)` (menor arco, 0..6, faz o wrap 12↔1 valer 1); classifica `(dnum, mesma_letra)` e consulta a tabela; sem match explícito cai nos "salto médio" por `mesma_letra`. Na tabela, "±2" e "±3" referem-se a esse arco mínimo (ex.: `8A→5A` e `8A→11A` colapsam ambos em `dnum=3`). **Não é monótona em `camelot_distance`** de propósito: relativo (`dnum=0`, comp=0.90) supera vizinho diagonal (`dnum=2`, comp=0.55), e mesmo na mesma distância crua o relativo (0.90) bate o vizinho (0.85) — é exatamente a não-linearidade que a tabela captura. O decaimento é **rápido após o vizinho/energy** (≤0.55) e **muito baixo no tritono** (0.05), refletindo que o ouvido tolera a "vizinhança" e rejeita o oposto.

> Lógica conferida em protótipo determinístico (2026-06-07): a classificação por `(dnum, mesma_letra)` cobre os 12×2 destinos sem ambiguidade; tritono = 0.05 em qualquer letra; wrap 1↔12 = 1 passo. Pronto para virar teste de tabela.

### Q2 — componente de energia/estrutura (OPCIONAL, injetado)

**O que medir.** Na pista, "energia" é principalmente **quão densa/intensa** a faixa soa. Para um score puro e barato, medimos **uma escalar de energia por faixa** e comparamos as duas. Decisão: **energia = loudness/intensidade média do mix** (RMS em dBFS, ou loudness integrado se o P1 já entregar), **não** número de seções. Justificativa de DJ: o que mata um mashup não é "A tem 5 seções e B tem 7", é uma faixa marcando muito mais forte que a outra (a densa "engole" a rarefeita). Número de seções é proxy ruim de vibe; fica de fora do MVP.

**Contrato de injeção (igual ao alinhamento — `metricas` é opcional):**

```python
metricas = {"energia_a": float, "energia_b": float}   # escalares por faixa, mesma unidade
```

O pipeline (`make_mashup`), que já carrega os stems/mix para a síntese, computa `energia_*` (ex.: RMS médio do mix em dBFS, ou LUFS). `comp_energia` é puro dado o `metricas`:

- Normaliza a diferença por uma **escala de tolerância** `energia_tol_db = 6.0` (≈ uma "casa" de fader; acima disso o desbalanço é nítido):
  `comp_energia = clamp(1 − |energia_a − energia_b| / energia_tol_db, 0, 1)`.
- Se a unidade vier linear (RMS 0..1) em vez de dB, o pipeline converte para dBFS antes de injetar (mantém o componente em domínio perceptual e a escala de tolerância fixa).

Sem `metricas` (teste sintético / sem stems): `energia=None`, sai do score, pesos renormalizam (harmônico+tempo). **Paridade testável garantida.** No MVP isso é aceitável porque tech×tech já tende a casar energia; o componente vira diferencial quando entrarem pares mais díspares (funk×house).

### Q3 — pesos e forma do `comp_tempo`

**Pesos default `w_harmonico=0.50 / w_tempo=0.35 / w_energia=0.15`.** Tradução da prática:
- **Harmônico domina (0.50):** o erro mais audível e imediato na pista é o choque de tom. É o que um DJ "ouve em 1 segundo".
- **Tempo logo atrás (0.35):** com `f∈{0.5,1,2}` o BPM quase sempre casa; quando *não* casa, o stretch vira artefato (rasga transientes do vocal declamado) — por isso peso alto, mas a penalidade só morde fora da janela de stretch.
- **Energia menor (0.15):** importa, mas o ouvido perdoa desbalanço de energia (resolve no mix/ganho) muito mais que choque de tom/tempo. É também o componente menos confiável (depende de áudio injetado).

Soma 1.0. Sem energia, renormaliza para `0.50/0.85 ≈ 0.588` (harmônico) e `0.35/0.85 ≈ 0.412` (tempo). **São defaults pré-calibração** — o P4 ajusta por Spearman; por isso `pesos` efetivos vão no `ScoreCompat`.

**`comp_tempo` (forma do decaimento):** escolhe `f∈{0.5,1,2}` via `_escolher_bpm_ratio` (reuso direto do `alignment.py`, mantendo consistência baseline↔proposto), obtém o `ratio` e o `stretch_pct = |ratio − 1| · 100`. Decaimento **linear até zerar em `max_stretch_pct`**:

`comp_tempo = clamp(1 − stretch_pct / max_stretch_pct, 0, 1)`.

Linear (não exponencial) por ser interpretável para o P4 e suficiente: dentro de ±8 % o Rubber Band segura a qualidade; passou disso, o componente já é ~0. Tech×tech (1–3 BPM ⇒ <2 %) fica ~0.75–1.0; gap de half-time mal resolvido (resíduo grande) afunda. Casos `bpm≤0/None` → `comp_tempo` neutro (1.0) e o `bpm_ratio` reportado = 1.0 (não há o que penalizar sem dado; consistente com o alinhamento).

### Q4 — H3 (tolerância do funk declamado): **fora do score no MVP**

**Decisão: NÃO incorporar H3 no score agora; deixar como análise posterior do P4.** Razões, pela lente de DJ e pelo escopo:
- O **MVP é tech×tech** (vocais melódicos/cantados, não declamados) — a premissa da H3 (vocal falado tolera salto harmônico) **não se aplica ao domínio do experimento principal**. Embutir um fator de declamação agora seria calibrar contra dados que não temos.
- H3 é uma **hipótese a testar, não um fato a embutir**: se o score já descontasse `w_harmonico` para vocal declamado, contaminaríamos a própria validação (o P4 não conseguiria isolar se a tolerância é real). O caminho limpo é **manter o score agnóstico** e deixar o P4 analisar os casos de salto harmônico alto (`camelot_dist` grande) cruzando com a natureza do vocal e as notas.
- **Gancho deixado pronto (sem ativar):** o `ScoreCompat` expõe `camelot_dist` cru e `harmonico` separado — exatamente o que o P4 precisa para a análise de H3 ("nos pares com `camelot_dist ≥ X`, vocais declamados foram notados melhor que o `harmonico` previa?"). Quando/se a H3 se confirmar e o produto crescer pra funk×house, o hook natural é um campo opcional em `ParamsScore` (ex.: `tolerancia_harmonica: float = 1.0`, multiplicando o "déficit" do harmônico) — **documentado como trabalho futuro, não implementado**.

## Critério de pronto

- [ ] `camelot_distance` (int) testado: mesma chave (0), relativo (mesmo nº, troca letra), vizinho (±1 mesma letra), energy ±2, tritono (máx), wrap-around (12↔1 = 1 passo), e **robustez a notação inválida** (vazio/None/`'0A'`/`'13B'`/`'8C'` → erro ou neutro claro, definido no código).
- [ ] `comp_harmonico` reproduz a **tabela do Q1** (cada classe → valor esperado), incluindo a não-monotonia relativo>vizinho-diagonal e o `key_ausente_neutro=0.5`.
- [ ] `comp_tempo` testado: BPM igual → 1.0; half/double-time resolve via `f` e dá ~1.0; 1–3 BPM (tech×tech) → ~0.75–1.0; gap acima de `max_stretch_pct` → 0.0; `bpm≤0` → neutro 1.0.
- [ ] `comp_energia` testado dado `metricas`: Δenergia=0 → 1.0; Δ=`energia_tol_db` → 0.0; e ausência (`metricas=None`) → `energia=None`.
- [ ] `compatibility_score` em `[0,1]`, **determinístico**, com **paridade** quando `metricas=None` (energia sai, pesos renormalizados; `pesos` no `ScoreCompat` refletem isso) — reproduzível (requisito P4).
- [ ] Breakdown exposto no `ScoreCompat`: `harmonico/tempo/energia` + `camelot_dist` cru + `bpm_ratio` + `pesos` efetivos (pro Spearman por componente e auditoria).
- [ ] Teste de sanidade: par perfeito (mesmo BPM/tom) ≈ 1.0; par ruim (tritono + gap de BPM > max_stretch) baixo; e ordenação coerente (relativo > energy > tritono).
- [ ] Não-regressão: `comp_tempo` usa o **mesmo** `_escolher_bpm_ratio` do `alignment.py` (consistência baseline↔proposto).

## Fundamentação teórica (lente: harmonic mixing / MIR) — revisão 2026-06-07

Segunda passada sobre Q1–Q4 pela lente da **teoria de harmonic mixing** e da literatura de **MIR**, confirmando as decisões da lente prática de DJ e ancorando-as. Implementação + testes (`tests/test_compatibility.py`, 29 casos) fechados nesta revisão.

**Q1 — por que tabela discreta (não fórmula contínua).** A roda Camelot é uma rotulagem da **roda das quintas** (Mixed In Key): ±1 no número = movimento de uma quinta justa/quarta justa (vizinhos de máxima proximidade harmônica), e a troca de letra A↔B com o **mesmo número** é o par **relativo** maior/menor (compartilham armadura/conjunto de notas). Logo a "distância" relevante para o ouvido é o **número de relações de quinta** mais a **mudança de modo** — discreta e por classe, não euclidiana. A tabela codifica três fatos da prática: (i) relativo (`0.90`) ≥ vizinho de quinta (`0.85`) porque relativo divide o material de notas e só troca o centro tonal; (ii) qualquer movimento que **combina** salto de número **e** troca de modo (diagonais) cai forte (`≤0.55`) — some uma classe inteira de proximidade; (iii) o **tritono / quinta-oposta** (arco 6, ±6 horas na roda ≈ trítono no círculo das quintas) é o choque máximo (`0.05`). A não-monotonia em `camelot_distance` (relativo, dist=1, supera vizinho-diagonal, dist=2) é proposital — é o que a métrica crua não captura e a tabela sim.

**Q2 — energia como loudness, à luz de MIR.** Em MIR, "energia" de áudio é classicamente o **RMS / short-time energy** (Tzanetakis & Cook 2002); loudness percebido escala melhor em **dBFS/LUFS** que em amplitude linear — por isso o componente opera em domínio logarítmico com tolerância `energia_tol_db`. Optou-se por **uma escalar de loudness por faixa** em vez de descritores de timbre (centroide/MFCC) ou de **estrutura** (nº de seções, self-similarity) porque: (a) é a feature de energia mais robusta e barata; (b) descritores de estrutura medem *forma temporal*, não *colisão de densidade* — que é o que degrada o mashup quando uma faixa "engole" a outra; (c) mantém o componente puro e injetável (paridade). Self-similarity de chroma/MFCC para casar **vibe/estrutura** fica como trabalho futuro registrado (mesma direção do trabalho futuro do alinhamento).

**Q3 — pesos à luz da prática de harmonic mixing.** Na literatura e na prática de DJ, a seleção de faixa para mixar é guiada **primeiro por compatibilidade harmônica e de tempo**; energia/loudness é ajustável no próprio mix (fader/EQ). Daí `w_harmonico=0.50 > w_tempo=0.35 > w_energia=0.15`. O decaimento **linear** de `comp_tempo` até `max_stretch_pct=8` reflete o limite prático do time-stretch de qualidade (Rubber Band) antes de artefatos audíveis — coerente com o `max_stretch_pct` do alinhamento.

**Q4 — H3 fora do score (confirmado).** Pela ótica MIR, H3 é uma **hipótese sobre percepção** (vocais declamados/percussivos toleram maior distância harmônica porque carregam menos conteúdo tonal sustentado — mais ruído/transiente que pitch estável). Embutir isso no score **antes** de medir contaminaria a validação. O `ScoreCompat` já expõe `camelot_dist` cru e `harmonico` isolado: o P4 testa H3 correlacionando, **nos pares de salto harmônico alto**, a natureza do vocal com o resíduo (nota observada − previsão do harmônico). Hook futuro (não implementado): `ParamsScore.tolerancia_harmonica` atenuando o déficit harmônico para vocais declamados, quando o domínio crescer para funk×house.

> **Notas de calibração para o P4 (divergências de lente, não bloqueantes):** os valores da tabela Q1 (relativo 0.90 vs 0.95; vizinho 0.85 vs 0.90) e `w_energia` (0.15 vs 0.20) variaram ±0.05 entre a lente de DJ e a de MIR — dentro do ruído de pré-calibração. **Ficam os defaults da spec fechada (lente DJ)**; o Spearman do P4 é o árbitro final. O ponto teórico robusto (independe da lente): ordenação mesma > relativo > vizinho > energy ±2 > tritono, decaimento rápido após energy e tritono ≈ 0; e `w_harmonico > w_tempo > w_energia`.

## Implementação fechada (`src/blend/compatibility.py`) — 2026-06-07

`camelot_distance(a, b) -> int` (crua, levanta `ValueError` em notação inválida) · `comp_harmonico(a, b, params) -> float` · `comp_tempo(bpm_base, bpm_vocal, params) -> (comp, ratio)` · `comp_energia(metricas, params) -> float | None` · `compatibility_score(a, b, metricas=None, params=None) -> ScoreCompat`. `ScoreCompat` em `types.py` com `camelot_dist` (-1 = tom ausente). `ParamsScore` (frozen) com os defaults acima. **66 testes passam** (`pytest`).
