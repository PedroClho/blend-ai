"""Síntese do mashup: time-stretch + pitch-shift (Rubber Band) + mixagem."""
from __future__ import annotations

import numpy as np

from .types import AlignmentPlan


def _stretch_pitch(
    vocal: np.ndarray, sr: int, ratio: float, semitones: float
) -> np.ndarray:
    """Time-stretch (ratio) + pitch-shift (semitons) no vocal (canais, amostras).

    `ratio` é o fator de Rubber Band (>1 acelera, <1 desacelera) — já vem pronto
    do alinhamento (`bpm_ratio = bpm_base / (f·bpm_vocal)`).
    """
    import pyrubberband as pyrb

    y = np.asarray(vocal, dtype=np.float32)
    w = y.T if y.ndim == 2 else y  # pyrb espera (amostras,) ou (amostras, canais)
    if ratio and abs(ratio - 1.0) > 1e-4:
        w = pyrb.time_stretch(w, sr, ratio)
    if semitones and abs(semitones) > 1e-3:
        w = pyrb.pitch_shift(w, sr, semitones)
    out = w.T if y.ndim == 2 else w
    return np.ascontiguousarray(out, dtype=np.float32)


def _recortar(
    voc: np.ndarray,
    sr: int,
    inicio: float,
    dur: float | None,
    fade_in_s: float = 0.02,
    fade_out_s: float = 0.20,
) -> np.ndarray:
    """Corta o vocal (canais, n) em [inicio, inicio+dur) com fades nas bordas."""
    i0 = max(0, int(round(inicio * sr)))
    i1 = voc.shape[1] if dur is None else min(voc.shape[1], i0 + int(round(dur * sr)))
    if i1 <= i0:
        return np.zeros((voc.shape[0], 1), dtype=np.float32)
    out = np.ascontiguousarray(voc[:, i0:i1], dtype=np.float32).copy()
    nfi = min(int(fade_in_s * sr), out.shape[1])
    if nfi > 1:
        out[:, :nfi] *= np.linspace(0.0, 1.0, nfi, dtype=np.float32)
    nfo = min(int(fade_out_s * sr), out.shape[1])
    if nfo > 1:
        out[:, -nfo:] *= np.linspace(1.0, 0.0, nfo, dtype=np.float32)
    return out


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64))) if x.size else 0.0


def _to_channels(x: np.ndarray, ch: int) -> np.ndarray:
    """Ajusta o nº de canais: mono→ch (replica) ou estéreo→mono (média)."""
    if x.shape[0] == ch:
        return x
    if x.shape[0] == 1:
        return np.repeat(x, ch, axis=0)
    if x.shape[0] > ch:
        return x.mean(axis=0, keepdims=True)
    return np.repeat(x[:1], ch, axis=0)


def _passa_altas(x: np.ndarray, sr: int, fc: float = 110.0, ordem: int = 2) -> np.ndarray:
    """Passa-altas Butterworth (gentil): tira graves do vocal p/ não competir com o baixo de B."""
    if x.size == 0:
        return x
    from scipy.signal import butter, sosfilt

    sos = butter(ordem, fc / (sr / 2.0), btype="highpass", output="sos")
    return np.ascontiguousarray(sosfilt(sos, x, axis=-1), dtype=np.float32)


def _envelope(mono: np.ndarray, sr: int, suav_s: float = 0.05) -> np.ndarray:
    """Envelope de amplitude suavizado, normalizado em [0,1] (p/ ducking)."""
    win = max(1, int(suav_s * sr))
    env = np.convolve(np.abs(mono), np.ones(win, np.float32) / win, mode="same")
    m = float(env.max()) if env.size else 0.0
    return env / m if m > 1e-9 else env


def _ducking(
    instrumental: np.ndarray, voc: np.ndarray, offset: int, sr: int, reducao_db: float = 3.5
) -> np.ndarray:
    """Sidechain-lite: atenua a base em até −`reducao_db` onde o vocal é forte."""
    out = instrumental.copy()
    n = min(voc.shape[1], out.shape[1] - offset)
    if n <= 0:
        return out
    env = _envelope(voc.mean(axis=0)[:n], sr)
    alpha = 1.0 - 10.0 ** (-abs(reducao_db) / 20.0)  # 1 sem vocal → 10^(-db/20) no pico
    out[:, offset : offset + n] *= (1.0 - alpha * env).astype(np.float32)
    return out


# --------------------------------------------------------------------------- #
# Detecção de frases (Fase 1a) — fronteiras de frase no stem vocal
# --------------------------------------------------------------------------- #
def _fundir_curtas(
    frases: list[tuple[float, float]], min_frase_s: float
) -> list[tuple[float, float]]:
    """Funde frases mais curtas que `min_frase_s` com a vizinha mais próxima."""
    mudou = True
    while mudou and len(frases) > 1:
        mudou = False
        for i, (ini, fim) in enumerate(frases):
            if fim - ini >= min_frase_s:
                continue
            if i == 0:
                j = 1
            elif i == len(frases) - 1:
                j = i - 1
            else:  # escolhe a vizinha com menor vão
                gap_prev = ini - frases[i - 1][1]
                gap_next = frases[i + 1][0] - fim
                j = i - 1 if gap_prev <= gap_next else i + 1
            a, b = min(i, j), max(i, j)
            novo = (min(frases[a][0], frases[b][0]), max(frases[a][1], frases[b][1]))
            frases = frases[:a] + [novo] + frases[b + 1 :]
            mudou = True
            break
    return frases


def _detectar_frases(
    voc: np.ndarray,
    sr: int,
    win_s: float = 0.05,
    silence_db: float = -40.0,
    min_gap_s: float = 0.30,
    min_frase_s: float = 0.50,
) -> list[tuple[float, float]]:
    """Fronteiras `(início, fim)` de cada frase vocal, em segundos do array recebido.

    RMS por janela de `win_s`; janela "ativa" quando o nível supera `silence_db`
    **relativo ao pico** (robusto a vazamento da separação, como `_melhor_janela_vocal`).
    Janelas ativas viram segmentos; um vão inativo de `>= min_gap_s` separa frases
    (vãos curtos são pontes dentro da frase). Frases `< min_frase_s` fundem com a vizinha.
    Silêncio total → `[]`.
    """
    y = np.asarray(voc, dtype=np.float32)
    if y.ndim == 2:
        y = y.mean(axis=0)
    w = max(1, int(win_s * sr))
    n = len(y) // w
    if n == 0:
        return []
    sq = np.square(y[: n * w].astype(np.float64)).reshape(n, w)
    rms = np.sqrt(sq.mean(axis=1))
    pico = float(rms.max()) if rms.size else 0.0
    if pico <= 1e-9:
        return []
    thr = pico * (10.0 ** (silence_db / 20.0))
    ativos = np.nonzero(rms > thr)[0]
    if ativos.size == 0:
        return []
    min_gap_win = max(1, int(round(min_gap_s / win_s)))
    segs: list[list[int]] = [[int(ativos[0]), int(ativos[0])]]
    for idx in ativos[1:]:
        idx = int(idx)
        if idx - segs[-1][1] - 1 >= min_gap_win:  # vão grande → nova frase
            segs.append([idx, idx])
        else:
            segs[-1][1] = idx
    frases = [(s * win_s, (e + 1) * win_s) for s, e in segs]
    return _fundir_curtas(frases, min_frase_s)


def sincronizar_frases(
    voc_recortado: np.ndarray,
    sr: int,
    plan: AlignmentPlan,
    base_downbeats: list[float],
    snap_tol_compassos: float = 0.5,
    bpm_base: float | None = None,
    win_s: float = 0.05,
    silence_db: float = -40.0,
    min_gap_s: float = 0.30,
    min_frase_s: float = 0.50,
) -> list[tuple[float, float]]:
    """Âncoras `(t_no_vocal_s, t_na_base_s)` para cada frase do vocal recortado.

    A 1ª frase entra exatamente em `plan.vocal_offset` (preserva a entrada
    escolhida por `align`). As demais vão para a posição derivada
    ``vocal_offset + (t_voc_i − t_voc_0)/bpm_ratio``, com **snap** ao downbeat mais
    próximo DENTRO de `plan.target_segment` quando estiver a `<= snap_tol_compassos`
    compassos; senão mantêm a posição derivada (não força encaixe que distorça).
    Sem downbeats ou sem frases detectadas → ``[]`` (render usa âncora única).
    """
    if not base_downbeats:
        return []
    frases = _detectar_frases(
        voc_recortado, sr, win_s, silence_db, min_gap_s, min_frase_s
    )
    if not frases:
        return []
    if bpm_base and bpm_base > 0:
        bar_s = 4 * 60.0 / bpm_base
    elif len(base_downbeats) >= 2:
        bar_s = float(np.median(np.diff(np.sort(base_downbeats))))
    else:
        bar_s = 2.0
    tol = snap_tol_compassos * bar_s
    seg = plan.target_segment
    db_seg = [d for d in base_downbeats if seg.start <= d < seg.end]
    ratio = plan.bpm_ratio if plan.bpm_ratio else 1.0
    t0 = frases[0][0]
    anchors: list[tuple[float, float]] = []
    for i, (t_voc, _fim) in enumerate(frases):
        if i == 0:
            anchors.append((t_voc, plan.vocal_offset))  # preserva a entrada do align
            continue
        derivado = plan.vocal_offset + (t_voc - t0) / ratio
        if db_seg:
            perto = min(db_seg, key=lambda d: abs(d - derivado))
            destino = perto if abs(perto - derivado) <= tol else derivado
        else:
            destino = derivado
        anchors.append((t_voc, destino))
    return anchors


def _render_frases(
    voc_full: np.ndarray, instrumental: np.ndarray, sr: int, plan: AlignmentPlan
) -> np.ndarray:
    """Render no modo frase-a-frase: cada frase do recorte vai ao seu downbeat-alvo.

    Usa o MESMO recorte do caminho de âncora única (`_recortar` por `vocal_in/dur`),
    fatia cada frase por `plan.phrase_anchors`, estica/transpõe com os MESMOS
    `bpm_ratio`/`pitch` globais e posiciona em `t_na_base`. Depois aplica a MESMA
    cadeia do caminho legado ao vocal montado: HPF → ganho por RMS → ducking → mix → norm.
    """
    voc = _recortar(voc_full, sr, plan.vocal_in, plan.vocal_dur)
    ch = max(instrumental.shape[0], voc.shape[0])
    instrumental = _to_channels(instrumental, ch)
    voc = _to_channels(voc, ch)

    anchors = plan.phrase_anchors or []
    n_rec = voc.shape[1]
    fronteiras = [int(round(t * sr)) for (t, _b) in anchors] + [n_rec]
    blocos: list[tuple[int, np.ndarray]] = []  # (offset_amostras, audio)
    for i, (_t, t_base) in enumerate(anchors):
        i0 = max(0, min(n_rec, fronteiras[i]))
        i1 = max(0, min(n_rec, fronteiras[i + 1]))
        if i1 <= i0:
            continue
        sub = np.ascontiguousarray(voc[:, i0:i1])
        sub = _stretch_pitch(sub, sr, plan.bpm_ratio, plan.pitch_shift_semitones)
        if sub.ndim == 1:
            sub = sub[np.newaxis, :]
        sub = _to_channels(sub, ch)
        blocos.append((max(0, int(round(t_base * sr))), sub))

    if not blocos:  # nenhuma frase posicionável → só o instrumental (degenerado)
        mix = instrumental.copy()
        pico = float(np.max(np.abs(mix))) if mix.size else 0.0
        return mix / pico if pico > 1.0 else mix

    fim_voc = max(off + b.shape[1] for off, b in blocos)
    n = max(instrumental.shape[1], fim_voc)
    voc_buf = np.zeros((ch, n), dtype=np.float32)
    for off, b in blocos:
        voc_buf[:, off : off + b.shape[1]] += b

    voc_buf = _passa_altas(voc_buf, sr)  # mesma cadeia do caminho legado
    ini = min(off for off, _ in blocos)
    rms_i = _rms(_passa_altas(instrumental[:, ini:fim_voc], sr))
    rms_v = _rms(voc_buf[:, ini:fim_voc])
    if rms_i > 1e-6 and rms_v > 1e-6:
        voc_buf = voc_buf * float(np.clip(rms_i / rms_v, 0.25, 4.0))

    instr2 = instrumental
    if n > instr2.shape[1]:
        instr2 = np.pad(instr2, ((0, 0), (0, n - instr2.shape[1])))
    for off, b in blocos:  # ducking sob cada frase
        instr2 = _ducking(instr2, voc_buf[:, off : off + b.shape[1]], off, sr)

    mix = np.zeros((ch, n), dtype=np.float32)
    mix[:, : instr2.shape[1]] += instr2
    mix += voc_buf
    pico = float(np.max(np.abs(mix))) if mix.size else 0.0
    if pico > 1.0:
        mix /= pico
    return mix


def render(
    vocal: np.ndarray,
    base_stems: dict[str, np.ndarray],
    sr: int,
    plan: AlignmentPlan,
) -> np.ndarray:
    """Mixa o vocal de A (recortado/esticado/transposto) sobre o INSTRUMENTAL da base.

    Instrumental da base = todos os stems de B menos o vocal de B
    (drums + bass + other). O vocal é recortado em [vocal_in, vocal_in+vocal_dur)
    (tempo de A) antes do stretch e tem o ganho casado por RMS com o trecho do
    instrumental onde entra. Retorna o mashup (canais, amostras) float32.
    """
    instr_parts = [v for k, v in base_stems.items() if k != "vocals"]
    instrumental = np.sum(instr_parts, axis=0).astype(np.float32)
    if instrumental.ndim == 1:
        instrumental = instrumental[np.newaxis, :]

    voc = np.asarray(vocal, dtype=np.float32)
    if voc.ndim == 1:
        voc = voc[np.newaxis, :]

    if plan.phrase_anchors:  # modo frase-a-frase (Fase 1a); vazio/None → âncora única
        return _render_frases(voc, instrumental, sr, plan)

    voc = _recortar(voc, sr, plan.vocal_in, plan.vocal_dur)
    voc = _stretch_pitch(voc, sr, plan.bpm_ratio, plan.pitch_shift_semitones)
    if voc.ndim == 1:
        voc = voc[np.newaxis, :]

    ch = max(instrumental.shape[0], voc.shape[0])
    instrumental = _to_channels(instrumental, ch)
    voc = _to_channels(voc, ch)

    offset = max(0, int(round(plan.vocal_offset * sr)))

    # corte de graves no vocal: não disputa a região do baixo de B (menos "barro")
    voc = _passa_altas(voc, sr)

    # ganho: casa o RMS do vocal com a energia da base NA BANDA DO VOCAL (a base
    # também passa-altas, p/ o baixo não dominar a referência e estourar o vocal),
    # vocal no nível da base. clamp evita amplificar bleed da separação.
    trecho = instrumental[:, offset : offset + voc.shape[1]]
    rms_i, rms_v = _rms(_passa_altas(trecho, sr)), _rms(voc)
    if rms_i > 1e-6 and rms_v > 1e-6:
        voc = voc * float(np.clip(rms_i / rms_v, 0.25, 4.0))

    # ducking: abre espaço pro vocal atenuando a base sob ele (sidechain-lite)
    instrumental = _ducking(instrumental, voc, offset, sr)

    n = max(instrumental.shape[1], offset + voc.shape[1])
    mix = np.zeros((ch, n), dtype=np.float32)
    mix[:, : instrumental.shape[1]] += instrumental
    mix[:, offset : offset + voc.shape[1]] += voc

    pico = float(np.max(np.abs(mix))) if mix.size else 0.0
    if pico > 1.0:  # evita clipping mantendo o ganho relativo
        mix /= pico
    return mix
