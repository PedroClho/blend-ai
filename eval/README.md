# Avaliação (P4)

Hipóteses e métricas detalhadas no `CLAUDE.md` (Avaliação científica) e em `designs/proposta-automashup.html`.

- **Objetivas:** SDR (MUSDB18, `museval`), F-measure de beat/downbeat (Harmonix, `mir_eval`), MIREX de tom (GiantSteps), erro de downbeat (ms). Tom também cruzado com o Rekordbox (silver standard).
- **Subjetiva (testa H1 e H2):** N mashups por **baseline** vs **proposto** → painel às cegas (Likert 1–5: qualidade, musicalidade, artefatos). **Wilcoxon** (H1); **Spearman** score×notas (H2).

Protocolo definido **antes** de coletar. Resultados e dados ficam aqui e em `data/`.

## Experimento subjetivo — como rodar

Protocolo congelado: [`specs/experimento-subjetivo.md`](../specs/experimento-subjetivo.md).

1. **Selecionar pares** (sem GPU): `python eval/gera_estimulos.py --listar`
2. **Gerar estímulos** (GPU, ~2 min/braço; resumível): `python eval/gera_estimulos.py --n 12 --dur 30`
   → `data/experimento/`: `estimulos/*.wav` (cegos), `gabarito.csv` (condição↔ID, **não dar ao painel**), `respostas_template.csv`, `ordem_avaliador_*.csv`.
3. **Coletar**: o painel preenche `data/experimento/respostas.csv` (Likert) e `respostas_ab.csv` (escolha A/B), seguindo as ordens cegas.
4. **Analisar**: `python eval/analise.py` → H1 (Wilcoxon + rank-biserial + A/B), H2 (Spearman + IC95% bootstrap), H3 (descritivo).

- `matriz_compatibilidade.py` — score H2 sobre o Rekordbox (sem áudio).
- `estimulos.py` / `analise.py` — helpers puros (testados em `tests/test_eval.py`).
