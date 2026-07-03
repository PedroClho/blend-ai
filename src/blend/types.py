"""Tipos compartilhados entre os módulos do Blend AI (contrato P1 ↔ P2 ↔ P3)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Segment:
    """Seção musical detectada (allin1)."""

    start: float  # segundos
    end: float  # segundos
    label: str  # 'intro' | 'verse' | 'chorus' | 'drop' | 'bridge' | 'outro' | ...


@dataclass
class TrackAnalysis:
    """Saída do módulo de análise (P1, blend-audio) — entrada do motor (P2)."""

    path: str
    sr: int
    bpm: float
    beats: list[float] = field(default_factory=list)  # tempos (s)
    downbeats: list[float] = field(default_factory=list)  # tempos (s)
    segments: list[Segment] = field(default_factory=list)
    key_camelot: str | None = None  # ex.: '8A'


@dataclass
class ScoreCompat:
    """Score de compatibilidade entre duas faixas (H2) — saída de `compatibility_score`.

    Expõe o índice final **e** o breakdown por componente: o P4 (`blend-eval`)
    correlaciona cada componente separadamente com as notas do painel (Spearman
    por componente), além do `total`.
    """

    total: float  # [0,1] — índice preditivo final
    harmonico: float  # [0,1] — componente harmônico (distância Camelot mapeada)
    tempo: float  # [0,1] — componente de tempo (stretch após half/double)
    energia: float | None  # [0,1] — energia/estrutura; None quando não injetada
    camelot_dist: int  # passos crus na roda (-1 = tom ausente); diagnóstico/Spearman
    bpm_ratio: float  # fator de stretch escolhido (diagnóstico, consistente com o alinhamento)
    pesos: dict = field(default_factory=dict)  # pesos efetivos usados (após redistribuição)


@dataclass
class AlignmentPlan:
    """Como o vocal (A) entra sobre a base (B) — saída do alinhamento (P2)."""

    target_segment: Segment  # seção da base onde o vocal entra
    bpm_ratio: float  # fator de time-stretch aplicado ao vocal
    pitch_shift_semitones: float  # transposição do vocal
    vocal_offset: float  # quando o vocal começa, em segundos da base JÁ esticada
    mode: str = "proposto"  # 'baseline' | 'proposto' | 'manual'
    nivel_fallback: int = 0  # 0 = caminho principal; 1–4 = degraus do fallback (auditoria P4)
    # Recorte do vocal no tempo de A (antes do stretch) — preenchido pelo pipeline,
    # que detecta atividade vocal no stem e limita a duração à seção alvo.
    vocal_in: float = 0.0  # onde o recorte começa, em segundos de A
    vocal_dur: float | None = None  # duração do recorte em segundos de A; None = até o fim
    # BPM alvo do mashup: a BASE também é esticada (sem mudar de tom) e o vocal
    # mira o alvo em vez do BPM da base. 1.0/None = mantém o BPM da base.
    base_ratio: float = 1.0  # fator de time-stretch aplicado ao instrumental de B
    bpm_alvo: float | None = None  # BPM final pedido (diagnóstico/UI)
