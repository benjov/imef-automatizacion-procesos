"""Motor de conciliación determinista. Sin IA, sin red, sin tokens.

Esta es la mitad de la charla que la gente no espera: el 90% de una
conciliación bancaria no necesita un modelo de lenguaje, necesita aritmética
bien hecha. El motor cruza dos archivos en cuatro niveles y deja como
"excepción" únicamente lo que NO puede probar. Ese residuo — y sólo ese — es
lo que se manda a la IA en `paginas/demo1_conciliacion.py`.

Todo el dinero se maneja internamente en CENTAVOS ENTEROS: comparar flotantes
en una conciliación es cómo se producen las diferencias de un peso que nadie
puede explicar.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import combinations
from pathlib import Path

# Festivo oficial dentro del periodo (16 de septiembre).
FESTIVOS = {date(2026, 9, 16)}

VENTANA_DIAS_HABILES = 3   # desfase máximo aceptado entre banco y libros
MAX_PARTIDAS_AGRUPADAS = 4  # tamaño máximo de una agrupación 1:N


# --------------------------------------------------------------------------
# Modelo de datos
# --------------------------------------------------------------------------
@dataclass
class Movimiento:
    id: str
    origen: str           # "banco" | "libros"
    fecha: date
    centavos: int         # con signo: + entra dinero, - sale dinero
    descripcion: str
    referencia: str = ""
    tercero: str = ""

    @property
    def monto(self) -> float:
        return self.centavos / 100

    def como_dict(self) -> dict:
        return {"id": self.id, "origen": self.origen, "fecha": self.fecha.isoformat(),
                "monto": self.monto, "descripcion": self.descripcion,
                "referencia": self.referencia, "tercero": self.tercero}


@dataclass
class Cruce:
    nivel: int
    etiqueta: str
    banco: list[Movimiento]
    libros: list[Movimiento]
    diferencia_centavos: int = 0

    def como_dict(self) -> dict:
        return {"nivel": self.nivel, "etiqueta": self.etiqueta,
                "banco": [m.como_dict() for m in self.banco],
                "libros": [m.como_dict() for m in self.libros],
                "diferencia": self.diferencia_centavos / 100}


@dataclass
class Resultado:
    cruces: list[Cruce] = field(default_factory=list)
    excepciones: list[Movimiento] = field(default_factory=list)
    total_banco: int = 0
    total_libros: int = 0
    segundos: float = 0.0

    @property
    def conciliados(self) -> int:
        return sum(len(c.banco) + len(c.libros) for c in self.cruces)

    @property
    def total_movimientos(self) -> int:
        return self.total_banco + self.total_libros

    @property
    def tasa(self) -> float:
        if not self.total_movimientos:
            return 0.0
        return self.conciliados / self.total_movimientos

    @property
    def monto_en_excepcion(self) -> float:
        return sum(abs(m.centavos) for m in self.excepciones) / 100

    def por_nivel(self) -> dict[str, int]:
        conteo: dict[str, int] = {}
        for c in self.cruces:
            clave = f"N{c.nivel} · {c.etiqueta}"
            conteo[clave] = conteo.get(clave, 0) + len(c.banco) + len(c.libros)
        return conteo


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def _a_centavos(texto: str) -> int:
    """'1,234.50' -> 123450. Cadena vacía -> 0."""
    texto = (texto or "").strip().replace(",", "").replace("$", "")
    if not texto:
        return 0
    return int(round(float(texto) * 100))


def cargar_banco(ruta: Path) -> list[Movimiento]:
    movs = []
    with ruta.open(encoding="utf-8") as fh:
        for i, fila in enumerate(csv.DictReader(fh), start=1):
            # En el estado de cuenta: abono = entra, cargo = sale.
            centavos = _a_centavos(fila["abono"]) - _a_centavos(fila["cargo"])
            movs.append(Movimiento(
                id=f"B{i:04d}", origen="banco",
                fecha=date.fromisoformat(fila["fecha"]),
                centavos=centavos,
                descripcion=fila["descripcion"].strip(),
                referencia=fila["referencia"].strip(),
            ))
    return movs


def cargar_libros(ruta: Path) -> list[Movimiento]:
    movs = []
    with ruta.open(encoding="utf-8") as fh:
        for i, fila in enumerate(csv.DictReader(fh), start=1):
            # En el auxiliar de Bancos la convención se invierte:
            # cargo = entra dinero, abono = sale. Es el error #1 de quien
            # concilia por primera vez con una hoja de cálculo.
            centavos = _a_centavos(fila["cargo"]) - _a_centavos(fila["abono"])
            movs.append(Movimiento(
                id=f"L{i:04d}", origen="libros",
                fecha=date.fromisoformat(fila["fecha"]),
                centavos=centavos,
                descripcion=fila["concepto"].strip(),
                referencia=fila["poliza"].strip(),
                tercero=fila["tercero"].strip(),
            ))
    return movs


# --------------------------------------------------------------------------
# Utilidades de fecha
# --------------------------------------------------------------------------
def _dias_habiles_entre(a: date, b: date) -> int:
    """Días hábiles entre dos fechas (valor absoluto, festivos excluidos)."""
    ini, fin = (a, b) if a <= b else (b, a)
    n, cur = 0, ini
    while cur < fin:
        cur += timedelta(days=1)
        if cur.weekday() < 5 and cur not in FESTIVOS:
            n += 1
    return n


def _en_ventana(a: date, b: date, ventana: int) -> bool:
    if abs((a - b).days) > ventana + 4:   # atajo barato antes de contar hábiles
        return False
    return _dias_habiles_entre(a, b) <= ventana


# --------------------------------------------------------------------------
# El motor
# --------------------------------------------------------------------------
def conciliar(banco: list[Movimiento], libros: list[Movimiento], *,
              ventana: int = VENTANA_DIAS_HABILES,
              tolerancia_centavos: int = 0) -> Resultado:
    """Cruza los dos lados en cuatro niveles, del más estricto al más flexible.

    `tolerancia_centavos` habilita el nivel 4 (cuadre por diferencia inmaterial).
    Viene en CERO a propósito: cada peso que se concilia por tolerancia es un
    peso que ningún humano miró. Subirlo es una decisión de control interno,
    no un detalle técnico.
    """
    import time
    t0 = time.perf_counter()

    res = Resultado(total_banco=len(banco), total_libros=len(libros))
    libre_b = {m.id: m for m in banco}
    libre_l = {m.id: m for m in libros}

    def emparejar(nivel: int, etiqueta: str, bs: list[Movimiento],
                  ls: list[Movimiento], dif: int = 0) -> None:
        res.cruces.append(Cruce(nivel, etiqueta, bs, ls, dif))
        for m in bs:
            libre_b.pop(m.id, None)
        for m in ls:
            libre_l.pop(m.id, None)

    # --- Nivel 1: mismo importe, misma fecha. Prueba irrefutable. -----------
    indice: dict[tuple[int, date], list[Movimiento]] = {}
    for m in libre_l.values():
        indice.setdefault((m.centavos, m.fecha), []).append(m)
    for b in sorted(libre_b.values(), key=lambda m: m.id):
        cubo = indice.get((b.centavos, b.fecha))
        while cubo:
            l = cubo.pop(0)
            if l.id in libre_l:
                emparejar(1, "Importe y fecha exactos", [b], [l])
                break

    # --- Nivel 2: mismo importe, fecha dentro de la ventana hábil. ----------
    por_monto: dict[int, list[Movimiento]] = {}
    for m in libre_l.values():
        por_monto.setdefault(m.centavos, []).append(m)
    for b in sorted(libre_b.values(), key=lambda m: m.id):
        for l in sorted(por_monto.get(b.centavos, []), key=lambda m: abs((m.fecha - b.fecha).days)):
            if l.id in libre_l and _en_ventana(b.fecha, l.fecha, ventana):
                emparejar(2, f"Importe exacto, desfase ≤{ventana} días hábiles", [b], [l])
                break

    # --- Nivel 3: agrupación uno-a-muchos (búsqueda de subconjuntos). -------
    #     Un depósito del banco que liquida varias facturas, o un pago del
    #     auxiliar que el banco partió en varias operaciones. Esto es
    #     combinatoria pura: exactamente el trabajo que NO debe hacer un LLM.
    def agrupar(uno: dict[str, Movimiento], muchos: dict[str, Movimiento],
                lado_uno: str) -> None:
        for m in sorted(uno.values(), key=lambda x: -abs(x.centavos)):
            if m.id not in uno:
                continue
            candidatos = [c for c in muchos.values()
                          if (c.centavos > 0) == (m.centavos > 0)
                          and abs(c.centavos) < abs(m.centavos)
                          and _en_ventana(m.fecha, c.fecha, ventana)]
            if len(candidatos) < 2:
                continue
            candidatos.sort(key=lambda c: c.fecha)
            candidatos = candidatos[:14]          # cota dura de trabajo
            hallado = None
            for k in range(2, MAX_PARTIDAS_AGRUPADAS + 1):
                for combo in combinations(candidatos, k):
                    if sum(c.centavos for c in combo) == m.centavos:
                        hallado = list(combo)
                        break
                if hallado:
                    break
            if hallado:
                bs, ls = ([m], hallado) if lado_uno == "banco" else (hallado, [m])
                emparejar(3, f"Agrupación 1:{len(hallado)}", bs, ls)

    agrupar(libre_b, libre_l, "banco")
    agrupar(libre_l, libre_b, "libros")

    # --- Nivel 4 (opcional): diferencia por debajo del umbral de materialidad.
    if tolerancia_centavos > 0:
        for b in sorted(libre_b.values(), key=lambda m: m.id):
            mejor, mejor_dif = None, tolerancia_centavos + 1
            for l in libre_l.values():
                if (l.centavos > 0) != (b.centavos > 0):
                    continue
                dif = abs(b.centavos - l.centavos)
                if dif <= tolerancia_centavos and dif < mejor_dif and \
                        _en_ventana(b.fecha, l.fecha, ventana):
                    mejor, mejor_dif = l, dif
            if mejor is not None:
                emparejar(4, "Diferencia bajo umbral de materialidad",
                          [b], [mejor], b.centavos - mejor.centavos)

    # --- Lo que sobrevive es la excepción: el trabajo que sí requiere criterio.
    res.excepciones = sorted(
        list(libre_b.values()) + list(libre_l.values()),
        key=lambda m: (m.fecha, -abs(m.centavos)),
    )
    res.segundos = time.perf_counter() - t0
    return res


# --------------------------------------------------------------------------
# Pistas para la IA (heurísticas baratas, NO conclusiones)
# --------------------------------------------------------------------------
_PALABRAS_COMISION = re.compile(r"COMISI|IVA COM|MANEJO DE CUENTA", re.I)
_PALABRAS_INTERES = re.compile(r"INTERES|ISR RETENIDO|RENDIMIENTO", re.I)


def pistas(m: Movimiento, todas: list[Movimiento]) -> list[str]:
    """Señales objetivas que se le entregan al modelo junto con la excepción.

    Son *pistas*, no diagnósticos: el modelo decide. Se calculan aquí porque
    son deterministas y baratas — pedirle a un LLM que detecte que 2,700 es
    divisible entre 9 sería pagar tokens por una división.
    """
    salida: list[str] = []
    texto = f"{m.descripcion} {m.referencia}".upper()

    if _PALABRAS_COMISION.search(texto):
        salida.append("El concepto contiene vocabulario de comisión bancaria.")
    if _PALABRAS_INTERES.search(texto):
        salida.append("El concepto contiene vocabulario de rendimientos o retención.")

    # Duplicado exacto dentro del mismo lado y misma fecha.
    gemelos = [o for o in todas if o.id != m.id and o.origen == m.origen
               and o.centavos == m.centavos and o.fecha == m.fecha]
    if gemelos:
        salida.append(f"Existe otro movimiento idéntico el mismo día ({gemelos[0].id}): "
                      "posible duplicado.")

    # Contraparte del lado opuesto que podría ser la pareja "casi" cuadrada.
    # Dos criterios distintos a propósito:
    #
    #  · TRANSPOSICIÓN — si la diferencia es múltiplo de 9 casi siempre es un
    #    error de captura de dígitos (45,890 vs 48,590). La regla del 9 es
    #    evidencia tan fuerte que justifica una banda amplia (hasta 20%).
    #  · CERCANÍA — cualquier otra diferencia sólo es señal si es realmente
    #    pequeña ($200 o 4%). Sin esa disciplina el modelo recibe media docena
    #    de coincidencias por azar y "explica" partidas que nada tienen que ver.
    #
    # En ambos casos se exige proximidad de fecha: un importe parecido con dos
    # semanas de distancia es una coincidencia, no una pista.
    transposiciones: list[tuple[int, Movimiento]] = []
    cercanas: list[tuple[int, Movimiento]] = []
    for o in todas:
        if o.origen == m.origen or (o.centavos > 0) != (m.centavos > 0):
            continue
        if not _en_ventana(m.fecha, o.fecha, 3):
            continue
        dif = abs(abs(o.centavos) - abs(m.centavos))
        if dif == 0:
            continue
        if dif % 900 == 0 and dif <= abs(m.centavos) // 5:
            transposiciones.append((dif, o))
        elif dif <= max(200_00, abs(m.centavos) // 25):
            cercanas.append((dif, o))

    for dif, o in sorted(transposiciones)[:2]:
        salida.append(
            f"Partida casi cuadrada en el otro sistema ({o.id}, ${o.monto:,.2f}, "
            f"{o.fecha:%d/%m}): diferencia de ${dif/100:,.2f}, múltiplo de 9 — "
            "firma típica de transposición de dígitos al capturar."
        )
    for dif, o in sorted(cercanas)[:1]:
        salida.append(
            f"Partida casi cuadrada en el otro sistema ({o.id}, ${o.monto:,.2f}, "
            f"{o.fecha:%d/%m}): diferencia de ${dif/100:,.2f}."
        )

    return salida
