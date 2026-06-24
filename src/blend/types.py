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
    # --- Mashability aprendida (Fase 2, COCOLA). Opcionais: None = não computado,
    # mantém o H2 heurístico intacto e a retrocompat de quem constrói só o básico. ---
    learned_score: float | None = None  # score de produto direcional A→B (cabeça calibrada)
    learned_score_rev: float | None = None  # direção reversa B→A (diagnóstico de assimetria)
    embed_sim: float | None = None  # similaridade bilinear COCOLA crua (diagnóstico)


@dataclass
class AlignmentPlan:
    """Como o vocal (A) entra sobre a base (B) — saída do alinhamento (P2)."""

    target_segment: Segment  # seção da base onde o vocal entra
    bpm_ratio: float  # fator de time-stretch aplicado ao vocal
    pitch_shift_semitones: float  # transposição do vocal
    vocal_offset: float  # quando o vocal começa, em segundos da base
    mode: str = "proposto"  # 'baseline' | 'proposto'
    nivel_fallback: int = 0  # 0 = caminho principal; 1–4 = degraus do fallback (auditoria P4)
    # Recorte do vocal no tempo de A (antes do stretch) — preenchido pelo pipeline,
    # que detecta atividade vocal no stem e limita a duração à seção alvo.
    vocal_in: float = 0.0  # onde o recorte começa, em segundos de A
    vocal_dur: float | None = None  # duração do recorte em segundos de A; None = até o fim
    # Sincronização frase-a-frase (Fase 1a). None = âncora única (comportamento atual).
    # Cada tupla = (t_no_vocal_s_de_A_relativo_ao_recorte, t_na_base_s_de_B_absoluto).
    phrase_anchors: list[tuple[float, float]] | None = None


@dataclass
class EmbedFeatures:
    """Features para a mashability aprendida (Fase 2) — injetadas pelo pipeline.

    Mantém `compatibility.py` puro: os embeddings COCOLA (e a similaridade
    bilinear pré-computada) são calculados em `mashability.py`/`pipeline` e
    passados prontos, espelhando o padrão de `metricas_por_segmento_de_audio`
    fora do `alignment.py`. Os campos da direção reversa (`*_b`/`*_a`) habilitam
    a assimetria A→B vs B→A; os demais são features baratas opcionais.
    """

    emb_vocal: list[float]  # embedding COCOLA do vocal isolado (A)
    emb_instr: list[float]  # embedding COCOLA do instrumental (B)
    emb_vocal_b: list[float] | None = None  # vocal de B (direção reversa)
    emb_instr_a: list[float] | None = None  # instrumental de A (direção reversa)
    centroide: float | None = None  # centroide espectral (diferença de brilho)
    mfcc: list[float] | None = None  # MFCC médios (timbre)
    rms_por_stem: dict | None = None  # loudness por stem (dBFS)
    sim_ab: float | None = None  # similaridade bilinear COCOLA direcional A→B (pré-computada)
    sim_ba: float | None = None  # similaridade bilinear direção reversa B→A
