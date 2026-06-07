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
class AlignmentPlan:
    """Como o vocal (A) entra sobre a base (B) — saída do alinhamento (P2)."""

    target_segment: Segment  # seção da base onde o vocal entra
    bpm_ratio: float  # fator de time-stretch aplicado ao vocal
    pitch_shift_semitones: float  # transposição do vocal
    vocal_offset: float  # quando o vocal começa, em segundos da base
    mode: str = "proposto"  # 'baseline' | 'proposto'
    nivel_fallback: int = 0  # 0 = caminho principal; 1–4 = degraus do fallback (auditoria P4)
