# Entrega — Checkpoint (prova de conceito) · Blend AI

**Blend AI** gera mashups automáticos encaixando o vocal de uma faixa sobre o
instrumental de outra, casando BPM, tom e — o diferencial — a **estrutura musical**.

Esta entrega é uma **prova de conceito**: o motor roda ponta-a-ponta e produz mashups
reais. O experimento subjetivo (painel às cegas) está com a infraestrutura pronta e é o
próximo passo.

## O que está sendo entregue

1. **Exemplo de áudio (principal):** `EXEMPLO_aula_tatsch_x_brokenhill_45s.wav` — trecho
   de 45s do mashup **Tatsch · Tension (vocal) × Broken Hill · Zero Tolerance (base)**.
   O vocal entra em ~0:46. Sem transposição (o vocal cai natural no tom da base).
2. **Mashup completo:** `APROVADO_tatsch_x_brokenhill_v1.wav` (faixa inteira).
3. **Métodos e datasets:** [`metodos-e-datasets.md`](metodos-e-datasets.md).
4. **Resultado quantitativo (H2):** [`resultado-matriz-compatibilidade.md`](resultado-matriz-compatibilidade.md)
   — matriz de compatibilidade sobre dados reais do Rekordbox.

> Os `.wav` não vão no repositório (áudio comercial é gitignored) — anexar à mão na entrega.

## Como o exemplo foi gerado

Pipeline: separação de fontes (Demucs) → beat/downbeat/estrutura (allin1) → tom→Camelot
(Essentia) → score de compatibilidade → alinhamento → síntese (time-stretch/pitch-shift
Rubber Band) → mixagem.

O alinhamento deste exemplo foi feito com **controle manual assistido** (DJ no loop):
escolha do trecho do vocal, do ponto de ancoragem na base e da decisão de não transpor.
Receita 100% reproduzível:

```
python scripts/gera_par.py \
  --vocal "data/raw/vocal/Tatsch - Tension [Extended Mix].wav" \
  --base  "data/raw/bases/Broken Hill - Zero Tolerance (Extended) [AET.mp3" \
  --modos proposto --sem-transposicao \
  --vocal-in 59 --vocal-dur 14.8 --vocal-offset 46
python scripts/corta_trecho.py <mashup>.wav 40 85 EXEMPLO_aula_tatsch_x_brokenhill_45s.wav
```

## Achados que sustentam as hipóteses

- **H1 (estrutura-aware):** o motor escolhe a seção da base e ancora o vocal no downbeat
  dela; o ponto fraco do modo 100% automático em vocal esparso motivou o controle manual
  assistido (DJ escolhe o trecho/âncora) — o caminho para resultado utilizável.
- **H2 (score de compatibilidade):** a matriz separa bem pares compatíveis dos ruins
  (ver doc da matriz).
- **H3 (vocal declamado tolera salto harmônico):** confirmado na prática — vocais
  declamados caem bem **sem transposição** mesmo com tom distante, evitando o artefato de
  um pitch-shift grande.

## Status e próximos passos

- ✅ Pipeline ponta-a-ponta na GPU; mashups reais aprovados de ouvido.
- ✅ Motor com controles de ancoragem manual (`vocal_in`/`vocal_dur`/`vocal_offset`,
  `compassos`, `transpor`) — backend da interface "Ver + ancorar na mão".
- ⏭️ Interface visual (waveform + estrutura das 2 faixas + ancoragem na tela).
- ⏭️ Coleta do experimento subjetivo (Wilcoxon/Spearman) — infra já congelada.
