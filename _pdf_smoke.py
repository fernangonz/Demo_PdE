import streamlit as st
from pathlib import Path
st.title("PDF smoke")
p = Path(r"Flujo de modelos/PI SUPERACIÓN DE UMBRAL.pdf")
st.caption(p.name)
st.pdf(p.read_bytes(), height=500, key="smoke")
