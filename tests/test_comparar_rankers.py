"""Teste do comparativo cabeça-calibrada vs H2 puro (Fase 2c, Tarefa 8). Puro (scipy)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402


def test_comparar_rankers_favorece_quem_correlaciona_mais():
    from eval.analise import comparar_rankers

    notas = np.arange(1, 11, dtype=float)
    learned = notas.copy()  # ranking perfeito → rho ~1
    h2 = np.array([3, 1, 4, 2, 5, 8, 6, 10, 7, 9], dtype=float)  # correlação menor
    r = comparar_rankers(learned, h2, notas)
    assert r["cabeca_melhor"] is True
    assert r["delta_rho"] > 0
    assert "learned" in r and "h2" in r
    assert r["learned"]["rho"] > r["h2"]["rho"]


def test_comparar_rankers_empate_nao_favorece_cabeca():
    from eval.analise import comparar_rankers

    notas = np.arange(1, 11, dtype=float)
    r = comparar_rankers(notas.copy(), notas.copy(), notas)
    assert r["delta_rho"] == 0.0
    assert r["cabeca_melhor"] is False
