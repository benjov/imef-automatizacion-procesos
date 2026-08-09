"""Estilos: legibles en videollamada comprimida y en proyector."""

import streamlit as st

CSS = """
<style>
#MainMenu, footer, header [data-testid="stDecoration"] {visibility: hidden;}

html, body, [data-testid="stAppViewContainer"] * { font-size: 1.02rem; }
h1 {font-size: 2.0rem !important; color: #1F2937;}
h2 {font-size: 1.55rem !important; color: #1F2937;}
h3 {font-size: 1.25rem !important;}
[data-testid="stMetricValue"] {font-size: 1.85rem;}
[data-testid="stMetricLabel"] {font-size: 0.95rem;}

.stButton > button[kind="primary"] { font-size: 1.1rem; padding: 0.6rem 1.4rem; }

/* Tarjeta de partida en conciliación */
.partida {
  border: 1px solid #E5E7EB; border-left: 5px solid #6B7280;
  border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
  background: #FFFFFF;
}
.partida.alta  { border-left-color: #0D9488; }
.partida.media { border-left-color: #B45309; }
.partida.baja  { border-left-color: #B91C1C; }
.partida .titulo { font-weight: 700; color: #1F2937; font-size: 1.08rem; }
.partida .meta   { color: #6B7280; font-size: 0.88rem; margin-bottom: 0.4rem; }
.partida .monto  { float: right; font-variant-numeric: tabular-nums;
                   font-weight: 700; color: #1F2937; }

/* Etiqueta de acción */
.etiqueta {
  display: inline-block; font-size: 0.78rem; font-weight: 700;
  letter-spacing: 0.04em; text-transform: uppercase;
  padding: 0.18rem 0.6rem; border-radius: 999px;
  background: #EFF4FF; color: #2563EB; margin-right: 0.4rem;
}
.etiqueta.humano { background: #FEF3C7; color: #B45309; }

/* Llamada de atención del motor determinista */
.motor {
  background: #F0FDFA; border: 1px solid #99F6E4; border-radius: 10px;
  padding: 0.9rem 1.1rem; margin: 0.6rem 0;
}
</style>
"""


def aplicar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
