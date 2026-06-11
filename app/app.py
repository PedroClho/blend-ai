"""Blend AI — app Streamlit (MVP). Casca fina sobre blend.pipeline."""
from __future__ import annotations

import io as _io
import sys
import tempfile
from pathlib import Path

# src/ no path (no container PYTHONPATH=/app/src já cobre; redundância defensiva)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

st.set_page_config(page_title="Blend AI", page_icon="🎛️", layout="centered")

st.title("🎛️ Blend AI")
st.caption("Mashup automático — vocal de uma faixa sobre o instrumental de outra.")


def _escrever_temp(dados: bytes, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".mp3")
    tmp.write(dados)
    tmp.close()
    return tmp.name


@st.cache_data(show_spinner=False, max_entries=4)
def _gerar(vocal_bytes: bytes, base_bytes: bytes, vsuf: str, bsuf: str, modo: str):
    """Roda o pipeline e devolve (wav_bytes, info). Cacheado por conteúdo+modo."""
    import soundfile as sf

    from blend.pipeline import make_mashup

    pv = _escrever_temp(vocal_bytes, vsuf)
    pb = _escrever_temp(base_bytes, bsuf)
    res = make_mashup(pv, pb, mode=modo)

    buf = _io.BytesIO()
    sf.write(buf, res.mashup.T, res.sr, format="WAV", subtype="PCM_16")

    seg = res.plan.target_segment
    info = {
        "score_total": res.score.total,
        "harm": res.score.harmonico,
        "tempo": res.score.tempo,
        "camelot_dist": res.score.camelot_dist,
        "bpm_ratio": res.plan.bpm_ratio,
        "pitch": res.plan.pitch_shift_semitones,
        "offset": res.plan.vocal_offset,
        "nivel": res.plan.nivel_fallback,
        "secao": seg.label,
        "secao_ini": seg.start,
        "secao_fim": seg.end,
    }
    return buf.getvalue(), info


col1, col2 = st.columns(2)
with col1:
    up_a = st.file_uploader(
        "Faixa A — de onde vem o **vocal**", type=["mp3", "wav", "flac"], key="a"
    )
with col2:
    up_b = st.file_uploader(
        "Faixa B — de onde vem o **instrumental**", type=["mp3", "wav", "flac"], key="b"
    )

modo = st.radio(
    "Alinhamento",
    ["proposto", "baseline"],
    horizontal=True,
    help=(
        "proposto = estrutura-aware (escolhe uma seção de groove e ancora o vocal "
        "no downbeat dela); baseline = ingênuo (casa BPM/tom e solta no 1º downbeat)."
    ),
)

if st.button(
    "🎚️ Gerar mashup", type="primary", disabled=not (up_a and up_b), use_container_width=True
):
    with st.spinner("Separando (Demucs), analisando e sintetizando… ~1–2 min na GPU"):
        wav_bytes, info = _gerar(
            up_a.getvalue(),
            up_b.getvalue(),
            Path(up_a.name).suffix,
            Path(up_b.name).suffix,
            modo,
        )

    st.success("Mashup pronto.")
    st.audio(wav_bytes, format="audio/wav")
    st.download_button(
        "⬇️ Baixar .wav",
        wav_bytes,
        file_name=f"blend_{modo}.wav",
        mime="audio/wav",
        use_container_width=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Compatibilidade", f"{info['score_total']:.2f}")
    m2.metric("Harmônico", f"{info['harm']:.2f}")
    m3.metric("Tempo", f"{info['tempo']:.2f}")

    nivel_txt = "seção rotulada" if info["nivel"] == 0 else f"fallback nível {info['nivel']}"
    st.caption(
        f"Seção: **{info['secao']}** [{info['secao_ini']:.1f}–{info['secao_fim']:.1f}s] · "
        f"vocal entra em {info['offset']:.1f}s · stretch ×{info['bpm_ratio']:.3f} · "
        f"pitch {info['pitch']:+.1f} st · Camelot dist {info['camelot_dist']} · {nivel_txt}"
    )
elif not (up_a and up_b):
    st.info("Envie as duas faixas (A = vocal, B = instrumental) para gerar o mashup.")
