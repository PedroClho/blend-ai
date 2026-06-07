"""Score de compatibilidade entre duas faixas (H2).

Combina três componentes num índice preditivo `[0,1]`:

* **Harmônico** — distância na roda Camelot mapeada para `[0,1]` por uma **tabela
  de classes de movimento** (mesma chave / relativo / vizinho de quinta-quarta /
  energy boost-drop / tritono), tradução direta da prática de *harmonic mixing*
  (Camelot Wheel, Mixed In Key). **[PURO]**
* **Tempo** — escolhe `f ∈ {0.5,1,2}` que minimiza o stretch (reusa
  `_escolher_bpm_ratio` do alinhamento) e decai linearmente com `|stretch − 1|`
  até zerar em `max_stretch_pct`. **[PURO]**
* **Energia / estrutura** — similaridade de loudness/intensidade (escalar de
  energia por faixa, em dBFS). **[depende de áudio → injetado pelo pipeline;
  OPCIONAL]** — sem ele, o peso é redistribuído e o score permanece puro e
  testável (paridade com o alinhamento).

Tudo determinístico e testável. Expõe o **breakdown** por componente (`harmonico`,
`tempo`, `energia`, `camelot_dist` cru, `bpm_ratio`, `pesos` efetivos): o P4
correlaciona cada um com as notas (Spearman por componente) e calibra os pesos.

Fundamentação e decisões (Q1–Q4): ``specs/score-compatibilidade.md``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .alignment import _escolher_bpm_ratio
from .types import ScoreCompat, TrackAnalysis


# --------------------------------------------------------------------------- #
# Parâmetros do score (defaults a calibrar via Spearman — P4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ParamsScore:
    """Pesos, limiares e curva do score de compatibilidade (defaults da spec).

    Em *harmonic mixing*, o ouvido perdoa um deslize de energia mais do que um
    choque harmônico, e o harmônico mais do que um stretch agressivo. Daí
    `w_harmonico > w_tempo > w_energia`. Os pesos são renormalizados quando a
    energia não é injetada (paridade com o alinhamento).
    """

    # Pesos da combinação (somam 1.0 com energia presente).
    w_harmonico: float = 0.50
    w_tempo: float = 0.35
    w_energia: float = 0.15

    # --- Tempo ---
    # Acima deste stretch (em %), o componente de tempo vai a 0 (Rubber Band
    # segura a qualidade dentro de ~8%). Consistente com a spec do alinhamento.
    max_stretch_pct: float = 8.0

    # --- Energia ---
    # Escala de tolerância da diferença de loudness (≈ uma "casa" de fader);
    # acima disso o desbalanço é nítido na pista.
    energia_tol_db: float = 6.0

    # --- Harmônico ---
    # Componente harmônico quando falta o tom de um dos lados: neutro
    # (não premia nem pune), deixa o P1 evoluir a detecção sem quebrar o score.
    key_ausente_neutro: float = 0.5


# --------------------------------------------------------------------------- #
# Distância Camelot
# --------------------------------------------------------------------------- #
_CAMELOT_RE = re.compile(r"^\s*(\d{1,2})\s*([abAB])\s*$")


def _parse_camelot(s: str | None) -> tuple[int, str] | None:
    """Valida e separa uma chave Camelot em `(numero 1..12, letra 'A'|'B')`.

    Retorna None para notação inválida (número fora de 1..12, letra ausente,
    string vazia/None). O score trata None como tom ausente (componente neutro).
    """
    if not isinstance(s, str):
        return None
    m = _CAMELOT_RE.match(s)
    if not m:
        return None
    num = int(m.group(1))
    if not (1 <= num <= 12):
        return None
    letra = m.group(2).upper()
    return num, letra


def camelot_distance(a: str, b: str) -> int:
    """Distância na roda Camelot, em "passos de incompatibilidade" (crua).

    Número **mínimo** de passos: troca de número (menor arco no círculo de 12,
    ±1 = 1 passo) **mais** troca de letra (A↔B = 1 passo). É a distância crua
    para auditoria do P4; **não** codifica a "qualidade" — isso é o
    :func:`comp_harmonico` (a tabela do Q1 captura a não-linearidade, p.ex.
    relativo > vizinho-diagonal apesar de ambos terem distância 1).

    Convenção (passos): mesma chave → 0; relativo (mesmo nº, troca letra) → 1;
    vizinho (±1, mesma letra: quinta/quarta) → 1; cresce com o arco + troca de modo.

    Levanta `ValueError` em notação inválida (contrato explícito; o score usa
    :func:`_parse_camelot` para degradar sem exceção).
    """
    pa = _parse_camelot(a)
    pb = _parse_camelot(b)
    if pa is None or pb is None:
        raise ValueError(f"Camelot inválido: a={a!r}, b={b!r}")
    (na, la), (nb, lb) = pa, pb
    d_ang = abs(na - nb)
    d_ang = min(d_ang, 12 - d_ang)  # menor arco na roda de 12 (quintas/quartas)
    d_modo = 0 if la == lb else 1  # troca de modo (maior↔menor) custa 1 passo
    return d_ang + d_modo


# Tabela de QUALIDADE harmônica por classe de movimento da roda Camelot → [0,1].
# Chaveada por (Δnúmero reduzido ao menor arco 0..6, mesma_letra?).
# Fundamentação (harmonic mixing / Camelot Wheel, Mixed In Key):
#   (0, mesma)   mesma chave ......................... 1.00 (encaixe perfeito)
#   (0, troca)   relativo maior↔menor ................ 0.90 (clássico)
#   (1, mesma)   vizinho: quinta/quarta .............. 0.85 (pilar do harmonic mixing)
#   (1, troca)   vizinho diagonal ................... 0.55 (com cuidado)
#   (2, mesma)   energy boost/drop (+2/−2) .......... 0.55 (sobe/baixa energia)
#   (2, troca)   +2 diagonal ........................ 0.30
#   (3, mesma)   ±3 mesma letra ..................... 0.35 (puxado, usável em build)
#   (3, troca)   ±3 diagonal ........................ 0.20
#   (4/5, *)     salto médio ........................ baixo
#   (6, *)       tritono / oposto ................... 0.05 (choque máximo)
_HARMONICO_TABELA: dict[tuple[int, bool], float] = {
    (0, True): 1.00,   # mesma_letra=True
    (0, False): 0.90,
    (1, True): 0.85,
    (1, False): 0.55,
    (2, True): 0.55,
    (2, False): 0.30,
    (3, True): 0.35,
    (3, False): 0.20,
    (4, True): 0.20,
    (4, False): 0.15,
    (5, True): 0.10,
    (5, False): 0.08,
    (6, True): 0.05,
    (6, False): 0.05,
}


def _qualidade_harmonica(d_ang: int, mesma_letra: bool) -> float:
    """Mapeia (arco 0..6, mesma_letra) → qualidade [0,1] via tabela do Q1.

    Fora da tabela (não deve ocorrer; d_ang ∈ 0..6), cai num "salto médio"
    conservador por mesma_letra.
    """
    key = (d_ang, mesma_letra)
    if key in _HARMONICO_TABELA:
        return _HARMONICO_TABELA[key]
    return 0.20 if mesma_letra else 0.15


def comp_harmonico(a: str | None, b: str | None, params: ParamsScore | None = None) -> float:
    """Componente harmônico `[0,1]` (qualidade do movimento na roda).

    Tom ausente/inválido em qualquer lado → `key_ausente_neutro` (default 0.5):
    não afirma nem nega o encaixe. Determinístico.
    """
    params = params or ParamsScore()
    pa = _parse_camelot(a)
    pb = _parse_camelot(b)
    if pa is None or pb is None:
        return params.key_ausente_neutro
    (na, la), (nb, lb) = pa, pb
    d_ang = abs(na - nb)
    d_ang = min(d_ang, 12 - d_ang)
    return _qualidade_harmonica(d_ang, la == lb)


def _camelot_dist_seguro(a: str | None, b: str | None) -> int:
    """`camelot_distance` que não levanta: tom ausente/inválido → -1 (sentinela)."""
    if _parse_camelot(a) is None or _parse_camelot(b) is None:
        return -1
    return camelot_distance(a, b)


# --------------------------------------------------------------------------- #
# Componente de tempo (half/double-time)
# --------------------------------------------------------------------------- #
def comp_tempo(
    bpm_base: float | None,
    bpm_vocal: float | None,
    params: ParamsScore | None = None,
) -> tuple[float, float]:
    """Componente de tempo `[0,1]` + `bpm_ratio` (diagnóstico).

    Reusa `_escolher_bpm_ratio` do alinhamento (consistência baseline↔proposto):
    escolhe `f∈{0.5,1,2}` e obtém `ratio`; `stretch_pct = |ratio − 1|·100`.
    Decai **linearmente** de 1.0 (stretch 0%) a 0.0 em `max_stretch_pct`. BPM
    ausente/≤0 → neutro 1.0 e `ratio=1.0` (sem dado, nada a penalizar).
    """
    params = params or ParamsScore()
    if not bpm_base or bpm_base <= 0 or not bpm_vocal or bpm_vocal <= 0:
        return 1.0, 1.0
    ratio = _escolher_bpm_ratio(bpm_base, bpm_vocal)
    stretch_pct = abs(ratio - 1.0) * 100.0
    comp = max(0.0, min(1.0, 1.0 - stretch_pct / params.max_stretch_pct))
    return comp, ratio


# --------------------------------------------------------------------------- #
# Componente de energia (opcional, injetado)
# --------------------------------------------------------------------------- #
def comp_energia(
    metricas: dict | None,
    params: ParamsScore | None = None,
) -> float | None:
    """Componente de energia `[0,1]`, ou None se `metricas` não trouxer energia.

    `metricas = {'energia_a': float, 'energia_b': float}` — escalares de loudness
    por faixa **na mesma unidade** (dBFS, ou LUFS), computados pelo pipeline a
    partir do mix/stems. Similaridade pela diferença normalizada por
    `energia_tol_db`:

        comp = clamp(1 − |energia_a − energia_b| / energia_tol_db, 0, 1).

    Sem `metricas` ou sem ambas as chaves → None (componente sai, peso
    redistribuído). Decisão (Q2): número de seções é proxy ruim de vibe e fica de
    fora; o que mata o mashup é uma faixa marcando muito mais forte que a outra.
    """
    params = params or ParamsScore()
    if not metricas:
        return None
    ea = metricas.get("energia_a")
    eb = metricas.get("energia_b")
    if ea is None or eb is None:
        return None
    # Guarda NaN/inf: sem isto, um NaN escaparia do clamp como 1.0 (casamento
    # perfeito espúrio) e envenenaria o Spearman do P4 silenciosamente.
    if not math.isfinite(float(ea)) or not math.isfinite(float(eb)):
        return None
    diff = abs(float(ea) - float(eb))
    return max(0.0, min(1.0, 1.0 - diff / max(params.energia_tol_db, 1e-9)))


# --------------------------------------------------------------------------- #
# Combinação final
# --------------------------------------------------------------------------- #
def compatibility_score(
    a: TrackAnalysis,
    b: TrackAnalysis,
    metricas: dict | None = None,
    params: ParamsScore | None = None,
) -> ScoreCompat:
    """Índice preditivo `[0,1]` + breakdown (H2).

    `a` = vocal, `b` = base (mesma convenção do alinhamento). `metricas` é a
    injeção opcional do pipeline com `{'energia_a', 'energia_b'}` (dBFS/LUFS);
    sem ela, o componente de energia sai e o peso `w_energia` é redistribuído
    proporcionalmente entre harmônico e tempo (paridade determinística — P4).

    Determinístico e puro (camelot e tempo não leem áudio; energia é injetada).
    """
    params = params or ParamsScore()

    harm = comp_harmonico(a.key_camelot, b.key_camelot, params)
    cam_dist = _camelot_dist_seguro(a.key_camelot, b.key_camelot)
    temp, bpm_ratio = comp_tempo(b.bpm, a.bpm, params)
    ener = comp_energia(metricas, params)

    # Pesos efetivos: se energia ausente, redistribui w_energia entre harm/tempo.
    if ener is None:
        soma_ht = params.w_harmonico + params.w_tempo
        w = {
            "harmonico": params.w_harmonico / soma_ht,
            "tempo": params.w_tempo / soma_ht,
            "energia": 0.0,
        }
        total = w["harmonico"] * harm + w["tempo"] * temp
    else:
        soma = params.w_harmonico + params.w_tempo + params.w_energia
        w = {
            "harmonico": params.w_harmonico / soma,
            "tempo": params.w_tempo / soma,
            "energia": params.w_energia / soma,
        }
        total = w["harmonico"] * harm + w["tempo"] * temp + w["energia"] * ener

    return ScoreCompat(
        total=max(0.0, min(1.0, total)),
        harmonico=harm,
        tempo=temp,
        energia=ener,
        camelot_dist=cam_dist,
        bpm_ratio=bpm_ratio,
        pesos=w,
    )
