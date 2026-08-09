"""Modo respaldo: reproduce corridas REALES pre-grabadas, sin red.

Los archivos de `demos/data/respaldos/` no son texto inventado a mano: son
corridas de la API guardadas tal cual con `python demos/record_run.py`. En
modo respaldo la demo se ve idéntica a la corrida en vivo —incluida la
simulación del streaming— pero no necesita internet ni API key.

Es la red de seguridad de la charla. En una sesión virtual el riesgo no es
sólo el WiFi propio: es la plataforma de videollamada saturando el enlace
justo cuando toca la demo.
"""

from __future__ import annotations

import json
import time
from typing import Iterator

import streamlit as st

from .config import DIR_RESPALDOS


def cargar(nombre: str) -> dict:
    ruta = DIR_RESPALDOS / f"{nombre}.json"
    if not ruta.exists():
        st.error(
            f"No existe el respaldo `{ruta.name}`. Regrábalo con "
            "`python demos/record_run.py` (requiere API key e internet)."
        )
        st.stop()
    return json.loads(ruta.read_text(encoding="utf-8"))


def stream_falso(texto: str, pausa: float = 0.010) -> Iterator[str]:
    """Emite el texto en trozos pequeños para que se vea como streaming real."""
    palabras = texto.split(" ")
    for i in range(0, len(palabras), 3):
        yield " ".join(palabras[i:i + 3]) + " "
        time.sleep(pausa)


def toggle_respaldo() -> bool:
    """Interruptor discreto en el panel lateral. True = modo respaldo activo."""
    with st.sidebar:
        st.markdown("---")
        activo = st.toggle(
            "Modo respaldo",
            value=st.session_state.get("modo_respaldo", False),
            help="Reproduce corridas reales pre-grabadas. No llama a la API "
                 "ni necesita internet.",
        )
        st.session_state["modo_respaldo"] = activo
        if activo:
            st.caption("🔌 Sin conexión. Reproduciendo una corrida grabada.")
    return activo
