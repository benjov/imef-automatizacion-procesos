"""El 10% que sí necesita criterio: clasificación de partidas en conciliación.

Este módulo es la frontera entre las dos mitades de la charla. Todo lo que el
motor pudo PROBAR ya quedó conciliado sin gastar un token. Lo que llega aquí
son las partidas que rompen la regla, y para cada una hace falta algo que un
`merge` no da: leer un concepto en lenguaje humano, cruzarlo con la política
contable y proponer un tratamiento.

Dos decisiones de diseño que son el argumento técnico de la charla:

1. **Salida estructurada, no prosa.** Se le pasa un JSON Schema al modelo
   (`output_config.format`) y la API garantiza que la respuesta cumpla el
   esquema. No se parsea texto libre ni se ruega "responde sólo con JSON".
   Una propuesta contable tiene que ser un objeto validable, auditable y
   comparable — no un párrafo.

2. **El prompt y el esquema viven aquí, en un solo lugar**, y tanto la app
   como `record_run.py` los importan. Es la única forma de que los respaldos
   pre-grabados correspondan de verdad a lo que la demo hace en vivo.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import (BANCO, BETAS_RESCATE, CUENTA, EMPRESA, ESFUERZO,
                     FALLBACKS, MODELO, PERIODO)
from .motor import Movimiento, pistas

# --------------------------------------------------------------------------
# Vocabulario cerrado. Que las categorías y acciones sean `enum` en el esquema
# no es cosmético: obliga al modelo a clasificar dentro del marco contable de
# la empresa en vez de inventar una taxonomía nueva en cada corrida, y hace
# que los resultados se puedan agregar y auditar entre periodos.
# --------------------------------------------------------------------------
CATEGORIAS = [
    "comision_bancaria",
    "rendimiento_financiero",
    "cheque_en_transito",
    "deposito_en_transito",
    "error_de_captura",
    "cargo_duplicado",
    "diferencia_cambiaria",
    "partida_de_corte",
    "cobro_no_identificado",
    "movimiento_no_reconocido",
]

ACCIONES = [
    "registrar_asiento",       # genera póliza de ajuste (en borrador)
    "corregir_poliza",         # el error está en libros, se corrige la captura
    "reclamar_al_banco",       # levantar aclaración ante la institución
    "dejar_en_conciliacion",   # partida legítima, se resuelve sola
    "investigar_y_escalar",    # nadie debe cerrarla en automático
]

ESQUEMA = {
    "type": "object",
    "properties": {
        "partidas": {
            "type": "array",
            "description": "Una entrada por partida en conciliación. Si dos o "
                           "más movimientos son la misma partida (por ejemplo "
                           "el mismo pago capturado con distinto importe en "
                           "cada sistema), agrúpalos en UNA sola entrada.",
            "items": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs de los movimientos que componen la partida.",
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Título corto y concreto, máximo 8 palabras.",
                    },
                    "categoria": {"type": "string", "enum": CATEGORIAS},
                    "explicacion": {
                        "type": "string",
                        "description": "Dos o tres frases explicando qué pasó y "
                                       "por qué esa es la conclusión. Dirigido a "
                                       "un contralor, sin jerga técnica de IA.",
                    },
                    "accion": {"type": "string", "enum": ACCIONES},
                    "asiento": {
                        "type": "array",
                        "description": "Renglones del asiento de ajuste propuesto. "
                                       "Arreglo VACÍO si la partida no genera asiento.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cuenta": {
                                    "type": "string",
                                    "description": "Clave y nombre, como en el "
                                                   "catálogo de la política 7.3.",
                                },
                                "cargo": {"type": "number"},
                                "abono": {"type": "number"},
                            },
                            "required": ["cuenta", "cargo", "abono"],
                            "additionalProperties": False,
                        },
                    },
                    "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
                    "requiere_humano": {
                        "type": "boolean",
                        "description": "true si un humano debe decidir antes de "
                                       "aplicar nada, por política o por duda "
                                       "genuina.",
                    },
                    "politica": {
                        "type": "string",
                        "description": "Sección del manual que sustenta la acción "
                                       "(por ejemplo '7.5'). Cadena vacía si ninguna aplica.",
                    },
                },
                "required": ["ids", "titulo", "categoria", "explicacion", "accion",
                             "asiento", "confianza", "requiere_humano", "politica"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["partidas"],
    "additionalProperties": False,
}


SISTEMA = f"""\
Eres el analista contable que resuelve las partidas en conciliación de \
{EMPRESA}, cuenta {BANCO} {CUENTA}, periodo {PERIODO}.

Un motor determinista ya concilió todo lo que se podía probar por importe y \
fecha. Lo que recibes es únicamente el residuo: las partidas que rompen la \
regla. Tu trabajo es clasificar cada una, explicarla y proponer el tratamiento \
contable conforme al manual de políticas que se te entrega.

Cómo trabajar:

- Apégate al manual. Cuando una acción esté sustentada en una sección, cítala.
- Agrupa. Si un mismo hecho aparece en los dos sistemas con importes distintos, \
es UNA partida con dos IDs, no dos partidas.
- Los asientos deben cuadrar: la suma de cargos igual a la suma de abonos, con \
las cuentas del catálogo de la sección 7.3.
- Calibra la confianza con honestidad. `baja` cuando la evidencia no alcanza; \
`media` cuando la hipótesis es razonable pero admite otra lectura.
- Marca `requiere_humano` cuando la política lo exija o cuando tú no puedas \
resolverlo con la información disponible. Decir "no sé, que lo vea una persona" \
es una respuesta correcta y valiosa; inventar una explicación plausible para \
cerrar la partida no lo es.
- Nunca propongas regularizar contablemente un movimiento no reconocido.
- Escribe para un contralor: frases directas, sin adjetivos de más y sin \
vocabulario de inteligencia artificial.
"""


def _bloque_movimiento(m: Movimiento, todos: list[Movimiento]) -> str:
    lineas = [
        f"[{m.id}] {'BANCO ' if m.origen == 'banco' else 'LIBROS'} | "
        f"{m.fecha:%d/%m/%Y} | ${m.monto:,.2f} | {m.descripcion}"
    ]
    if m.referencia:
        lineas.append(f"      referencia: {m.referencia}")
    if m.tercero:
        lineas.append(f"      tercero: {m.tercero}")
    for p in pistas(m, todos):
        lineas.append(f"      · {p}")
    return "\n".join(lineas)


def construir_prompt(excepciones: list[Movimiento], todos: list[Movimiento],
                     cartera_csv: str, politicas_md: str) -> str:
    """Arma el mensaje del usuario: excepciones + pistas + cartera + política."""
    partidas = "\n".join(_bloque_movimiento(m, todos) for m in excepciones)
    return f"""\
## Partidas en conciliación ({len(excepciones)})

Los renglones que empiezan con `·` son señales objetivas calculadas por el \
motor (aritmética y coincidencias de texto). Son pistas, no conclusiones: \
verifícalas antes de apoyarte en ellas.

{partidas}

## Cartera de clientes abierta al corte

```csv
{cartera_csv.strip()}
```

## Manual de políticas contables (extracto vigente)

{politicas_md.strip()}

## Instrucción

Clasifica y resuelve las {len(excepciones)} partidas anteriores. Ordena tu \
respuesta de mayor a menor importe absoluto."""


def analizar(cliente, excepciones: list[Movimiento], todos: list[Movimiento],
             cartera_csv: str, politicas_md: str, *, al_recibir=None) -> dict:
    """Llama a la API con salida estructurada y devuelve el resultado parseado.

    `al_recibir(tokens_salida)` se invoca durante el streaming para que la UI
    pueda mostrar el contador de tokens (y por tanto el costo) subiendo en vivo.
    Se usa streaming porque una respuesta larga sin streaming se arriesga a
    agotar el tiempo de la conexión HTTP — y porque ver avanzar el contador
    delante del público vale más que cualquier lámina sobre costos.
    """
    prompt = construir_prompt(excepciones, todos, cartera_csv, politicas_md)

    with cliente.beta.messages.stream(
        model=MODELO,
        max_tokens=16000,
        system=SISTEMA,
        betas=BETAS_RESCATE,
        fallbacks=FALLBACKS,
        output_config={"format": {"type": "json_schema", "schema": ESQUEMA},
                       "effort": ESFUERZO},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for evento in stream:
            if not al_recibir:
                continue
            if evento.type == "message_delta":
                uso = getattr(evento, "usage", None)
                al_recibir(getattr(uso, "output_tokens", None) if uso else None)
            elif evento.type == "content_block_delta":
                al_recibir(None)   # latido: hay avance, aún sin conteo exacto
        mensaje = stream.get_final_message()

    # Nunca leer content[0] sin revisar antes stop_reason: si toda la cadena
    # de modelos declinó, `content` viene vacío y el índice revienta con un
    # error que no dice nada.
    if mensaje.stop_reason == "refusal":
        raise RuntimeError(
            "El clasificador de seguridad declinó la solicitud y el modelo de "
            "rescate también. Vuelve a intentar o usa el Modo respaldo."
        )

    textos = [b.text for b in mensaje.content if b.type == "text"]
    if not textos:
        raise RuntimeError(
            f"La respuesta no trae texto (stop_reason={mensaje.stop_reason})."
        )

    rescatado = next((b.to.model for b in mensaje.content if b.type == "fallback"), None)
    return {
        "modelo": mensaje.model,
        "esfuerzo": ESFUERZO,
        "rescatado_por": rescatado,
        "partidas": json.loads(textos[0])["partidas"],
        "tokens_entrada": mensaje.usage.input_tokens,
        "tokens_salida": mensaje.usage.output_tokens,
    }


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")
