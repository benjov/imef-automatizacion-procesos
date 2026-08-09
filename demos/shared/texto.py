"""Utilidades de texto para Streamlit.

Streamlit interpreta `$...$` en Markdown como fórmula de LaTeX, así que un
reporte financiero lleno de montos ("$8.9 M contra $1.6 M") se deforma en
pantalla. Aquí se escapa el signo SÓLO al renderizar: el texto que se guarda
y el que se descarga quedan intactos.
"""

from typing import Iterable, Iterator

import streamlit as st


def escapar(texto: str) -> str:
    return texto.replace("$", "\\$")


def markdown(texto: str) -> None:
    st.markdown(escapar(texto))


def stream_md(chunks: Iterable[str]) -> str:
    """Renderiza un stream escapando `$` y devuelve el texto CRUDO acumulado."""
    crudo: list[str] = []

    def gen() -> Iterator[str]:
        for c in chunks:
            crudo.append(c)
            yield c.replace("$", "\\$")

    st.write_stream(gen())
    return "".join(crudo)


def pesos(monto: float) -> str:
    """Formato contable: negativos entre paréntesis, como en un estado financiero."""
    if monto < 0:
        return f"($ {abs(monto):,.2f})"
    return f"$ {monto:,.2f}"
