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

ARCHIVO_BANCO = DIR_DATA / "estado_cuenta.csv"
ARCHIVO_LIBROS = DIR_DATA / "auxiliar_contable.csv"
ARCHIVO_CARTERA = DIR_DATA / "cuentas_por_cobrar.csv"
ARCHIVO_POLITICAS = DIR_DATA / "politicas_contables.md"

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
