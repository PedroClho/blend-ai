# Ancoragem manual (DJ-in-the-loop) na aplicação

**Status:** implementado (2026-07-03) · **Módulos:** P2 (motor) + P3 (produto) · **Dono da decisão:** Pedro

## Problema

O alinhamento automático é o elo fraco do pipeline: o melhor mashup gerado até aqui
(vocal do break de A, 16 compassos, sobre o break de B) saiu dos knobs manuais do
`make_mashup` (`vocal_in`, `vocal_dur`, `vocal_offset`) via CLI/chat — a aplicação web
não expõe esses controles. O usuário da UI fica preso à escolha automática de seção.

## Escopo

Levar o fluxo **"ver + ancorar na mão"** para a aplicação:

1. **Análise prévia por faixa** — endpoint que roda a análise (allin1 + Essentia) de
   UMA faixa e devolve BPM, tom, downbeats e seções, para a UI desenhar a grade antes
   de gerar. Cache por hash de conteúdo do arquivo (a análise é função pura do arquivo);
   o job de mashup reaproveita o mesmo cache (pula allin1/Essentia na 2ª vez).
2. **Âncoras manuais na API** — `POST /api/mashups` aceita `vocal_in`, `vocal_dur`,
   `vocal_offset` (segundos) e `transpor` (H3: desligar transposição p/ vocal declamado).
3. **UI modo "manual"** — terceira estratégia ao lado de estrutura-aware/baseline:
   clique na waveform de A marca o início da janela do vocal (snap no downbeat de A),
   stepper define o tamanho em compassos, clique na waveform de B marca o ponto de
   entrada (snap no downbeat de B). Seções detectadas coloridas sobre as waveforms
   servem de guia visual (achar o break). Snap é responsabilidade da UI; o motor
   confia nos segundos recebidos.

## Interface entre módulos

- `make_mashup(..., analise_vocal=None, analise_base=None)` — análises pré-computadas
  (TrackAnalysis) pulam `analyze()`/`estimate_key()`. Overrides manuais marcam
  `plan.mode = "manual"` e re-rotulam `plan.target_segment` para a seção de B que
  contém o `vocal_offset` (a leitura "vocal entra na seção X" continua verdadeira).
- `POST /api/analyses` (multipart `faixa`) → `202 {analysis_id}`;
  `GET /api/analyses/{id}` → job com `resultado: {bpm, key_camelot, duracao, downbeats, segments, cache}`.
- Cache em `data/cache/analises/<sha256[:24]>.json`, versão explícita; só análises
  completas (com seções) são cacheadas — fallback madmom degradado nunca congela no cache.
- O modo manual da UI envia `modo=proposto` + âncoras (stretch/pitch continuam
  automáticos — o humano decide COLOCAÇÃO, a máquina decide beatmatch/tom).

## Ajustes pós-v1 (feedback do Pedro, 2026-07-03)

- **Clique = audição, campo = âncora.** Clicar na onda/tira de seções navega e TOCA
  (achar o ponto de ouvido); a âncora é definida por campo de tempo (`2:08` ou
  segundos), botão "⌖ no cursor" (captura o playhead) e nudge ±1 compasso — tudo
  com snap no downbeat. Clique nunca marca âncora.
- **Tira de seções sólida** abaixo da onda (estilo phrase bar do Rekordbox) no lugar
  das lavagens de cor a 16% sobre a onda colorida (ilegível); segmentos adjacentes
  de mesmo rótulo são fundidos e o rótulo aparece dentro do bloco.
- **BPM alvo** (`bpm_alvo`, 40–220): as DUAS faixas vão para o BPM final escolhido
  antes do merge — a base ganha `base_ratio = alvo/bpm_base` (time-stretch puro,
  tom preservado) e o vocal recalcula o ratio contra o alvo (mesma regra de
  half/double-time). Âncoras são escolhidas no relógio ORIGINAL de B e convertidas
  (`t → t/base_ratio`) depois de `aplicar_ancoras_manuais`. Vazio = BPM da base.

## Fora do escopo (visão)

Arrastar/redimensionar a região (v1 é campo + stepper), zoom na waveform, ajuste
fino em beats (snap é por compasso), pré-escuta do trecho ancorado antes de gerar.

## Critério de pronto

- `pytest` verde (âncoras → plano manual re-rotulado; cache round-trip; validação da API).
- Ponta a ponta real: análise prévia de uma faixa das 11 bases devolve seções; mashup
  com âncoras manuais devolve `plan.mode="manual"`, `vocal_offset` ecoado e `.wav` audível.
- UI buildada servida pelo FastAPI com o modo manual operável.
