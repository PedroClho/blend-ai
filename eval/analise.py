"""Análise estatística do experimento subjetivo (P4): H1, H2, H3.

Funções estatísticas PURAS (arrays) + carregadores (pandas) + CLI. Lê o gabarito
(condição↔ID) e as respostas do painel. Ver `specs/experimento-subjetivo.md`.

Uso: python eval/analise.py [--gabarito ...] [--respostas ...] [--ab ...]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
DIR_EXP = ROOT / "data" / "experimento"


# --------------------------------------------------------------------------- #
# Estatística pura
# --------------------------------------------------------------------------- #
def _rank_biserial(diffs: np.ndarray) -> float:
    """Rank-biserial pareado em [-1,1]: + favorece o 1º braço (proposto)."""
    d = np.asarray([x for x in diffs if x != 0], dtype=float)
    if d.size == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    w_pos, w_neg = ranks[d > 0].sum(), ranks[d < 0].sum()
    tot = w_pos + w_neg
    return float((w_pos - w_neg) / tot) if tot > 0 else 0.0


def wilcoxon_h1(prop: np.ndarray, base: np.ndarray) -> dict:
    """Wilcoxon pareado proposto vs baseline (H1) + tamanho de efeito."""
    prop, base = np.asarray(prop, float), np.asarray(base, float)
    diffs = prop - base
    out: dict = {
        "n_pares": int(len(diffs)),
        "n_nao_empate": int(np.count_nonzero(diffs)),
        "media_proposto": float(prop.mean()) if prop.size else float("nan"),
        "media_baseline": float(base.mean()) if base.size else float("nan"),
        "rank_biserial": _rank_biserial(diffs),
        "stat": None,
        "p": None,
    }
    if out["n_nao_empate"] >= 1:
        try:
            w = stats.wilcoxon(prop, base, zero_method="wilcox", alternative="two-sided")
            out["stat"], out["p"] = float(w.statistic), float(w.pvalue)
        except ValueError as e:
            out["erro"] = str(e)
    return out


def spearman_h2(
    scores: np.ndarray, notas: np.ndarray, n_boot: int = 2000, seed: int = 7
) -> dict:
    """Spearman score×nota (H2) + IC95% por bootstrap (N pequeno: reportar `n`)."""
    scores, notas = np.asarray(scores, float), np.asarray(notas, float)
    n = len(scores)
    if n < 3:
        return {"n": n, "rho": float("nan"), "p": float("nan"), "ci95": (float("nan"),) * 2}
    rho, p = stats.spearmanr(scores, notas)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if np.unique(scores[idx]).size < 2 or np.unique(notas[idx]).size < 2:
            continue
        r, _ = stats.spearmanr(scores[idx], notas[idx])
        if not np.isnan(r):
            boots.append(r)
    ci = (
        (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
        if boots
        else (float("nan"), float("nan"))
    )
    return {"n": n, "rho": float(rho), "p": float(p), "ci95": ci}


def comparar_rankers(
    learned: np.ndarray, h2_total: np.ndarray, notas: np.ndarray, **kw
) -> dict:
    """Compara o ranker aprendido (cabeça COCOLA) vs o H2 puro pela correlação com as notas.

    Critério da Fase 2c: a cabeça calibrada só se justifica se correlacionar **melhor**
    com o painel que o H2 heurístico. Reusa :func:`spearman_h2` (com IC95% bootstrap);
    `delta_rho > 0` e `cabeca_melhor=True` favorecem a cabeça.
    """
    s_learned = spearman_h2(learned, notas, **kw)
    s_h2 = spearman_h2(h2_total, notas, **kw)
    delta = s_learned["rho"] - s_h2["rho"]
    return {
        "learned": s_learned,
        "h2": s_h2,
        "delta_rho": float(delta),
        "cabeca_melhor": bool(s_learned["rho"] > s_h2["rho"]),
    }


def binomial_ab(n_prefere_proposto: int, n_total: int) -> dict:
    """Teste binomial da escolha forçada A/B (H1 confirmatório)."""
    if n_total == 0:
        return {"n": 0, "prefere_proposto": 0, "prop": float("nan"), "p": float("nan")}
    res = stats.binomtest(n_prefere_proposto, n_total, 0.5, alternative="two-sided")
    return {
        "n": n_total,
        "prefere_proposto": int(n_prefere_proposto),
        "prop": n_prefere_proposto / n_total,
        "p": float(res.pvalue),
    }


# --------------------------------------------------------------------------- #
# Carregadores (pandas) — do gabarito + respostas para as funções acima
# --------------------------------------------------------------------------- #
def carregar(gabarito_path: Path, respostas_path: Path):
    import pandas as pd

    gab = pd.read_csv(gabarito_path)
    resp = pd.read_csv(respostas_path)
    df = resp.merge(gab, on="estimulo_id", how="inner")
    return df, gab


def h1_de_df(df, eixo: str = "musicalidade") -> dict:
    medias = df.groupby(["par_id", "condicao"])[eixo].mean().unstack("condicao")
    medias = medias.dropna(subset=["baseline", "proposto"])
    return wilcoxon_h1(medias["proposto"].to_numpy(), medias["baseline"].to_numpy())


def h2_de_df(df, gab, eixo: str = "qualidade", condicao: str = "proposto") -> dict:
    sub = df[df["condicao"] == condicao]
    notas = sub.groupby("par_id")[eixo].mean()
    scores = gab.drop_duplicates("par_id").set_index("par_id")["score"]
    j = notas.to_frame("nota").join(scores).dropna()
    return spearman_h2(j["score"].to_numpy(), j["nota"].to_numpy())


def ab_de_df(ab_df, gab) -> dict:
    cond = gab.set_index("estimulo_id")["condicao"].to_dict()
    escolhas = ab_df["id_preferido"].map(cond)
    return binomial_ab(int((escolhas == "proposto").sum()), int(escolhas.notna().sum()))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser(description="Análise do experimento subjetivo (P4)")
    ap.add_argument("--gabarito", default=str(DIR_EXP / "gabarito.csv"))
    ap.add_argument("--respostas", default=str(DIR_EXP / "respostas.csv"))
    ap.add_argument("--ab", default=str(DIR_EXP / "respostas_ab.csv"))
    args = ap.parse_args()

    if not Path(args.respostas).exists():
        print(f"[analise] sem respostas em {args.respostas} — colete o painel antes.")
        return

    df, gab = carregar(Path(args.gabarito), Path(args.respostas))
    print(f"\n=== Experimento subjetivo — {df['avaliador'].nunique()} avaliadores, "
          f"{gab['par_id'].nunique()} pares ===\n")

    print("H1 — Wilcoxon pareado (proposto vs baseline):")
    for eixo in ("musicalidade", "qualidade", "artefatos"):
        if eixo in df.columns:
            r = h1_de_df(df, eixo)
            p = "n/a" if r["p"] is None else f"{r['p']:.4f}"
            print(f"  {eixo:13s} média {r['media_baseline']:.2f}→{r['media_proposto']:.2f} "
                  f"| W={r['stat']} p={p} | rank-biserial={r['rank_biserial']:+.2f} (n={r['n_pares']})")

    print("\nH2 — Spearman (score × qualidade percebida, proposto):")
    h2 = h2_de_df(df, gab)
    print(f"  rho={h2['rho']:+.3f} p={h2['p']:.4f} IC95%=[{h2['ci95'][0]:+.2f},{h2['ci95'][1]:+.2f}] (n={h2['n']})")
    if h2["n"] < 10:
        print("  (N pequeno: não concluir hipótese nula só por p>0.05 — reportar o IC.)")

    if Path(args.ab).exists():
        ab = ab_de_df(pd.read_csv(args.ab), gab)
        print(f"\nA/B escolha forçada: {ab['prefere_proposto']}/{ab['n']} preferem o proposto "
              f"({ab['prop']*100:.0f}%) — p binomial={ab['p']:.4f}")

    print("\nH3 — pares de maior salto harmônico (camelot_dist):")
    altos = gab.drop_duplicates("par_id").nlargest(3, "camelot_dist")
    for _, row in altos.iterrows():
        print(f"  {row['par_id']}: dist={row['camelot_dist']} score={row['score']:.2f}")


if __name__ == "__main__":
    main()
