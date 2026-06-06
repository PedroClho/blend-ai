"""Blend AI — app Streamlit (MVP). Casca fina sobre blend.pipeline."""
import streamlit as st

st.set_page_config(page_title="Blend AI", page_icon="🎛️", layout="centered")

st.title("🎛️ Blend AI")
st.caption("Mashup automático — vocal de uma faixa sobre o instrumental de outra.")

# TODO P3: upload de A (vocal) e B (base), seleção de modo, disparar
# blend.pipeline.make_mashup, preview com player e export do .wav.
st.info("MVP em construção. Lógica do produto em `app/` (P3); motor em `src/blend/pipeline.py`.")
