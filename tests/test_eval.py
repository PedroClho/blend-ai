"""Testes do experimento subjetivo (P4): helpers de estímulo + estatística.

Tudo puro (sem GPU/áudio real). Ver `specs/experimento-subjetivo.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from eval.analise import (  # noqa: E402
    ab_de_df,
    binomial_ab,
    h1_de_df,
    h2_de_df,
    spearman_h2,
    wilcoxon_h1,
)
from eval.estimulos import (  # noqa: E402
    casar_arquivo,
    excerto,
    normalizar_rms,
    nucleo_titulo,
    selecionar_pares,
)

SR = 44100


# --------------------------------------------------------------------------- #
# estímulos: casamento + seleção
# --------------------------------------------------------------------------- #
def test_nucleo_titulo():
    assert nucleo_titulo("Stop Talking (Extended Mix) [Hellbent]") == "Stop Talking"
    assert (
        nucleo_titulo("Trust Me feat. Ben Westbeech (Original Mix) [Solid Grooves]")
        == "Trust Me feat. Ben Westbeech"
    )


def test_casar_arquivo(tmp_path):
    (tmp_path / "Joshwa - Work Your Body (Extended Mix) [Catch Release]_pn.mp3").write_bytes(b"x")
    (tmp_path / "ATLAC - Stop Talking (Extended Mix) [Hellbent]_pn.mp3").write_bytes(b"x")
    p = casar_arquivo({"nucleo": "Work Your Body"}, dir_bases=tmp_path)
    assert p is not None and "Work Your Body" in p.name
    assert casar_arquivo({"nucleo": "Inexistente"}, dir_bases=tmp_path) is None


def test_selecionar_pares_respeita_restricoes():
    faixas = [
        {"num": 1, "nucleo": "t1", "bpm": 128.0, "camelot": "8A", "titulo": "t1"},
        {"num": 2, "nucleo": "t2", "bpm": 129.0, "camelot": "9A", "titulo": "t2"},
        {"num": 3, "nucleo": "t3", "bpm": 130.0, "camelot": "5A", "titulo": "t3"},
        {"num": 4, "nucleo": "t4", "bpm": 131.0, "camelot": "8B", "titulo": "t4"},
        {"num": 5, "nucleo": "t5", "bpm": 140.0, "camelot": "1A", "titulo": "t5"},  # BPM longe
    ]
    pares = selecionar_pares(faixas, n=4, max_dbpm=3.0, cap_por_vocal=2, so_com_arquivo=False)
    assert 1 <= len(pares) <= 4
    chaves, uso = set(), {}
    for par in pares:
        a, b = par["a"], par["b"]
        assert abs(a["bpm"] - b["bpm"]) <= 3.0
        assert a["num"] != b["num"]
        chave = (a["num"], b["num"])
        assert chave not in chaves  # sem pares repetidos
        chaves.add(chave)
        uso[a["num"]] = uso.get(a["num"], 0) + 1
    assert all(v <= 2 for v in uso.values())  # cap por vocal
    nums = {par["a"]["num"] for par in pares} | {par["b"]["num"] for par in pares}
    assert 5 not in nums  # t5 (140 BPM) dista >3 de todas → fora


# --------------------------------------------------------------------------- #
# estímulos: excerto + normalização
# --------------------------------------------------------------------------- #
def test_excerto_janela_e_clamp():
    y = np.ones((2, 10 * SR), dtype=np.float32)
    ex = excerto(y, SR, centro_s=5.0, dur_s=2.0, lead_in_s=1.0)  # [4s, 6s)
    assert ex.shape[0] == 2 and abs(ex.shape[1] - 2 * SR) <= 2
    ex_borda = excerto(y, SR, centro_s=0.5, dur_s=2.0, lead_in_s=1.0)  # clampa no 0
    assert ex_borda.shape[1] <= 2 * SR


def test_normalizar_rms_atinge_alvo():
    rng = np.random.default_rng(0)
    y = (0.01 * rng.standard_normal((2, SR))).astype(np.float32)  # bem abaixo do teto
    out = normalizar_rms(y, alvo_dbfs=-20.0, teto=0.97)
    rms = float(np.sqrt(np.mean(out**2)))
    assert abs(rms - 0.1) < 0.02  # -20 dBFS = 0.1 linear


def test_normalizar_rms_silencio_nao_quebra():
    assert np.all(normalizar_rms(np.zeros((1, 1000), dtype=np.float32)) == 0)


# --------------------------------------------------------------------------- #
# estatística: H1 / H2 / A/B
# --------------------------------------------------------------------------- #
def test_wilcoxon_h1_proposto_melhor():
    r = wilcoxon_h1([4, 5, 4, 5, 4, 5], [2, 3, 2, 3, 2, 3])
    assert r["media_proposto"] > r["media_baseline"]
    assert r["rank_biserial"] == 1.0
    assert r["n_pares"] == 6
    assert r["p"] is not None and r["p"] < 0.05


def test_wilcoxon_h1_empate_total():
    r = wilcoxon_h1([3, 3, 3], [3, 3, 3])
    assert r["rank_biserial"] == 0.0
    assert r["p"] is None  # sem diferenças não-nulas


def test_spearman_h2_monotonico():
    r = spearman_h2([0.2, 0.4, 0.6, 0.8], [2.0, 3.0, 4.0, 5.0], n_boot=200)
    assert r["n"] == 4 and r["rho"] > 0.9
    assert -1.0 <= r["ci95"][0] <= r["ci95"][1] <= 1.0


def test_spearman_h2_n_pequeno():
    r = spearman_h2([0.1, 0.2], [1.0, 2.0])
    assert r["n"] == 2 and np.isnan(r["rho"])


def test_binomial_ab():
    assert binomial_ab(9, 10)["p"] < 0.05
    assert abs(binomial_ab(5, 10)["p"] - 1.0) < 1e-9
    assert np.isnan(binomial_ab(0, 0)["p"])


def test_loaders_h1_h2_ab():
    import pandas as pd

    gab = pd.DataFrame(
        [
            {"estimulo_id": "e1", "par_id": "par01", "condicao": "baseline", "score": 0.3, "camelot_dist": 1},
            {"estimulo_id": "e2", "par_id": "par01", "condicao": "proposto", "score": 0.3, "camelot_dist": 1},
            {"estimulo_id": "e3", "par_id": "par02", "condicao": "baseline", "score": 0.6, "camelot_dist": 3},
            {"estimulo_id": "e4", "par_id": "par02", "condicao": "proposto", "score": 0.6, "camelot_dist": 3},
            {"estimulo_id": "e5", "par_id": "par03", "condicao": "baseline", "score": 0.9, "camelot_dist": 5},
            {"estimulo_id": "e6", "par_id": "par03", "condicao": "proposto", "score": 0.9, "camelot_dist": 5},
        ]
    )
    resp = pd.DataFrame(
        [
            {"avaliador": "a", "estimulo_id": "e1", "qualidade": 2, "musicalidade": 2, "artefatos": 3},
            {"avaliador": "a", "estimulo_id": "e2", "qualidade": 3, "musicalidade": 4, "artefatos": 4},
            {"avaliador": "a", "estimulo_id": "e3", "qualidade": 3, "musicalidade": 3, "artefatos": 3},
            {"avaliador": "a", "estimulo_id": "e4", "qualidade": 4, "musicalidade": 5, "artefatos": 4},
            {"avaliador": "a", "estimulo_id": "e5", "qualidade": 4, "musicalidade": 3, "artefatos": 4},
            {"avaliador": "a", "estimulo_id": "e6", "qualidade": 5, "musicalidade": 5, "artefatos": 5},
        ]
    )
    df = resp.merge(gab, on="estimulo_id")

    h1 = h1_de_df(df, "musicalidade")
    assert h1["media_proposto"] > h1["media_baseline"] and h1["rank_biserial"] > 0

    h2 = h2_de_df(df, gab, eixo="qualidade", condicao="proposto")
    assert h2["n"] == 3 and h2["rho"] > 0.9

    ab = pd.DataFrame(
        [
            {"avaliador": "a", "par_id": "par01", "id_preferido": "e2"},  # proposto
            {"avaliador": "a", "par_id": "par02", "id_preferido": "e4"},  # proposto
            {"avaliador": "a", "par_id": "par03", "id_preferido": "e5"},  # baseline
        ]
    )
    assert ab_de_df(ab, gab)["prefere_proposto"] == 2
