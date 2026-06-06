# Avaliação (P4)

Hipóteses e métricas detalhadas no `CLAUDE.md` (Avaliação científica) e em `designs/proposta-automashup.html`.

- **Objetivas:** SDR (MUSDB18, `museval`), F-measure de beat/downbeat (Harmonix, `mir_eval`), MIREX de tom (GiantSteps), erro de downbeat (ms). Tom também cruzado com o Rekordbox (silver standard).
- **Subjetiva (testa H1 e H2):** N mashups por **baseline** vs **proposto** → painel às cegas (Likert 1–5: qualidade, musicalidade, artefatos). **Wilcoxon** (H1); **Spearman** score×notas (H2).

Protocolo definido **antes** de coletar. Resultados e dados ficam aqui e em `data/`.
