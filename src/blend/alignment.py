"""Alinhamento do vocal (A) sobre a base (B). Contribuição central (H1).

Dois modos, ambos mantidos para o experimento às cegas do P4 (`blend-eval`):

* ``baseline`` — ingênuo: casa BPM/tom e solta o vocal no 1º downbeat da faixa.
* ``proposto`` — estrutura-aware: escolhe uma **seção de groove** da base e ancora
  o vocal no 1º downbeat dessa seção (+1 compasso quando a seção é longa).

Baseline e proposto diferem **só** em seção + ancoragem — o resto (stretch/pitch)
é idêntico, para um teste justo de H1.

`align` **não lê áudio**: o contrato é `TrackAnalysis` (P1). As métricas de áudio
por segmento (groove + headroom vocal) são computadas pelo **pipeline** — que já
carrega os stems da base para a síntese — e injetadas via `metricas_por_segmento`.
Sem métricas (teste sintético / sem stems), a escolha degrada de forma
determinística para "maior seção de groove recente".

Critério-fonte: ``specs/alinhamento-estrutura-aware.md`` (Decisão do agente
`blend-mashup`, FECHADA em 2026-06-07).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .types import AlignmentPlan, Segment, TrackAnalysis


# --------------------------------------------------------------------------- #
# Parâmetros da escolha de seção (defaults a calibrar no painel — ver spec)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ParamsSecao:
    """Pesos e limiares do score de escolha de seção (defaults da spec)."""

    w_vocalfit: float = 0.45
    w_recencia: float = 0.25
    w_duracao: float = 0.20
    w_repeticao: float = 0.10
    bonus_label: float = 0.05  # +bônus para chorus/drop
    min_segment_bars: int = 8
    groove_labels: frozenset = frozenset({"verse", "chorus", "drop", "inst"})
    edge_labels: frozenset = frozenset({
        "intro", "outro", "break", "bridge", "build",
        "start_loop", "end_loop", "silence", "fadein", "fadeout",
    })
    bonus_labels: frozenset = frozenset({"chorus", "drop"})
    repeticao_tol: float = 0.15
    score_eps: float = 0.02
    tie_eps_s: float = 0.5
    fallback_skip_intro_frac: float = 0.10


# Sinônimos de rótulo → forma canônica (normalização antes de filtrar/fundir).
_SINONIMOS = {
    "instrumental": "inst",
    "refrão": "chorus",
    "refrao": "chorus",
    "breakdown": "break",
}


# --------------------------------------------------------------------------- #
# Normalização e fusão de segmentos
# --------------------------------------------------------------------------- #
def _normalizar_label(label: str | None) -> str:
    """lower/strip + sinônimos; vazio/None → 'unknown'."""
    if label is None:
        return "unknown"
    norm = label.strip().lower()
    if not norm:
        return "unknown"
    return _SINONIMOS.get(norm, norm)


@dataclass
class _Cand:
    """Candidata interna: segmento (rótulo já normalizado) + índice de métrica.

    Mantemos o índice na lista original de métricas para casar o `vocal_fit_rel`
    mesmo após fusão (a fusão usa o índice do 1º fragmento do grupo).
    """

    start: float
    end: float
    label: str
    metr_idx: int  # índice em metricas_por_segmento (ou -1)

    @property
    def dur(self) -> float:
        return self.end - self.start


def _fundir_adjacentes(segments: list[Segment]) -> list[_Cand]:
    """Normaliza rótulos e funde segmentos adjacentes de mesmo rótulo.

    O allin1 fragmenta tech house em blocos de 4–8 compassos; sem fundir, cada
    fragmento ficaria abaixo de `dur_min_s` e zeraria as candidatas de groove.
    A fusão usa o índice de métrica do **primeiro** fragmento do grupo.
    """
    cands: list[_Cand] = []
    for i, seg in enumerate(segments):
        lab = _normalizar_label(seg.label)
        if cands and cands[-1].label == lab and math.isclose(
            cands[-1].end, seg.start, abs_tol=1e-6
        ):
            # adjacente e mesmo rótulo: estende o grupo anterior
            cands[-1].end = seg.end
        else:
            cands.append(_Cand(seg.start, seg.end, lab, i))
    return cands


def _vocal_fit(cand: _Cand, metricas_por_segmento: list[dict] | None) -> float | None:
    """Lê vocal_fit_rel da métrica injetada; None se ausente/fora de faixa."""
    if metricas_por_segmento is None:
        return None
    idx = cand.metr_idx
    if idx < 0 or idx >= len(metricas_por_segmento):
        return None
    m = metricas_por_segmento[idx]
    v = m.get("vocal_fit_rel") if isinstance(m, dict) else None
    if v is None:
        return None
    return max(0.0, min(1.0, float(v)))


# --------------------------------------------------------------------------- #
# Score composto
# --------------------------------------------------------------------------- #
def _pesos_normalizados(params: ParamsSecao, tem_vocalfit: bool) -> dict:
    """Pesos finais somando 1.0.

    Sem `vocal_fit` (métricas None), o peso de vocal_fit é redistribuído
    proporcionalmente aos demais termos ativos e tudo é renormalizado.
    """
    w = {
        "vocalfit": params.w_vocalfit if tem_vocalfit else 0.0,
        "recencia": params.w_recencia,
        "duracao": params.w_duracao,
        "repeticao": params.w_repeticao,
    }
    total = sum(w.values())
    if total <= 0:
        return w
    return {k: v / total for k, v in w.items()}


def _pontuar(
    cands: list[_Cand],
    metricas_por_segmento: list[dict] | None,
    params: ParamsSecao,
    com_bonus: bool,
) -> list[tuple[float, float, _Cand]]:
    """Pontua candidatas. Retorna [(score, vocal_fit_efetivo, cand)].

    Termos normalizados **entre as candidatas** (relativos), conforme a spec.
    `vocal_fit_efetivo` é usado também como critério de desempate.
    """
    n = len(cands)
    if n == 0:
        return []

    fits = [_vocal_fit(c, metricas_por_segmento) for c in cands]
    tem_vocalfit = any(f is not None for f in fits)
    pesos = _pesos_normalizados(params, tem_vocalfit)

    # duração relativa (proxy da seção principal)
    maior_dur = max(c.dur for c in cands)
    durs_rel = [(c.dur / maior_dur) if maior_dur > 0 else 0.0 for c in cands]

    # recência inversa: 1ª seção cheia (menor start) pontua mais
    ordem_start = sorted(range(n), key=lambda i: cands[i].start)
    rank = [0] * n
    for r, i in enumerate(ordem_start):
        rank[i] = r
    recencias = [
        (1.0 - rank[i] / (n - 1)) if n > 1 else 1.0 for i in range(n)
    ]

    # repetição: rótulo igual + vocal_fit (ou duração, se sem fit) ~igual
    repeticoes = _repeticao(cands, fits, params)

    out: list[tuple[float, float, _Cand]] = []
    for i, c in enumerate(cands):
        fit_ef = fits[i] if fits[i] is not None else 0.0
        score = (
            pesos["vocalfit"] * fit_ef
            + pesos["recencia"] * recencias[i]
            + pesos["duracao"] * durs_rel[i]
            + pesos["repeticao"] * repeticoes[i]
        )
        if com_bonus and c.label in params.bonus_labels:
            score += params.bonus_label
        out.append((score, fit_ef, c))
    return out


def _repeticao(
    cands: list[_Cand], fits: list[float | None], params: ParamsSecao
) -> list[float]:
    """Quantas outras candidatas repetem rótulo + fit (~tol), normalizado [0,1]."""
    n = len(cands)
    if n <= 1:
        return [0.0] * n
    contagem = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if cands[i].label != cands[j].label:
                continue
            fi = fits[i] if fits[i] is not None else cands[i].dur
            fj = fits[j] if fits[j] is not None else cands[j].dur
            ref = max(abs(fi), abs(fj), 1e-9)
            if abs(fi - fj) / ref <= params.repeticao_tol:
                contagem[i] += 1
    maxc = max(contagem)
    if maxc == 0:
        return [0.0] * n
    return [c / maxc for c in contagem]


def _escolher_melhor(
    pontuadas: list[tuple[float, float, _Cand]], params: ParamsSecao
) -> _Cand:
    """argmax(score) com desempate determinístico.

    |Δscore| < score_eps → maior vocal_fit → maior duração → menor start.
    """
    # ordena por score desc; o topo define a "faixa" de empate
    pontuadas_ord = sorted(pontuadas, key=lambda t: t[0], reverse=True)
    melhor_score = pontuadas_ord[0][0]
    empatadas = [
        t for t in pontuadas_ord
        if (melhor_score - t[0]) < params.score_eps
    ]
    # tie-break: maior vocal_fit, maior duração, menor start
    empatadas.sort(key=lambda t: (-t[1], -t[2].dur, t[2].start))
    return empatadas[0][2]


# --------------------------------------------------------------------------- #
# Função pura: escolha da seção de groove (+ fallback em cascata)
# --------------------------------------------------------------------------- #
def escolher_secao_groove(
    segments: list[Segment],
    downbeats: list[float],
    bpm: float | None,
    metricas_por_segmento: list[dict] | None = None,
    params: ParamsSecao | None = None,
) -> tuple[Segment, int]:
    """Escolhe a seção de groove da base onde inserir o vocal.

    Pura e 100% testável sem áudio. Retorna ``(Segment, nivel_fallback)``:
    nível 0 = caminho principal; 1–4 = degraus do fallback (ver spec).

    `metricas_por_segmento` é uma lista **alinhada a `segments`** com
    ``{'vocal_fit_rel': float em [0,1]}`` por segmento, ou ``None`` (sem stems /
    teste sintético) — nesse caso o termo vocal_fit sai do score e seu peso é
    redistribuído aos demais.

    Guardas (sem exceção): `bpm` ≤ 0/None **ou** algum segmento com `end ≤ start`
    → cai direto no fallback nível 4 (equivale ao baseline).
    """
    params = params or ParamsSecao()

    # --- Guarda: BPM inválido -> nível 4 (baseline) --------------------------
    if bpm is None or bpm <= 0:
        return _fallback_nivel_4(downbeats), 4

    # --- Guarda: segmento inválido (end <= start) -> nível 4 -----------------
    for seg in segments:
        if seg.end <= seg.start:
            return _fallback_nivel_4(downbeats), 4

    bar_s = 4 * 60.0 / bpm
    dur_min_s = params.min_segment_bars * bar_s

    cands = _fundir_adjacentes(segments)

    # --- Caminho principal: candidatas GROOVE com dur >= dur_min_s ----------
    groove = [
        c for c in cands
        if c.label in params.groove_labels and c.dur >= dur_min_s
    ]
    if groove:
        pontuadas = _pontuar(groove, metricas_por_segmento, params, com_bonus=True)
        melhor = _escolher_melhor(pontuadas, params)
        return _para_segment(melhor), 0

    # --- Nível 1: sem candidata GROOVE -> não-borda com dur >= dur_min_s -----
    nivel1 = [
        c for c in cands
        if c.label not in params.edge_labels and c.dur >= dur_min_s
    ]
    if nivel1:
        # sem bônus de rótulo neste nível
        pontuadas = _pontuar(nivel1, metricas_por_segmento, params, com_bonus=False)
        melhor = _escolher_melhor(pontuadas, params)
        return _para_segment(melhor), 1

    # --- Nível 2: só segmentos curtos -> relaxa dur_min para metade ----------
    nivel2 = [
        c for c in cands
        if c.label not in params.edge_labels and c.dur >= dur_min_s / 2
    ]
    if nivel2:
        pontuadas = _pontuar(nivel2, metricas_por_segmento, params, com_bonus=False)
        melhor = _escolher_melhor(pontuadas, params)
        return _para_segment(melhor), 2
    # senão, o não-borda mais longo (se existir)
    nao_borda = [c for c in cands if c.label not in params.edge_labels]
    if nao_borda:
        melhor = max(nao_borda, key=lambda c: (c.dur, -c.start))
        return _para_segment(melhor), 2

    # --- Nível 3: segments vazio/só borda -> janela deslizante --------------
    if downbeats:
        secao = _fallback_nivel_3(downbeats, bar_s, params)
        if secao is not None:
            return secao, 3

    # --- Nível 4: sem downbeats / nada acima -> baseline ---------------------
    return _fallback_nivel_4(downbeats), 4


def _para_segment(c: _Cand) -> Segment:
    return Segment(c.start, c.end, c.label)


def _fallback_nivel_3(
    downbeats: list[float], bar_s: float, params: ParamsSecao
) -> Segment | None:
    """Janela de `min_segment_bars` compassos a partir de skip_intro_frac da faixa.

    Sem métricas de áudio aqui (função pura), escolhemos a 1ª janela após o skip
    — determinística e ancorada num downbeat real.
    """
    if not downbeats:
        return None
    dur_total = downbeats[-1]
    if dur_total <= 0:
        return None
    skip = dur_total * params.fallback_skip_intro_frac
    janela = params.min_segment_bars * bar_s
    # 1º downbeat >= skip
    inicio = next((d for d in downbeats if d >= skip - 1e-9), downbeats[0])
    fim = inicio + janela
    return Segment(inicio, fim, "unknown")


def _fallback_nivel_4(downbeats: list[float]) -> Segment:
    """Seção sintética cobrindo a faixa; ancoragem no 1º downbeat (ou 0.0).

    Equivale ao baseline — garante que o proposto nunca fica pior que o baseline.
    """
    inicio = downbeats[0] if downbeats else 0.0
    fim = downbeats[-1] if downbeats else inicio
    if fim <= inicio:
        fim = inicio + 1.0  # seção sintética não-degenerada
    return Segment(0.0, fim, "full")


# --------------------------------------------------------------------------- #
# bpm_ratio — half/double-time
# --------------------------------------------------------------------------- #
def _escolher_bpm_ratio(bpm_base: float, bpm_vocal: float) -> float:
    """Fator f ∈ {0.5, 1, 2} que minimiza o stretch; ratio = bpm_base/(f·bpm_vocal).

    O stretch ideal é 1.0 (sem esticar): escolhemos f que deixa o ratio mais
    próximo de 1.0. Trata gaps grandes de BPM (funk × house) via half/double-time.
    """
    if bpm_vocal is None or bpm_vocal <= 0 or bpm_base is None or bpm_base <= 0:
        return 1.0
    melhor_f = 1.0
    melhor_dist = float("inf")
    for f in (0.5, 1.0, 2.0):
        ratio = bpm_base / (f * bpm_vocal)
        dist = abs(ratio - 1.0)
        if dist < melhor_dist - 1e-12:
            melhor_dist = dist
            melhor_f = f
    return bpm_base / (melhor_f * bpm_vocal)


# --------------------------------------------------------------------------- #
# Ancoragem do vocal nos downbeats
# --------------------------------------------------------------------------- #
def _ancorar(
    target: Segment,
    downbeats: list[float],
    bar_s: float,
    params: ParamsSecao,
) -> float:
    """Offset do vocal: 1º downbeat >= target.start (+1 compasso se seção longa).

    Se nenhum downbeat cai na seção, o mais próximo do start; se `downbeats`
    vazio, o próprio start.
    """
    if not downbeats:
        return target.start
    dentro = [d for d in downbeats if target.start - 1e-9 <= d < target.end + 1e-9]
    if dentro:
        offset = dentro[0]
        ancorou_na_secao = True
    else:
        # nenhum downbeat cai na seção: o mais próximo do start (fora dela)
        offset = min(downbeats, key=lambda d: abs(d - target.start))
        ancorou_na_secao = False
    # +1 compasso só quando ancoramos no 1º downbeat DA seção (fronteira) e a
    # seção é longa o bastante (>= min_segment_bars+1 compassos), para não jogar
    # a 1ª frase em cima do riser/crash de transição. No ramo "downbeat mais
    # próximo do start" o offset já não é a fronteira — somar +1 compasso só
    # afastaria ainda mais o vocal da seção (ver finding adversarial).
    if ancorou_na_secao:
        dur_min1 = (params.min_segment_bars + 1) * bar_s
        if target.end - target.start >= dur_min1 - 1e-9:
            candidato = offset + bar_s
            if candidato < target.end - 1e-9:
                offset = candidato
    return offset


# --------------------------------------------------------------------------- #
# align — orquestra baseline vs proposto
# --------------------------------------------------------------------------- #
def align(
    vocal: TrackAnalysis,
    base: TrackAnalysis,
    mode: str = "proposto",
    metricas_por_segmento: list[dict] | None = None,
    params: ParamsSecao | None = None,
) -> AlignmentPlan:
    """Decide como o vocal entra sobre a base. Não lê áudio (contrato TrackAnalysis).

    mode='proposto': estrutura-aware (escolhe a seção + ancora no downbeat dela).
    mode='baseline': ingênuo (casa BPM/tom + 1º downbeat da faixa).

    Baseline e proposto diferem **só** em seção + ancoragem — mesmo stretch/pitch
    (teste justo de H1). Ambos existem para o experimento comparativo (P4).
    """
    params = params or ParamsSecao()

    bpm_ratio = _escolher_bpm_ratio(base.bpm, vocal.bpm)
    # pitch_shift fica em 0.0 por enquanto.
    # TODO P2/H2: derivar a transposição da distância Camelot entre
    # vocal.key_camelot e base.key_camelot, respeitando camelot_transpose_threshold
    # (regra H3 — vocais declamados toleram salto). Depende do score de
    # compatibilidade (compatibility.py), fora do escopo desta spec.
    pitch_shift = 0.0

    if mode == "baseline":
        offset = base.downbeats[0] if base.downbeats else 0.0
        seg_full = _secao_full(base)
        return AlignmentPlan(
            target_segment=seg_full,
            bpm_ratio=bpm_ratio,
            pitch_shift_semitones=pitch_shift,
            vocal_offset=offset,
            mode="baseline",
            nivel_fallback=0,
        )

    # mode == 'proposto'
    target, nivel = escolher_secao_groove(
        base.segments, base.downbeats, base.bpm, metricas_por_segmento, params
    )
    if base.bpm and base.bpm > 0:
        bar_s = 4 * 60.0 / base.bpm
    else:
        bar_s = 0.0

    if nivel == 4:
        # equivale ao baseline: 1º downbeat (ou 0.0)
        offset = base.downbeats[0] if base.downbeats else 0.0
    else:
        offset = _ancorar(target, base.downbeats, bar_s, params)

    return AlignmentPlan(
        target_segment=target,
        bpm_ratio=bpm_ratio,
        pitch_shift_semitones=pitch_shift,
        vocal_offset=offset,
        mode="proposto",
        nivel_fallback=nivel,
    )


def _secao_full(base: TrackAnalysis) -> Segment:
    """Seção sintética cobrindo a faixa toda (baseline)."""
    fim = 0.0
    if base.segments:
        fim = max(s.end for s in base.segments)
    if base.downbeats:
        fim = max(fim, base.downbeats[-1])
    if fim <= 0:
        fim = 1.0
    return Segment(0.0, fim, "full")


# --------------------------------------------------------------------------- #
# Helper de áudio — STUB (depende de numpy/stems/P1; computado no pipeline)
# --------------------------------------------------------------------------- #
def metricas_por_segmento_de_audio(stems, sr, segments, params=None):
    """Computa `metricas_por_segmento` (vocal_fit_rel) a partir dos stems da base.

    NÃO IMPLEMENTADO AQUI de propósito: depende de numpy e dos stems separados
    pelo P1 (drums+bass para `groove_rel`; `other`/mix para `headroom_rel` na
    banda vocal ~200 Hz–4 kHz). Por isso vive fora desta função pura.

    O **pipeline** (`make_mashup`), que já carrega os stems da base para a
    síntese, computa essas métricas e as **injeta** em `align`/`escolher_secao_groove`
    via `metricas_por_segmento`. Mantém `align` sem leitura de áudio e os testes
    de alinhamento 100% sintéticos.

    Contrato esperado (quando implementado): retorna uma lista alinhada a
    `segments`, cada item ``{'vocal_fit_rel': float em [0,1]}`` com
    ``vocal_fit_rel = groove_rel · headroom_rel``.
    """
    raise NotImplementedError(
        "metricas_por_segmento_de_audio é computado pelo pipeline (P2) a partir "
        "dos stems do P1; ver docstring."
    )
