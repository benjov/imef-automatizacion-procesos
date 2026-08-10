"""Configuración compartida de las demos."""

from pathlib import Path

# --------------------------------------------------------------------------
# Modelo. Se cambia AQUÍ y en `demos/record_run.py` (los respaldos guardan el
# nombre del modelo con el que fueron grabados).
# --------------------------------------------------------------------------
MODELO = "claude-opus-5"

# Nivel de esfuerzo: cuánto razona el modelo antes de responder
# (low | medium | high | xhigh | max).
#
# Medido sobre este caso el 8 de agosto de 2026, con las 14 excepciones reales:
#   low     ~38 s   ~$2.12 MXN   clasificación correcta en los 10 casos sembrados
#   medium  ~61 s   ~$2.83 MXN   misma clasificación, 60% más de espera
#
# Se queda en "low" por la razón que importa en vivo: son 23 segundos menos de
# silencio frente al público, sin diferencia de calidad observable. Si algún
# día el caso se vuelve más ambiguo, subirlo es cambiar esta línea.
ESFUERZO = "low"

# --------------------------------------------------------------------------
# Rescate ante rechazos del clasificador de seguridad.
#
# Preparando esta charla, una petición completamente inocua (escribir un lector
# de CSV bancario, ver el cuaderno de Colab) fue rechazada con categoría
# "cyber". Reintentada, pasó: el rechazo es intermitente. Ocurre con datos
# transaccionales y generación de código, que es exactamente lo que hacen estas
# demos.
#
# `fallbacks="default"` hace que la API reencamine la petición a otro modelo
# dentro de la misma llamada cuando eso pasa. No cuesta nada cuando no se
# dispara, y evita que la demo se caiga en vivo por un falso positivo.
BETAS_RESCATE = ["server-side-fallback-2026-07-01"]
FALLBACKS = "default"

# Precio de lista vigente de claude-opus-5, en dólares por millón de tokens.
# Se usa sólo para mostrar el costo estimado en pantalla: en una charla sobre
# automatización de procesos, el costo por corrida es parte del argumento.
USD_POR_MTOK_ENTRADA = 5.00
USD_POR_MTOK_SALIDA = 25.00
TIPO_DE_CAMBIO = 18.50  # MXN/USD, referencia para convertir en pantalla


def costo_mxn(tokens_entrada: int, tokens_salida: int) -> float:
    """Costo estimado de una corrida, en pesos."""
    usd = (tokens_entrada / 1_000_000) * USD_POR_MTOK_ENTRADA \
        + (tokens_salida / 1_000_000) * USD_POR_MTOK_SALIDA
    return usd * TIPO_DE_CAMBIO


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
DIR_DEMOS = Path(__file__).resolve().parent.parent      # demos/
DIR_DATA = DIR_DEMOS / "data"
DIR_RESPALDOS = DIR_DATA / "respaldos"

DIR_FORMATOS = DIR_DATA / "formatos_reales"

ARCHIVO_BANCO = DIR_DATA / "estado_cuenta.csv"
ARCHIVO_LIBROS = DIR_DATA / "auxiliar_contable.csv"
ARCHIVO_CARTERA = DIR_DATA / "cuentas_por_cobrar.csv"
ARCHIVO_POLITICAS = DIR_DATA / "politicas_contables.md"

# Cómo llegan de verdad los estados de cuenta. Sirven sólo para la narrativa
# de la Demo 1: el motor trabaja sobre la versión ya normalizada.
#
# Los nombres de institución son genéricos a propósito — los patrones de
# formato son reales, pero atribuirlos a un banco concreto sería afirmar algo
# que no se puede verificar delante de alguien que lo usa a diario.
FORMATOS_REALES = [
    ("Banco A · CSV con membrete", "banco_a_export.csv", "csv",
     "Los encabezados reales están en el renglón 6: arriba hay membrete y "
     "abajo un total. Un lector ingenuo se rompe en la primera línea."),
    ("Banco B · dos fechas", "banco_b_movimientos.csv", "csv",
     "Trae fecha de operación Y fecha de aplicación, y no siempre coinciden. "
     "¿Contra cuál concilias? De esa decisión salen la mitad de los desfases."),
    ("Banco C · signo arrastrado", "banco_c_export.csv", "csv",
     "El negativo va al final del número: `169,052.96-`. Herencia de "
     "mainframe. Y el concepto viene truncado a 24 caracteres, así que la "
     "referencia del proveedor se pierde."),
    ("Banco D · texto de un PDF", "banco_d_extracto.txt", "text",
     "No es un archivo de datos: es texto extraído de un PDF. Ancho fijo, "
     "membrete repetido en cada página, saltos de página y leyenda legal. "
     "Es el peor caso — y es el más común."),
]

# --------------------------------------------------------------------------
# Contexto del caso (aparece en pantalla y en los prompts)
# --------------------------------------------------------------------------
EMPRESA = "Industrias del Norte, S.A. de C.V."
BANCO = "BBVA México"
CUENTA = "0198 4471 92"
PERIODO = "Septiembre 2026"

# --------------------------------------------------------------------------
# Paleta validada para proyector y videollamada (contraste AA, segura para
# daltonismo). Rojo reservado exclusivamente para anomalías.
# --------------------------------------------------------------------------
AZUL = "#2563EB"
AMBAR = "#B45309"
TEAL = "#0D9488"
ROJO = "#B91C1C"
GRIS = "#6B7280"
TINTA = "#1F2937"
PALETA = [AZUL, AMBAR, TEAL, GRIS]

# Semáforo de confianza de las propuestas del modelo.
COLOR_CONFIANZA = {"alta": TEAL, "media": AMBAR, "baja": ROJO}
ICONO_CONFIANZA = {"alta": "🟢", "media": "🟡", "baja": "🔴"}
