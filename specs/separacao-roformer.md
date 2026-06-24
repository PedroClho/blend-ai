# Spec — Backend de separação Mel-Band RoFormer (Fase 1b)

> Módulo: P1 (`blend-audio`) · Arquivo: `src/blend/separation.py` · Status: **ABERTA — proposta de produto (pós-entrega 01/07); requer brainstorming/review da equipe antes de implementar**

## Problema / motivação

A separação atual usa Demucs v4 **`htdemucs`** (modelo único, escolhido por causa da RAM — `htdemucs_ft` estourava os 6 GB da RTX 2060 + ~8 GB do WSL). É sólida, mas está ~0,5–1 dB de SDR atrás do estado da arte de 2024–2026 (**Mel-Band RoFormer** / **BS-RoFormer**, 1º lugar no Sound Demixing Challenge). Como o vocal de A e o instrumental de B são a **matéria-prima** do mashup, stems mais limpos reduzem artefatos (vazamento de hi-hat no vocal, resíduo de vocal no instrumental) que hoje degradam a mixagem e atrapalham a detecção de janela vocal (`_melhor_janela_vocal`) e, na Fase 2, os embeddings de mashability.

Não é o diferencial do produto — é **polimento de qualidade de entrada**, ROI médio. Entra como **troca opcional atrás da interface estável**, sem mexer no resto do pipeline.

## Hipótese (se experimento) e como validar

Sem hipótese de produto; é melhoria de engenharia validável **objetivamente**: SDR/SI-SDR em **MUSDB18** (test set) do backend novo vs. `htdemucs`. Critério de aceite: ganho de SDR de vocais/instrumental **sem** regressão de tempo/inviabilidade na RTX 2060.

## Escopo

**Entra:**
1. **Switch de backend** em `separation.py`: `"htdemucs"` (atual, default) | `"roformer"` (novo), selecionável por env var (`BLEND_SEP_BACKEND`) ou parâmetro — **a interface `separate(samples, sr) -> dict[str,np.ndarray]` não muda** (mesmas chaves `vocals/drums/bass/other`, mesmo formato `(canais, amostras)` float32).
2. Backend RoFormer via **`python-audio-separator`** (ecossistema UVR mantido), com **inferência em chunks** (`segment_size`/`chunk_duration`/`batch_size`) para caber em 6 GB de VRAM, e fallback ONNX/CPU.
3. Mapeamento de saída: RoFormer de 2 stems (vocals/instrumental) → preencher `vocals` + derivar `drums/bass/other` (ou rodar um 2º modelo de stems quando precisar dos 4). **Atenção:** o alinhamento usa `drums+bass` (`groove_rel`) e `other` (`headroom_rel`); a síntese soma "tudo menos vocals". Definir no review se o `proposto` precisa dos 4 stems ou se um modelo 2-stem + Demucs só para drums/bass basta.

**Não entra:**
- BS-RoFormer Ensemble (16–20 GB VRAM — inviável na 2060).
- Treinar/fine-tunar qualquer modelo de separação (ROI negativo no hardware/dados — ver roadmap).
- Trocar o default: `htdemucs` continua o caminho garantido; RoFormer é opt-in até provar ganho e estabilidade.

## Abordagem técnica

- Manter `_get_model()`/`_MODEL` como cache, generalizado por backend (`_BACKEND`).
- Reaproveitar o padrão de **fallback de memória** já existente (`try cuda → except RuntimeError "out of memory" → cpu`): com RoFormer, o equivalente é reduzir `segment_size`/`chunk_duration` antes de cair para CPU.
- Cuidar do **teto de RAM de sistema** (16 GB — o mesmo que matou `htdemucs_ft`): chunking limita também a RAM do host, não só a VRAM.
- Pesos baixados de HuggingFace em runtime → **assar no Docker** para reprodutibilidade (mesma decisão A3 da auditoria técnica para os pesos de allin1/Demucs).

## Interface (`src/blend/types.py`)

Nenhuma mudança de tipo. Contrato preservado: `separate(samples, sr) -> dict[str,np.ndarray]` com chaves `vocals/drums/bass/other`. `pipeline.py`, `synthesis.py` e `alignment.py` **não mudam**.

## Critério de pronto

- [ ] `separate()` com `BLEND_SEP_BACKEND=roformer` retorna o mesmo dicionário de stems, mesmo shape/dtype; com o default, comportamento atual intacto.
- [ ] Inferência cabe na RTX 2060 (6 GB) com chunking; medir VRAM/RAM de pico e tempo por faixa de ~3 min.
- [ ] **SDR em MUSDB18** do backend novo vs. `htdemucs` (tabela objetiva no `docs/` ou `eval/`); aceite = ganho sem regressão de viabilidade.
- [ ] Fallback: sem GPU / OOM → degrada (chunk menor → CPU) sem exceção.
- [ ] Verificação real: gerar um mashup ponta-a-ponta com cada backend e **ouvir** (vocal mais limpo, menos vazamento).
- [ ] Pesos assados na imagem Docker (reprodutibilidade). `pytest` verde.
