"""Testes do alinhamento estrutura-aware (H1) — núcleo do motor de mashup (P2).

Tudo 100% sintético: nenhum áudio é lido. `Segment`/`TrackAnalysis` são montados na mão
e as métricas de áudio por segmento (`vocal_fit_rel`) são injetadas como se viessem do
pipeline (que computa RMS de drums+bass e headroom da banda vocal).

Critério-fonte: specs/alinhamento-estrutura-aware.md (Decisão do agente blend-mashup, FECHADA).
"""
from __future__ import annotations

import pytest

from blend.alignment import (
    ParamsSecao,
    _ancorar,
    align,
    escolher_secao_groove,
    metricas_por_segmento_de_audio,
)
from blend.types import AlignmentPlan, Segment, TrackAnalysis


# --------------------------------------------------------------------------- #
# Helpers de construção de cenários sintéticos
# --------------------------------------------------------------------------- #
def _downbeats(bpm: float, dur: float) -> list[float]:
    """Downbeats (1 por compasso de 4 tempos) cobrindo [0, dur)."""
    bar = 4 * 60.0 / bpm
    t = 0.0
    out: list[float] = []
    while t < dur:
        out.append(round(t, 6))
        t += bar
    return out


def _metricas(*vals: float) -> list[dict]:
    """Lista de métricas por segmento com vocal_fit_rel dado."""
    return [{"vocal_fit_rel": v} for v in vals]


# --------------------------------------------------------------------------- #
# 1. Score escolhe a seção certa
# --------------------------------------------------------------------------- #
def test_score_escolhe_secao_de_groove_com_maior_vocal_fit():
    # bpm 128 -> bar = 1.875s; min_segment_bars=8 -> dur_min = 15s
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),       # borda
        Segment(16.0, 48.0, "verse"),      # groove, dur 32s, vocal_fit alto
        Segment(48.0, 80.0, "chorus"),     # groove, dur 32s, vocal_fit menor
        Segment(80.0, 96.0, "outro"),      # borda
    ]
    db = _downbeats(bpm, 96.0)
    # métricas alinhadas a segs: verse tem o maior vocal_fit
    metr = _metricas(0.1, 0.9, 0.5, 0.05)
    seg, nivel = escolher_secao_groove(segs, db, bpm, metr)
    assert nivel == 0
    assert seg.label == "verse"
    assert seg.start == 16.0


def test_secoes_borda_nunca_vencem_mesmo_com_vocal_fit_alto():
    bpm = 128.0
    segs = [
        Segment(0.0, 40.0, "intro"),       # borda longa com fit altíssimo
        Segment(40.0, 72.0, "verse"),      # groove
    ]
    db = _downbeats(bpm, 72.0)
    metr = _metricas(0.99, 0.4)
    seg, nivel = escolher_secao_groove(segs, db, bpm, metr)
    assert nivel == 0
    assert seg.label == "verse"


# --------------------------------------------------------------------------- #
# 2. Bônus chorus/drop
# --------------------------------------------------------------------------- #
def test_bonus_chorus_drop_inverte_quando_resto_quase_empata():
    # chorus tem fit um pouco maior; sem o bônus o verse (mais recente) ainda
    # venceria, mas o +0.05 do rótulo chorus vira a decisão.
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "verse"),    # rank recência mais alto, sem bônus
        Segment(48.0, 80.0, "chorus"),   # rank recência mais baixo, fit maior, +bônus
    ]
    db = _downbeats(bpm, 80.0)
    # n=2 grooves -> recência verse=1.0, chorus=0.0 (gap 0.25 no score).
    # Para o chorus vencer precisa compensar 0.25 com fit + bônus:
    # verse: 0.45*0.1 + 0.25*1.0 = 0.295
    # chorus: 0.45*0.95 + 0.25*0.0 + 0.05 = 0.4775 -> chorus vence.
    metr = _metricas(0.05, 0.1, 0.95)
    seg, nivel = escolher_secao_groove(segs, db, bpm, metr)
    assert nivel == 0
    assert seg.label == "chorus"


def test_bonus_e_o_fiel_da_balanca_isolado_via_params():
    # Isola o efeito do bônus: mesmo cenário, com e sem bonus_label.
    # verse (rank0, rec=1.0) vs chorus (rank1, rec=0.0). Calibramos o fit do
    # chorus para que SEM bônus o verse vença por pouco, e COM bônus o chorus
    # ultrapasse — provando que o termo de bônus é o fiel da balança.
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "verse"),
        Segment(48.0, 80.0, "chorus"),
    ]
    db = _downbeats(bpm, 80.0)
    # verse:  0.45*0.40 + 0.25*1.0 + 0.20*1.0 = 0.18+0.25+0.20 = 0.630
    # chorus: 0.45*0.84 + 0.25*0.0 + 0.20*1.0 = 0.378+0.20    = 0.578  (sem bônus -> verse)
    #         +0.05 (com bônus) = 0.628 ... ainda < 0.630? ajustamos fit p/ 0.86
    # chorus: 0.45*0.86 + 0.20 = 0.387+0.20 = 0.587; +0.05 = 0.637 > 0.630 (verse)
    metr = _metricas(0.1, 0.40, 0.86)
    sem_bonus = ParamsSecao(bonus_label=0.0)
    com_bonus = ParamsSecao()  # bonus_label=0.05
    seg_sem, _ = escolher_secao_groove(segs, db, bpm, metr, sem_bonus)
    seg_com, _ = escolher_secao_groove(segs, db, bpm, metr, com_bonus)
    # Atenção ao score_eps (0.02): sem bônus a diferença verse-chorus é
    # 0.630-0.587=0.043 > eps, então não há empate e o verse vence limpo.
    assert seg_sem.label == "verse"
    assert seg_com.label == "chorus"


def test_bonus_nao_inverte_quando_vocal_fit_domina():
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "verse"),    # fit muito maior
        Segment(48.0, 80.0, "chorus"),   # bônus mas fit baixo
    ]
    db = _downbeats(bpm, 80.0)
    metr = _metricas(0.1, 0.95, 0.2)
    seg, _ = escolher_secao_groove(segs, db, bpm, metr)
    assert seg.label == "verse"


# --------------------------------------------------------------------------- #
# 3. Empates determinísticos
# --------------------------------------------------------------------------- #
def test_empate_resolve_por_maior_vocal_fit():
    # 1º critério do tie-break (spec passo 4): com |Δscore| < score_eps, o
    # maior vocal_fit decide. Para exercitar ESSE critério de verdade (e não
    # a recência), isolamos os pesos: score = só duração. Dois verses de mesma
    # duração -> empate EXATO (Δscore=0) -> resta o vocal_fit como desempate.
    # O fit maior está no SEGUNDO segmento (start=30), que perderia por menor
    # recência/start; provar que ele vence isola o critério de maior fit.
    # Rótulos groove DISTINTOS e SEM bônus (verse/inst) para não fundir
    # adjacentes nem deixar o bônus de chorus/drop quebrar o empate exato.
    bpm = 120.0
    segs = [
        Segment(0.0, 30.0, "verse"),    # fit menor, start menor (venceria por start)
        Segment(30.0, 60.0, "inst"),    # fit MAIOR -> deve vencer o empate
    ]
    db = _downbeats(bpm, 60.0)
    params = ParamsSecao(
        w_vocalfit=0.0, w_recencia=0.0, w_duracao=1.0, w_repeticao=0.0
    )
    metr = _metricas(0.50, 0.80)
    seg, _ = escolher_secao_groove(segs, db, bpm, metr, params)
    # Empate exato em score (mesma duração); o maior vocal_fit (segundo) vence.
    assert seg.start == 30.0
    # determinismo: repetir dá o mesmo resultado
    seg2, _ = escolher_secao_groove(segs, db, bpm, metr, params)
    assert seg.start == seg2.start


def test_empate_total_resolve_por_menor_start():
    # vocal_fit idêntico, duração idêntica, mesmo rótulo -> resta menor start.
    bpm = 120.0
    segs = [
        Segment(0.0, 30.0, "verse"),
        Segment(30.0, 60.0, "verse"),
    ]
    db = _downbeats(bpm, 60.0)
    metr = _metricas(0.5, 0.5)
    seg, _ = escolher_secao_groove(segs, db, bpm, metr)
    # recência favorece a primeira (start 0.0); empate em fit e duração.
    assert seg.start == 0.0


# --------------------------------------------------------------------------- #
# 4. Paridade determinística com métricas ausentes (None)
# --------------------------------------------------------------------------- #
def test_paridade_metricas_none_reproduzivel_e_redistribui_peso():
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "verse"),    # groove recente e longa
        Segment(48.0, 64.0, "chorus"),   # groove mais curta, mais nova
    ]
    db = _downbeats(bpm, 64.0)
    # Sem métricas: o termo vocal_fit some e o critério vira
    # "maior seção de groove recente". Deve ser reproduzível.
    r1 = escolher_secao_groove(segs, db, bpm, None)
    r2 = escolher_secao_groove(segs, db, bpm, None)
    assert r1[0].start == r2[0].start
    assert r1[1] == r2[1] == 0
    # Com peso redistribuído (recência+duração+repetição+bônus), o verse
    # (mais longo e mais recente após intro) deve vencer o chorus curto.
    assert r1[0].label == "verse"


def test_metricas_none_nao_levanta_excecao_e_escolhe_groove():
    bpm = 124.0
    segs = [
        Segment(0.0, 20.0, "intro"),
        Segment(20.0, 60.0, "drop"),
        Segment(60.0, 90.0, "verse"),
    ]
    db = _downbeats(bpm, 90.0)
    seg, nivel = escolher_secao_groove(segs, db, bpm, None)
    assert nivel == 0
    assert seg.label in {"drop", "verse"}


# --------------------------------------------------------------------------- #
# 5. Cada nível de fallback
# --------------------------------------------------------------------------- #
def test_fallback_nivel_1_sem_candidata_groove():
    # Só rótulos fora de groove_labels mas não-borda (ex.: 'theme'/'section').
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "section"),   # não-borda, não-groove
        Segment(48.0, 80.0, "section"),   # idem
    ]
    db = _downbeats(bpm, 80.0)
    metr = _metricas(0.1, 0.8, 0.4)
    seg, nivel = escolher_secao_groove(segs, db, bpm, metr)
    assert nivel == 1
    assert seg.label == "section"
    assert seg.start in {16.0, 48.0}


def test_fallback_nivel_2_so_segmentos_curtos():
    # Grooves existem mas todos < dur_min_s -> relaxa para dur_min/2.
    bpm = 128.0  # bar=1.875; dur_min=15s; dur_min/2=7.5s
    segs = [
        Segment(0.0, 6.0, "intro"),
        Segment(6.0, 16.0, "verse"),    # 10s: < 15 mas >= 7.5
        Segment(16.0, 24.0, "chorus"),  # 8s
    ]
    db = _downbeats(bpm, 24.0)
    metr = _metricas(0.1, 0.7, 0.6)
    seg, nivel = escolher_secao_groove(segs, db, bpm, metr)
    assert nivel == 2
    assert seg.label in {"verse", "chorus"}


def test_fallback_nivel_3_tudo_unknown_ou_borda():
    # Sem nada aproveitável por rótulo/duração -> janela deslizante.
    bpm = 120.0
    segs = [
        Segment(0.0, 30.0, "unknown"),
        Segment(30.0, 60.0, "unknown"),
    ]
    db = _downbeats(bpm, 60.0)
    # unknown não está em groove_labels nem em edge_labels; mas o nível 1/2
    # tratam não-borda. Para forçar nível 3, deixamos sem métricas e segmentos
    # que o pipeline considera vazios de groove: usamos segments só de borda.
    segs_borda = [
        Segment(0.0, 30.0, "intro"),
        Segment(30.0, 60.0, "outro"),
    ]
    seg, nivel = escolher_secao_groove(segs_borda, db, bpm, None)
    assert nivel == 3
    assert seg.end > seg.start


def test_fallback_nivel_3_segments_vazio():
    bpm = 120.0
    db = _downbeats(bpm, 60.0)
    seg, nivel = escolher_secao_groove([], db, bpm, None)
    assert nivel == 3
    assert seg.end > seg.start


def test_fallback_nivel_4_sem_downbeats():
    bpm = 120.0
    segs = [
        Segment(0.0, 30.0, "intro"),
        Segment(30.0, 60.0, "outro"),
    ]
    seg, nivel = escolher_secao_groove(segs, [], bpm, None)
    assert nivel == 4
    assert seg.start == 0.0


def test_fallback_nivel_4_bpm_invalido():
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "verse"),
    ]
    db = [0.0, 1.0, 2.0]
    seg, nivel = escolher_secao_groove(segs, db, 0.0, _metricas(0.1, 0.9))
    assert nivel == 4
    seg2, nivel2 = escolher_secao_groove(segs, db, None, _metricas(0.1, 0.9))
    assert nivel2 == 4


def test_guarda_segmento_invalido_end_menor_que_start():
    bpm = 128.0
    segs = [Segment(20.0, 10.0, "verse")]  # end <= start
    db = _downbeats(bpm, 60.0)
    seg, nivel = escolher_secao_groove(segs, db, bpm, _metricas(0.9))
    # Cai no fallback (não levanta exceção).
    assert nivel >= 1


# --------------------------------------------------------------------------- #
# 6. Fusão de segmentos adjacentes de mesmo rótulo
# --------------------------------------------------------------------------- #
def test_fusao_de_segmentos_adjacentes_mesmo_rotulo():
    # allin1 fragmenta: 4 'verse' de 8s viram 1 de 32s -> passa no dur_min.
    bpm = 128.0  # dur_min = 15s
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 24.0, "verse"),
        Segment(24.0, 32.0, "verse"),
        Segment(32.0, 40.0, "verse"),
        Segment(40.0, 48.0, "verse"),
    ]
    db = _downbeats(bpm, 48.0)
    # Sem fusão, cada verse (8s) < 15s -> nível 2. Com fusão (32s) -> nível 0.
    seg, nivel = escolher_secao_groove(segs, db, bpm, None)
    assert nivel == 0
    assert seg.label == "verse"
    assert seg.start == 16.0
    assert seg.end == 48.0


def test_fusao_respeita_sinonimos_de_rotulo():
    # 'refrão' e 'chorus' normalizam para o mesmo rótulo e devem fundir.
    bpm = 120.0  # bar=2s; dur_min=16s
    segs = [
        Segment(0.0, 10.0, "chorus"),
        Segment(10.0, 24.0, "refrão"),
    ]
    db = _downbeats(bpm, 24.0)
    seg, nivel = escolher_secao_groove(segs, db, bpm, None)
    assert nivel == 0
    assert seg.start == 0.0
    assert seg.end == 24.0


# --------------------------------------------------------------------------- #
# 7. align() — baseline vs proposto
# --------------------------------------------------------------------------- #
def _track(bpm, dur, segs=None, key="8A"):
    return TrackAnalysis(
        path="x.wav",
        sr=44100,
        bpm=bpm,
        beats=[],
        downbeats=_downbeats(bpm, dur),
        segments=segs or [],
        key_camelot=key,
    )


def test_baseline_usa_primeiro_downbeat_e_secao_sintetica():
    base = _track(128.0, 96.0, segs=[
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 80.0, "verse"),
        Segment(80.0, 96.0, "outro"),
    ])
    vocal = _track(128.0, 60.0, key="8A")
    plan = align(vocal, base, mode="baseline")
    assert isinstance(plan, AlignmentPlan)
    assert plan.mode == "baseline"
    assert plan.nivel_fallback == 0
    assert plan.vocal_offset == base.downbeats[0]
    # seção sintética cobre a faixa toda
    assert plan.target_segment.start == 0.0
    assert plan.target_segment.end >= 96.0 - 1e-6


def test_baseline_sem_downbeats_offset_zero():
    base = _track(128.0, 96.0)
    base.downbeats = []
    vocal = _track(128.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    assert plan.vocal_offset == 0.0


def test_proposto_escolhe_secao_e_ancora_no_downbeat_da_secao():
    base = _track(128.0, 96.0, segs=[
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 80.0, "verse"),
        Segment(80.0, 96.0, "outro"),
    ])
    vocal = _track(128.0, 60.0)
    metr = _metricas(0.1, 0.9, 0.05)
    plan = align(vocal, base, mode="proposto", metricas_por_segmento=metr)
    assert plan.mode == "proposto"
    assert plan.target_segment.label == "verse"
    # offset cai dentro do verse (>= 16.0)
    assert plan.vocal_offset >= 16.0
    assert plan.vocal_offset < 80.0


def test_proposto_ancoragem_mais_um_compasso_quando_secao_longa():
    # verse longa (>= min_segment_bars+1) -> pula +1 compasso da fronteira.
    bpm = 128.0
    bar = 4 * 60.0 / bpm  # 1.875
    base = _track(bpm, 96.0, segs=[
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 80.0, "verse"),   # 64s = ~34 compassos, bem longa
        Segment(80.0, 96.0, "outro"),
    ])
    vocal = _track(bpm, 60.0)
    metr = _metricas(0.1, 0.9, 0.05)
    plan = align(vocal, base, mode="proposto", metricas_por_segmento=metr)
    # 1º downbeat >= 16.0 é o de índice round(16/bar). +1 compasso.
    dbs = base.downbeats
    primeiro = next(d for d in dbs if d >= 16.0 - 1e-9)
    assert plan.vocal_offset == pytest.approx(primeiro + bar, abs=1e-6)


def test_ancorar_downbeat_mais_proximo_quando_nenhum_cai_na_secao():
    # Ramo "downbeat mais próximo do start" do _ancorar: nenhum downbeat dentro
    # da seção [50,70] (db em [0,10,20,100]). Ancora no mais próximo do start
    # (20.0) e NÃO soma +1 compasso, mesmo a seção sendo longa — somar afastaria
    # ainda mais o vocal da seção real (correção do finding adversarial MEDIA).
    bpm = 120.0  # bar=2s; (min_segment_bars+1)*bar=18s -> seção de 20s é "longa"
    bar = 4 * 60.0 / bpm
    target = Segment(50.0, 70.0, "verse")  # 20s, longa o bastante p/ +1 compasso
    downbeats = [0.0, 10.0, 20.0, 100.0]   # nenhum em [50,70]
    offset = _ancorar(target, downbeats, bar, ParamsSecao())
    # mais próximo do start (50) é 20.0; SEM +bar (não está na fronteira da seção)
    assert offset == pytest.approx(20.0, abs=1e-6)


def test_ancorar_mais_um_compasso_so_quando_ancora_dentro_da_secao():
    # Espelho do teste acima: quando HÁ downbeat dentro da seção e ela é longa,
    # aí sim o +1 compasso se aplica (fronteira real).
    bpm = 120.0
    bar = 4 * 60.0 / bpm  # 2s
    target = Segment(50.0, 70.0, "verse")
    downbeats = [0.0, 10.0, 20.0, 50.0, 52.0, 54.0]  # 50.0 cai na seção
    offset = _ancorar(target, downbeats, bar, ParamsSecao())
    assert offset == pytest.approx(50.0 + bar, abs=1e-6)


def test_proposto_secao_curta_nao_adiciona_compasso():
    bpm = 120.0  # bar=2s; min_segment_bars=8 -> dur_min=16s; (min_bars+1)*bar=18s
    base = _track(bpm, 80.0, segs=[
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 33.0, "verse"),   # 17s -> >= dur_min(16) mas < 18s (não soma compasso)
        Segment(33.0, 80.0, "outro"),
    ])
    vocal = _track(bpm, 40.0)
    metr = _metricas(0.1, 0.9, 0.05)
    plan = align(vocal, base, mode="proposto", metricas_por_segmento=metr)
    primeiro = next(d for d in base.downbeats if d >= 16.0 - 1e-9)
    assert plan.vocal_offset == pytest.approx(primeiro, abs=1e-6)


def test_baseline_e_proposto_diferem_so_em_secao_e_ancoragem():
    base = _track(128.0, 96.0, segs=[
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 80.0, "verse"),
        Segment(80.0, 96.0, "outro"),
    ])
    vocal = _track(128.0, 60.0)
    metr = _metricas(0.1, 0.9, 0.05)
    pb = align(vocal, base, mode="baseline")
    pp = align(vocal, base, mode="proposto", metricas_por_segmento=metr)
    # mesmo stretch e mesmo pitch (resto igual = teste justo de H1)
    assert pb.bpm_ratio == pp.bpm_ratio
    assert pb.pitch_shift_semitones == pp.pitch_shift_semitones
    # diferem em seção e offset
    assert pb.target_segment.label != pp.target_segment.label
    assert pb.vocal_offset != pp.vocal_offset


def test_proposto_grava_nivel_fallback_no_plano():
    base = _track(128.0, 96.0)  # sem segments e sem métricas
    vocal = _track(128.0, 60.0)
    plan = align(vocal, base, mode="proposto")
    assert plan.nivel_fallback >= 1


def test_proposto_fallback_nivel_4_equivale_ao_baseline():
    # sem downbeats e sem segments -> nível 4 == baseline.
    base = _track(128.0, 96.0)
    base.downbeats = []
    vocal = _track(128.0, 60.0)
    pp = align(vocal, base, mode="proposto")
    assert pp.nivel_fallback == 4
    assert pp.vocal_offset == 0.0


# --------------------------------------------------------------------------- #
# 8. bpm_ratio — half/double-time
# --------------------------------------------------------------------------- #
def test_bpm_ratio_fator_1_quando_bpm_proximos():
    base = _track(128.0, 96.0)
    vocal = _track(127.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    # f=1: ratio = 128/127 ~ 1.008
    assert plan.bpm_ratio == pytest.approx(128.0 / 127.0, abs=1e-6)


def test_bpm_ratio_double_time_para_vocal_lento():
    # vocal 64, base 128 -> f=2 minimiza stretch; ratio = 128/(2*64)=1.0
    base = _track(128.0, 96.0)
    vocal = _track(64.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    assert plan.bpm_ratio == pytest.approx(1.0, abs=1e-6)


def test_bpm_ratio_half_time_para_vocal_rapido():
    # vocal 150, base 126 -> f=0.5: 0.5*150=75 (longe); f=1: 150 (longe);
    # melhor f que aproxima 126: f=1 dá 150 (ratio .84), f=0.5 dá 75 (ratio 1.68).
    # f=1 minimiza |stretch-1|? |.84-1|=.16 vs |1.68-1|=.68 -> f=1.
    base = _track(126.0, 96.0)
    vocal = _track(150.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    assert plan.bpm_ratio == pytest.approx(126.0 / 150.0, abs=1e-6)


def test_bpm_ratio_half_time_quando_vocal_muito_rapido():
    # vocal 250, base 128 -> f=0.5: 125 (perto de 128) ratio=128/125=1.024
    base = _track(128.0, 96.0)
    vocal = _track(250.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    assert plan.bpm_ratio == pytest.approx(128.0 / (0.5 * 250.0), abs=1e-6)


# --------------------------------------------------------------------------- #
# 9. pitch_shift — placeholder (depende de H2/Camelot, fora desta spec)
# --------------------------------------------------------------------------- #
def test_pitch_shift_zero_placeholder():
    base = _track(128.0, 96.0)
    vocal = _track(128.0, 60.0)
    plan = align(vocal, base, mode="baseline")
    assert plan.pitch_shift_semitones == 0.0


# --------------------------------------------------------------------------- #
# 10. helper de áudio é stub (depende de numpy/stems — P1/pipeline)
# --------------------------------------------------------------------------- #
def test_helper_de_audio_e_stub():
    with pytest.raises(NotImplementedError):
        metricas_por_segmento_de_audio(None, None, None, None)


# --------------------------------------------------------------------------- #
# 11. params customizáveis
# --------------------------------------------------------------------------- #
def test_params_customizado_groove_labels():
    bpm = 128.0
    segs = [
        Segment(0.0, 16.0, "intro"),
        Segment(16.0, 48.0, "section"),  # só vira groove com params custom
    ]
    db = _downbeats(bpm, 48.0)
    params = ParamsSecao(groove_labels=frozenset({"section"}))
    seg, nivel = escolher_secao_groove(segs, db, bpm, None, params)
    assert nivel == 0
    assert seg.label == "section"
