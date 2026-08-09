"""Agente de cierre: el modelo decide qué herramientas usar y en qué orden.

La diferencia con la Demo 1 no es de tamaño, es de naturaleza. En la Demo 1
nosotros decidimos el flujo: corre el motor, toma el residuo, clasifícalo. Aquí
sólo se entrega un objetivo ("cierra la conciliación de septiembre") y un
cinturón de herramientas; el modelo arma el plan.

Tres cosas que conviene señalar en voz alta durante la demo:

1. **La herramienta más importante ejecuta código determinista.** Cuando el
   agente llama `ejecutar_conciliacion` no está "conciliando con IA": está
   invocando el mismo motor de la Demo 1. El modelo orquesta; la aritmética la
   sigue haciendo código auditable.

2. **El control de autorización vive en el código, no en el prompt.**
   `registrar_asiento_borrador` verifica los umbrales de la política 7.2 y se
   niega a registrar en firme, pase lo que pase. Un guardarraíl que depende de
   que el modelo "se porte bien" no es un control interno; es una esperanza.

3. **Nada se escribe en ningún sistema.** El agente propone; la autorización
   es un acto humano posterior.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date

from .config import (ARCHIVO_BANCO, ARCHIVO_CARTERA, ARCHIVO_LIBROS,
                     ARCHIVO_POLITICAS, BANCO, BETAS_RESCATE, CUENTA, EMPRESA,
                     ESFUERZO, FALLBACKS, MODELO, PERIODO)
from .motor import cargar_banco, cargar_libros, conciliar, pistas

# --------------------------------------------------------------------------
# Umbrales de autorización — copia literal de la política 7.2. Están aquí, en
# código, porque un control interno no puede vivir sólo dentro de un prompt.
# --------------------------------------------------------------------------
UMBRALES = [
    (50_000.00, "Contador General"),
    (250_000.00, "Contralor"),
    (float("inf"), "Dirección de Finanzas"),
]


def quien_autoriza(importe: float) -> str:
    for tope, cargo in UMBRALES:
        if abs(importe) <= tope:
            return cargo
    return "Dirección de Finanzas"


# --------------------------------------------------------------------------
# Definición de herramientas
# --------------------------------------------------------------------------
HERRAMIENTAS = [
    {
        "name": "ejecutar_conciliacion",
        "description": (
            "Cruza el estado de cuenta bancario contra el auxiliar contable del "
            "periodo con el motor determinista de la empresa (aritmética exacta, "
            "sin IA) y devuelve las métricas del cruce y las partidas que quedaron "
            "sin conciliar. Es SIEMPRE el primer paso de una conciliación: no "
            "intentes cruzar movimientos mentalmente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tolerancia_pesos": {
                    "type": "number",
                    "description": "Diferencia máxima en pesos para dar por cuadrada "
                                   "una pareja (política 7.1: materialidad de $500). "
                                   "Usa 0 para el cruce estricto.",
                },
            },
            "required": ["tolerancia_pesos"],
        },
    },
    {
        "name": "consultar_cartera",
        "description": (
            "Busca facturas abiertas de clientes con saldo parecido al importe "
            "indicado. Sirve para identificar depósitos que el banco reportó sin "
            "referencia utilizable. Devuelve SIEMPRE las candidatas cercanas, no "
            "sólo la coincidencia exacta, para que puedas juzgar si hay "
            "ambigüedad entre varias facturas (política 7.6)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "importe": {"type": "number", "description": "Importe del depósito a identificar."},
                "tolerancia_pesos": {
                    "type": "number",
                    "description": "Holgura mínima de búsqueda en pesos. La "
                                   "herramienta amplía la banda por su cuenta si "
                                   "este valor es demasiado estrecho.",
                },
            },
            "required": ["importe", "tolerancia_pesos"],
        },
    },
    {
        "name": "consultar_politica",
        "description": (
            "Devuelve el texto íntegro de una o varias secciones del manual de "
            "políticas contables. Consúltalo antes de decidir el tratamiento de "
            "una partida: no supongas los umbrales ni las facultades de "
            "autorización. Pide en UNA sola llamada todas las secciones que vayas "
            "a necesitar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "secciones": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7"],
                    },
                    "description": ("7.1 materialidad · 7.2 facultades de autorización · "
                                    "7.3 catálogo de cuentas · 7.4 partidas en conciliación · "
                                    "7.5 movimientos no reconocidos · 7.6 cobros no "
                                    "identificados · 7.7 evidencia para auditoría"),
                },
            },
            "required": ["secciones"],
        },
    },
    {
        "name": "registrar_asiento_borrador",
        "description": (
            "Deja un asiento de ajuste en la cola de pólizas BORRADOR. El asiento "
            "no afecta la contabilidad: queda pendiente de que la persona facultada "
            "lo autorice. La herramienta valida por su cuenta los umbrales y las "
            "prohibiciones del manual y puede rechazar la propuesta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concepto": {"type": "string", "description": "Descripción del ajuste."},
                "categoria": {
                    "type": "string",
                    "description": "Tipo de partida: comision_bancaria, "
                                   "rendimiento_financiero, error_de_captura, "
                                   "diferencia_cambiaria, cargo_duplicado, "
                                   "movimiento_no_reconocido, cobro_no_identificado.",
                },
                "renglones": {
                    "type": "array",
                    "description": "Renglones del asiento. La suma de cargos debe "
                                   "ser igual a la suma de abonos.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cuenta": {"type": "string"},
                            "cargo": {"type": "number"},
                            "abono": {"type": "number"},
                        },
                        "required": ["cuenta", "cargo", "abono"],
                    },
                },
            },
            "required": ["concepto", "categoria", "renglones"],
        },
    },
]


# --------------------------------------------------------------------------
# Implementación de las herramientas
# --------------------------------------------------------------------------
def _seccion_politica(clave: str) -> str:
    texto = ARCHIVO_POLITICAS.read_text(encoding="utf-8")
    partes = re.split(r"^## (?=7\.\d)", texto, flags=re.M)
    for parte in partes:
        if parte.startswith(clave):
            return "## " + parte.strip()
    return f"No existe la sección {clave} en el manual."


def _conciliacion(tolerancia_pesos: float) -> dict:
    banco = cargar_banco(ARCHIVO_BANCO)
    libros = cargar_libros(ARCHIVO_LIBROS)
    res = conciliar(banco, libros,
                    tolerancia_centavos=int(round(tolerancia_pesos * 100)))
    todos = banco + libros
    return {
        "movimientos_totales": res.total_movimientos,
        "conciliados": res.conciliados,
        "tasa_automatica": round(res.tasa, 4),
        "milisegundos": round(res.segundos * 1000, 1),
        "monto_en_excepcion": round(res.monto_en_excepcion, 2),
        "niveles_de_cruce": res.por_nivel(),
        "partidas_sin_conciliar": [
            {**m.como_dict(), "señales": pistas(m, todos)} for m in res.excepciones
        ],
    }


def _cartera(importe: float, tolerancia_pesos: float) -> dict:
    """Devuelve la coincidencia exacta Y las cercanas.

    Detalle de diseño que vale la pena señalar en la demo: una versión anterior
    de esta herramienta sólo devolvía la coincidencia exacta. El agente veía una
    única factura por $93,600, concluía "no hay ambigüedad" y aplicaba el
    depósito — razonando bien sobre información incompleta. Pero existe otra
    factura por $93,615, y la política 7.6 justamente prohíbe aplicar cuando hay
    candidatas parecidas.

    El modelo no estaba fallando: la herramienta le escondía lo que necesitaba
    ver. Por eso la banda de búsqueda se amplía aquí por cuenta propia, sin
    depender de que quien llama pida la tolerancia correcta. Diseñar la
    herramienta ES diseñar el control.
    """
    filas = list(csv.DictReader(io.StringIO(
        ARCHIVO_CARTERA.read_text(encoding="utf-8"))))
    hoy = date(2026, 9, 30)
    objetivo = abs(importe)
    # Banda mínima: lo que pidan, o el 1% del importe, o $500. La que sea mayor.
    banda = max(tolerancia_pesos, objetivo * 0.01, 500.0)

    candidatas = []
    for f in filas:
        saldo = float(f["saldo"])
        dif = round(saldo - objetivo, 2)
        if abs(dif) <= banda:
            venc = date.fromisoformat(f["fecha_vencimiento"])
            candidatas.append({
                "folio": f["folio"], "cliente": f["cliente"], "saldo": saldo,
                "vencimiento": f["fecha_vencimiento"],
                "estatus": "VENCIDA" if venc < hoy else "vigente",
                "diferencia": dif,
                "coincidencia_exacta": abs(dif) < 0.005,
            })
    candidatas.sort(key=lambda c: abs(c["diferencia"]))
    exactas = sum(1 for c in candidatas if c["coincidencia_exacta"])
    return {
        "buscado": objetivo,
        "banda_de_busqueda": round(banda, 2),
        "candidatas": candidatas,
        "coincidencias_exactas": exactas,
        "total_facturas_abiertas": len(filas),
        "advertencia": (
            "Hay más de una factura con importe similar: la política 7.6 impide "
            "aplicar el depósito a alguna de ellas."
            if len(candidatas) > 1 else ""
        ),
    }


def _registrar(concepto: str, categoria: str, renglones: list[dict]) -> dict:
    """Aquí vive el control interno. Ningún prompt puede saltárselo."""
    cargos = round(sum(float(r.get("cargo") or 0) for r in renglones), 2)
    abonos = round(sum(float(r.get("abono") or 0) for r in renglones), 2)

    if abs(cargos - abonos) > 0.005:
        return {"estatus": "RECHAZADO",
                "motivo": f"El asiento no cuadra: cargos ${cargos:,.2f} contra "
                          f"abonos ${abonos:,.2f}. Corrige los renglones."}

    if categoria == "movimiento_no_reconocido":
        return {"estatus": "RECHAZADO",
                "motivo": "La política 7.5 prohíbe regularizar contablemente un "
                          "movimiento no reconocido antes de agotar la aclaración "
                          "bancaria, cualquiera que sea su importe. Escala la "
                          "partida al Contralor en vez de registrarla."}

    autoriza = quien_autoriza(cargos)
    return {"estatus": "EN BORRADOR",
            "importe": cargos,
            "autoriza": autoriza,
            "nota": f"Asiento encolado sin afectar la contabilidad. Requiere "
                    f"autorización de: {autoriza} (política 7.2). Queda "
                    f"registrado en bitácora quién lo propuso y cuándo."}


def ejecutar_herramienta(nombre: str, args: dict) -> dict:
    if nombre == "ejecutar_conciliacion":
        return _conciliacion(float(args.get("tolerancia_pesos", 0)))
    if nombre == "consultar_cartera":
        return _cartera(float(args["importe"]), float(args.get("tolerancia_pesos", 0)))
    if nombre == "consultar_politica":
        claves = args.get("secciones") or ([args["seccion"]] if args.get("seccion") else [])
        return {"secciones": {c: _seccion_politica(c) for c in claves}}
    if nombre == "registrar_asiento_borrador":
        return _registrar(args["concepto"], args.get("categoria", ""),
                          args.get("renglones", []))
    return {"error": f"Herramienta desconocida: {nombre}"}


# --------------------------------------------------------------------------
# El bucle del agente
# --------------------------------------------------------------------------
SISTEMA = f"""\
Eres el asistente de cierre contable de {EMPRESA}. Trabajas sobre la cuenta \
{BANCO} {CUENTA}, periodo {PERIODO}.

Escribe siempre en español, desde la primera palabra, incluidos los avisos \
breves de lo que vas a hacer a continuación.

Tienes herramientas para conciliar, consultar la cartera de clientes, leer el \
manual de políticas y encolar asientos en borrador. Úsalas: no calcules a mano \
lo que una herramienta calcula exacto, y no supongas una política que puedes \
leer.

Método:
1. Ejecuta la conciliación antes que nada.
2. Consulta las secciones del manual que apliquen a lo que encontraste.
3. Resuelve cada partida. Encola en borrador únicamente los asientos que la \
política permita; lo que deba escalarse, escálalo.
4. Cierra con el acta de conciliación.

Si una herramienta rechaza una propuesta, no insistas ni busques la vuelta: \
lee el motivo y ajusta el tratamiento.

El acta final se dirige al Contralor. Estructura:

**ACTA DE CONCILIACIÓN BANCARIA** — encabezado con cuenta y periodo.
**1. Resultado del cruce automático** — cifras del motor, incluido el tiempo.
**2. Partidas resueltas** — una línea por partida: qué era y qué se hizo.
**3. Asientos en borrador pendientes de autorización** — importe y quién autoriza.
**4. Partidas que requieren decisión humana** — qué falta y de quién depende.
**5. Efecto en el saldo** — el impacto de los ajustes propuestos.

Escribe en español, en frases directas, para alguien que va a firmar el \
documento. Sin viñetas decorativas, sin adjetivos de más y sin vocabulario de \
inteligencia artificial. Reporta lo que realmente pasó: si algo quedó abierto, \
dilo con todas sus letras.
"""

INSTRUCCIONES = {
    "Cierre completo del mes":
        "Concilia la cuenta del periodo y prepárame el paquete de cierre: "
        "resuelve lo que se pueda resolver conforme a política, encola los "
        "asientos que correspondan y dime qué necesita mi decisión.",
    "Sólo lo que necesita mi firma":
        "Concilia la cuenta y devuélveme únicamente las partidas que requieren "
        "autorización o decisión humana, con el importe y el motivo. Lo que "
        "puedas dejar resuelto conforme a política, resuélvelo sin consultarme.",
    "Revisión de riesgos":
        "Concilia la cuenta y señálame cualquier partida que pudiera indicar un "
        "cobro indebido, un duplicado o un movimiento ajeno a la operación. "
        "Ordénalas por riesgo, no por importe.",
}


def _para_reenviar(bloques: list) -> list:
    """Deja el turno del asistente listo para mandarlo de vuelta a la API.

    Si a media respuesta entró un modelo de rescate, todo lo que el modelo
    original alcanzó a producir antes del corte (razonamiento, llamadas a
    herramientas a medio formar) ya no es válido para el que continuó. La API
    pide omitir esos bloques y conservar el resto.

    Sin fallback —el caso de siempre— esto no toca nada.
    """
    ultimo = max((i for i, b in enumerate(bloques) if b.type == "fallback"),
                 default=None)
    if ultimo is None:
        return bloques
    descartar = {"thinking", "redacted_thinking", "tool_use"}
    return [b for i, b in enumerate(bloques)
            if not (i < ultimo and b.type in descartar)]


def correr(cliente, instruccion: str, *, al_paso=None, max_vueltas: int = 12) -> dict:
    """Ejecuta el bucle de tool use hasta que el agente termina.

    `al_paso(evento)` recibe cada paso para que la UI lo pinte en vivo:
      {"tipo": "texto",       "texto": ...}
      {"tipo": "herramienta", "nombre": ..., "args": ..., "resultado": ...}
    """
    mensajes = [{"role": "user", "content": instruccion}]
    pasos: list[dict] = []
    entrada = salida = 0

    for _ in range(max_vueltas):
        r = cliente.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            system=SISTEMA,
            tools=HERRAMIENTAS,
            betas=BETAS_RESCATE,
            fallbacks=FALLBACKS,
            output_config={"effort": ESFUERZO},
            messages=mensajes,
        )
        entrada += r.usage.input_tokens
        salida += r.usage.output_tokens

        if r.stop_reason == "refusal":
            raise RuntimeError(
                "El clasificador de seguridad declinó la solicitud y el modelo "
                "de rescate también. Vuelve a intentar o usa el Modo respaldo."
            )

        for bloque in r.content:
            if bloque.type == "text" and bloque.text.strip():
                evento = {"tipo": "texto", "texto": bloque.text}
                pasos.append(evento)
                if al_paso:
                    al_paso(evento)

        if r.stop_reason != "tool_use":
            break

        mensajes.append({"role": "assistant", "content": _para_reenviar(r.content)})
        resultados = []
        for bloque in r.content:
            if bloque.type != "tool_use":
                continue
            salida_herr = ejecutar_herramienta(bloque.name, dict(bloque.input))
            evento = {"tipo": "herramienta", "nombre": bloque.name,
                      "args": dict(bloque.input), "resultado": salida_herr}
            pasos.append(evento)
            if al_paso:
                al_paso(evento)
            resultados.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": json.dumps(salida_herr, ensure_ascii=False, default=str),
            })
        mensajes.append({"role": "user", "content": resultados})

    acta = "\n\n".join(p["texto"] for p in pasos if p["tipo"] == "texto")
    return {"modelo": MODELO, "esfuerzo": ESFUERZO, "instruccion": instruccion,
            "pasos": pasos, "acta": acta,
            "tokens_entrada": entrada, "tokens_salida": salida}
