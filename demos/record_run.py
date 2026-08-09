"""Graba corridas REALES de la API para alimentar el Modo respaldo.

    python demos/record_run.py            # graba las dos demos
    python demos/record_run.py --solo 1   # sólo la Demo 1

Requiere `ANTHROPIC_API_KEY` (en el entorno o en el `.env` de la raíz).

Importa el MISMO prompt, el MISMO esquema y las MISMAS herramientas que usa la
app (`shared/analisis.py` y `shared/agente.py`). Por eso no hay riesgo de que
el respaldo se desincronice de la demo en vivo: no existen dos copias del
prompt que mantener.

Después de cambiar datos, prompts o herramientas: regrabar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "demos"))

from shared import agente, analisis                                   # noqa: E402
from shared.config import (ARCHIVO_BANCO, ARCHIVO_CARTERA,            # noqa: E402
                           ARCHIVO_LIBROS, ARCHIVO_POLITICAS,
                           DIR_RESPALDOS, MODELO, costo_mxn)
from shared.motor import cargar_banco, cargar_libros, conciliar       # noqa: E402


def cargar_env() -> None:
    """Lee el .env de la raíz.

    Quita comillas y espacios alrededor del valor: en la charla anterior una
    key entre comillas produjo un 401 que costó media hora de depuración
    buscando el problema en el lugar equivocado.
    """
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", linea)
        if m and not linea.lstrip().startswith("#"):
            clave, valor = m.group(1), m.group(2).strip().strip('"').strip("'")
            os.environ.setdefault(clave, valor)


def cliente_directo():
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY (ponla en el entorno o en el .env de la raíz).")
    return anthropic.Anthropic()


def guardar(nombre: str, datos: dict) -> None:
    DIR_RESPALDOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_RESPALDOS / f"{nombre}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    kb = ruta.stat().st_size / 1024
    print(f"  guardado -> {ruta.relative_to(RAIZ)} ({kb:.1f} KB)")


# --------------------------------------------------------------------------
def grabar_demo1(cliente) -> None:
    print("\n=== Demo 1 · Motor + clasificación de excepciones ===")
    banco = cargar_banco(ARCHIVO_BANCO)
    libros = cargar_libros(ARCHIVO_LIBROS)
    res = conciliar(banco, libros)
    print(f"  motor: {res.conciliados}/{res.total_movimientos} conciliados "
          f"({res.tasa:.1%}) en {res.segundos*1000:.1f} ms · "
          f"{len(res.excepciones)} excepciones")

    t0 = time.perf_counter()
    salida = analisis.analizar(
        cliente, res.excepciones, banco + libros,
        ARCHIVO_CARTERA.read_text(encoding="utf-8"),
        ARCHIVO_POLITICAS.read_text(encoding="utf-8"),
    )
    salida["segundos"] = round(time.perf_counter() - t0, 2)
    salida["grabado"] = time.strftime("%Y-%m-%d %H:%M")

    print(f"  modelo: {salida['tokens_entrada']:,} tokens de entrada, "
          f"{salida['tokens_salida']:,} de salida en {salida['segundos']:.1f} s "
          f"(~${costo_mxn(salida['tokens_entrada'], salida['tokens_salida']):.2f} MXN)")
    print(f"  partidas clasificadas: {len(salida['partidas'])}")
    for p in salida["partidas"]:
        marca = "👤" if p["requiere_humano"] else "  "
        print(f"    {marca} [{p['confianza'][:1].upper()}] {p['titulo']} "
              f"-> {p['accion']}")
    guardar("demo1", salida)


def grabar_demo2(cliente) -> None:
    print("\n=== Demo 2 · Agente de cierre (tool use) ===")
    grabados = {}
    for etiqueta, instruccion in agente.INSTRUCCIONES.items():
        print(f"\n  -- {etiqueta}")
        t0 = time.perf_counter()

        def al_paso(ev):
            if ev["tipo"] == "herramienta":
                print(f"     herramienta: {ev['nombre']}({json.dumps(ev['args'], ensure_ascii=False)[:70]})")

        salida = agente.correr(cliente, instruccion, al_paso=al_paso)
        salida["segundos"] = round(time.perf_counter() - t0, 2)
        salida["grabado"] = time.strftime("%Y-%m-%d %H:%M")
        llamadas = sum(1 for p in salida["pasos"] if p["tipo"] == "herramienta")
        print(f"     {llamadas} llamadas a herramientas · "
              f"{salida['tokens_entrada']:,}/{salida['tokens_salida']:,} tokens · "
              f"{salida['segundos']:.1f} s "
              f"(~${costo_mxn(salida['tokens_entrada'], salida['tokens_salida']):.2f} MXN)")
        grabados[etiqueta] = salida

    guardar("demo2", {"modelo": MODELO, "corridas": grabados,
                      "grabado": time.strftime("%Y-%m-%d %H:%M")})


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Graba los respaldos de las demos.")
    ap.add_argument("--solo", choices=["1", "2"], help="Grabar sólo una demo.")
    args = ap.parse_args()

    cargar_env()
    cliente = cliente_directo()
    print(f"Modelo: {MODELO}")

    if args.solo != "2":
        grabar_demo1(cliente)
    if args.solo != "1":
        grabar_demo2(cliente)

    print("\nListo. Prueba el Modo respaldo con el WiFi apagado antes del evento.")


if __name__ == "__main__":
    main()
