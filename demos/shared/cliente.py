"""Cliente de Anthropic: resuelve la API key sin que nunca toque el repo."""

import os

import anthropic
import streamlit as st


def _key() -> str | None:
    """Streamlit Cloud (Secrets) primero, entorno después."""
    try:
        if st.secrets.get("ANTHROPIC_API_KEY"):
            return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def hay_api_key() -> bool:
    return bool(_key())


@st.cache_resource
def obtener_cliente() -> anthropic.Anthropic:
    api_key = _key()
    if not api_key:
        st.error(
            "No se encontró `ANTHROPIC_API_KEY`. Configúrala en los **Secrets** de "
            "Streamlit Cloud o como variable de entorno (ver README). "
            "Mientras tanto, activa el **Modo respaldo** en el panel lateral: "
            "reproduce corridas reales pre-grabadas y no necesita internet."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)
