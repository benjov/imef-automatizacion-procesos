"""App multipágina de las demos — un solo despliegue en Streamlit Cloud.

Correr en local:  streamlit run demos/app.py
"""

import sys
from pathlib import Path

import streamlit as st

# `shared` debe ser importable aunque Streamlit arranque desde otra carpeta.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.config import BANCO, CUENTA, EMPRESA, MODELO, PERIODO  # noqa: E402

st.set_page_config(
    page_title="Automatización de Procesos Financieros · IMEF",
    page_icon="🏦",
    layout="wide",
)

with st.sidebar:
    st.markdown("### Automatización de Procesos Financieros")
    st.caption(
        "Comité Técnico Nacional de Transformación y Economía Digital · IMEF  \n"
        "Benjamín Oliva Vázquez · 13 de agosto de 2026"
    )
    st.markdown("---")
    st.markdown(
        f"**Caso**  \n{EMPRESA}  \n{BANCO} {CUENTA}  \n{PERIODO}  \n\n"
        f"**Modelo** `{MODELO}`"
    )
    st.caption(
        "Datos sintéticos generados con semilla fija. Ninguna cifra "
        "corresponde a una empresa real."
    )

paginas = st.navigation([
    st.Page("paginas/demo1_conciliacion.py",
            title="1 · Conciliación bancaria", icon="🏦", default=True),
    st.Page("paginas/demo2_agente.py",
            title="2 · Agente de cierre", icon="🤖"),
])
paginas.run()
