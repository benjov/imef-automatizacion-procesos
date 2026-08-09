"""Pruebas de humo: ejecutan las dos páginas de verdad, sin gastar un token.

    python demos/pruebas_de_humo.py

Usa `streamlit.testing` para correr cada página en modo respaldo y verificar
que renderiza sin excepciones. Es lo que hay que correr después de tocar
cualquier cosa, y en particular antes del ensayo general: una demo que falla
en vivo por un `KeyError` no la salva ningún respaldo.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMOS))

from streamlit.testing.v1 import AppTest      # noqa: E402


def revisar(at: AppTest, etiqueta: str) -> bool:
    if at.exception:
        print(f"  ✗ {etiqueta}")
        for e in at.exception:
            print(f"      {e.type}: {e.value}")
        return False
    print(f"  ✓ {etiqueta}")
    return True


def correr_pagina(ruta: Path, etiqueta: str) -> bool:
    ok = True
    at = AppTest.from_file(str(ruta), default_timeout=60)
    at.run()
    ok &= revisar(at, f"{etiqueta} — carga inicial")
    if at.exception:
        return False

    # Modo respaldo encendido: reproduce la corrida grabada, sin red.
    at.session_state["modo_respaldo"] = True
    at.toggle[0].set_value(True).run()
    ok &= revisar(at, f"{etiqueta} — modo respaldo")

    if at.button:
        at.button[0].click().run()
        ok &= revisar(at, f"{etiqueta} — corrida completa desde respaldo")
        n_tablas = len(at.dataframe)
        print(f"      {n_tablas} tablas y {len(at.markdown)} bloques renderizados")
    return ok


def main() -> None:
    print("Pruebas de humo (modo respaldo, sin llamadas a la API)\n")
    todo_bien = True
    todo_bien &= correr_pagina(DEMOS / "paginas" / "demo1_conciliacion.py",
                               "Demo 1 · Conciliación")
    todo_bien &= correr_pagina(DEMOS / "paginas" / "demo2_agente.py",
                               "Demo 2 · Agente")

    print()
    if todo_bien:
        print("Todo verde. Recuerda probar también el modo REAL antes del evento.")
    else:
        print("Hay fallas. No ensayes hasta arreglarlas.")
        sys.exit(1)


if __name__ == "__main__":
    main()
