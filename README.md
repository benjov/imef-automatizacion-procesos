# Automatización de Procesos Financieros

Demos de la sesión del **Comité Técnico Nacional de Transformación y Economía
Digital del IMEF** — 13 de agosto de 2026.
**Benjamín Oliva Vázquez** · Socio en Analítica Boutique · Principal en Games Economics

> **La tesis:** el 90% de un proceso financiero lo resuelve una regla. El 10%
> que la rompe es donde se va el 80% del tiempo del área — y ahí, sólo ahí, es
> donde un modelo de lenguaje cambia la aritmética.

El caso es una **conciliación bancaria**: 226 movimientos, dos sistemas que no
se hablan, y un cierre de mes que hay que firmar.

| | Qué muestra |
|---|---|
| **1 · Conciliación** | Un motor determinista cuadra el **93.8% en 0.3 ms y por $0.00**. Las 14 partidas que sobreviven van al modelo, que devuelve un objeto validado contra esquema. |
| **2 · Agente de cierre** | Se le da un objetivo, no un procedimiento. Elige herramientas, lee el manual de políticas y encola asientos en borrador. El control de autorización vive en el código. |
| **3 · Cuaderno de Colab** | Tu banco no usa estas columnas. La IA escribe el adaptador; el motor no se toca. |

---

## Correrlo en local

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r demos/requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y pon tu key
streamlit run demos/app.py
```

Sin key o sin internet: activa **Modo respaldo** en el panel lateral. Reproduce
corridas reales pre-grabadas y se ve idéntico a la corrida en vivo.

```bash
python demos/pruebas_de_humo.py      # ejecuta ambas páginas, sin gastar tokens
```

---

## Cómo funciona la conciliación

### El motor (`demos/shared/motor.py`) — sin IA

Cruza los dos archivos en cuatro niveles, del más estricto al más flexible, y
deja como excepción sólo lo que **no puede probar**:

| Nivel | Criterio | Movimientos |
|---|---|---|
| 1 | Importe y fecha exactos | 152 |
| 2 | Importe exacto, desfase ≤ 3 días hábiles | 56 |
| 3 | Agrupación uno-a-muchos (búsqueda de subconjuntos) | 4 |
| 4 | Diferencia bajo el umbral de materialidad | *apagado por defecto* |

El nivel 3 es el que sorprende al público: un depósito de $487,300 que liquida
tres facturas distintas. Encontrar esa combinación es combinatoria — el trabajo
que un modelo de lenguaje **no** debe hacer.

El nivel 4 viene en cero a propósito. Cada peso conciliado por tolerancia es un
peso que ningún humano revisó: subir ese número es una decisión de control
interno, no un ajuste técnico. En la demo hay un control deslizante para
mostrarlo en vivo.

Todo el dinero se maneja en **centavos enteros**. Comparar flotantes es como se
producen las diferencias de un peso que nadie puede explicar.

### El modelo (`demos/shared/analisis.py`) — sólo el residuo

Recibe las 14 excepciones con las señales objetivas que calculó el motor
(divisibilidad entre 9, duplicados exactos, partidas casi cuadradas), la cartera
abierta y el manual de políticas. Devuelve **salida estructurada**: se le pasa un
JSON Schema y la API garantiza que la respuesta lo cumpla. No se parsea texto
libre ni se ruega "responde sólo con JSON".

Categoría y acción son listas cerradas; el asiento es un arreglo de renglones
con cuenta, cargo y abono. Un párrafo hay que leerlo y creerle; un objeto
validado se compara entre periodos, se suma, se audita y se conecta al ERP.

### Los casos sembrados

Los datos son sintéticos y deterministas (`demos/data/generar_datos.py`, semilla
fija). Cada caso es una partida que un contador reconoce al instante:

| # | Caso | Quién lo resuelve |
|---|---|---|
| 1 | Un depósito que liquida 3 facturas | **Motor** (nivel 3) |
| 2 | Comisiones bancarias e IVA no registrados | Modelo → asiento |
| 3 | Cheque en tránsito | Modelo → dejar en conciliación |
| 4 | Cargo duplicado del banco | Modelo → reclamar |
| 5 | Transposición de dígitos (45,890 vs 48,590; la diferencia es múltiplo de 9) | Modelo → corregir póliza |
| 6 | Diferencia cambiaria de $45.50 en un pago en dólares | Modelo → bajo materialidad |
| 7 | Depósito sin referencia, con **dos** facturas candidatas parecidas | Modelo → *no aplicar* (política 7.6) |
| 8 | Intereses ganados e ISR retenido | Modelo → asiento |
| 9 | Cargo no reconocido | Modelo → **escalar, nunca regularizar** |
| 10 | Traspaso registrado en el periodo siguiente | Modelo → partida de corte |

El caso 7 es una trampa deliberada: hay una coincidencia exacta *y* otra factura
a $15 de distancia. La política prohíbe aplicar cuando hay ambigüedad, y el
modelo tiene que notarlo.

### Cómo llegan de verdad los estados de cuenta

`demos/data/formatos_reales/` tiene los mismos movimientos exportados por cuatro
instituciones distintas. Sirven sólo para la narrativa de la demo — el motor
trabaja sobre la versión ya normalizada — pero son el argumento visual de por
qué existe la primera capa determinista:

| Archivo | El patrón |
|---|---|
| `banco_a_export.csv` | Encabezados en el renglón 6: arriba membrete, abajo un total |
| `banco_b_movimientos.csv` | Dos fechas, operación y aplicación, que no coinciden |
| `banco_c_export.csv` | Signo negativo **arrastrado** (`169,052.96-`) y concepto truncado a 24 caracteres |
| `banco_d_extracto.txt` | Ancho fijo extraído de un PDF, con membrete repetido por página |

Los nombres de institución son **genéricos a propósito**. Los patrones de
formato son reales y reconocibles; atribuirlos a un banco concreto sería afirmar
algo que no se puede verificar delante de alguien que lo usa a diario.

---

## El agente y sus controles

`demos/shared/agente.py` expone cuatro herramientas. Tres detalles que importan
más que el número de herramientas:

**La herramienta principal ejecuta código determinista.** Cuando el agente llama
`ejecutar_conciliacion` no está "conciliando con IA": invoca el mismo motor. El
modelo orquesta; la aritmética la hace código auditable.

**El control de autorización está en el código, no en el prompt.**
`registrar_asiento_borrador` verifica que el asiento cuadre, aplica los umbrales
de la política 7.2 y **rechaza** regularizar un movimiento no reconocido — pase
lo que pase por el prompt. Un guardarraíl que depende de que el modelo se porte
bien no es un control interno, es una esperanza.

**Diseñar la herramienta es diseñar el control.** Una versión anterior de
`consultar_cartera` sólo devolvía la coincidencia exacta. El agente veía una
factura por $93,600, concluía "no hay ambigüedad" y aplicaba el depósito —
razonando correctamente sobre información incompleta. La herramienta le escondía
lo que la política 7.6 le pedía detectar. Ahora amplía la banda de búsqueda por
su cuenta. El comentario en el código conserva la historia.

Nada se escribe en ningún sistema. El agente propone; firmar es humano.

---

## Rechazos del clasificador

Preparando esta charla, una petición **completamente inocua** —escribir un lector
de CSV bancario, en el cuaderno de Colab— fue rechazada con `stop_reason:
"refusal"`, categoría `cyber`. Reintentada, pasó: el rechazo es intermitente.

Las tres rutas usan `fallbacks="default"`, que reencamina la petición a otro
modelo dentro de la misma llamada. No cuesta nada cuando no se dispara y evita
que una demo se caiga en vivo por un falso positivo.

Regla general, aplicada en todo el repo: **nunca leas `content[0]` sin revisar
antes `stop_reason`.** Si la cadena entera declina, `content` viene vacío.

---

## Estructura

```
demos/
  app.py                     App multipágina (Streamlit)
  paginas/                   Las dos demos
  shared/
    motor.py                 Conciliación determinista. Sin IA, sin red.
    analisis.py              Prompt + JSON Schema de las excepciones
    agente.py                Herramientas, controles y bucle de tool use
    config.py                Modelo, esfuerzo, precios, rutas, paleta
  data/
    generar_datos.py         Genera todo, con semilla fija
    politicas_contables.md   Manual que consulta el agente
    respaldos/               Corridas reales grabadas
  record_run.py              Graba los respaldos
  pruebas_de_humo.py         Ejecuta ambas páginas sin gastar tokens
docs/                        Landing (GitHub Pages) + calculadora de ROI
notebooks/                   Cuaderno de Colab (+ copia con salidas)
```

`record_run.py` importa el **mismo** prompt, esquema y herramientas que la app:
no existen dos copias que mantener sincronizadas.

El **por qué** de cada decisión —las mediciones, lo que se descartó y los cuatro
hallazgos que cambiaron el código— está en [`BITACORA.md`](BITACORA.md).

---

## Regenerar todo

```bash
python demos/data/generar_datos.py   # datos (determinista)
python demos/record_run.py           # respaldos (requiere key e internet)
python demos/pruebas_de_humo.py      # verificación
```

Si cambias datos, prompts o herramientas: **regraba los respaldos**, o el modo
respaldo dejará de corresponder a lo que la demo hace en vivo.

Modelo y esfuerzo se cambian en un solo lugar: `demos/shared/config.py`.
El esfuerzo está en `low` — medido sobre este caso, `medium` tarda 60% más
(61 s contra 38 s) sin diferencia de calidad observable en los 10 casos
sembrados. Frente a un público, esos 23 segundos son la diferencia.

---

## Despliegue

**GitHub Pages** — Settings → Pages → Deploy from a branch → `main` / `/docs`.
Después edita el bloque `const URLS` al inicio de `docs/index.html` con las URLs
reales.

**Streamlit Community Cloud** — [share.streamlit.io](https://share.streamlit.io)
→ New app → este repo → main file `demos/app.py`. En *Advanced settings →
Secrets*:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

La key **nunca** va al repo: es público porque Pages sirve `docs/`.

---

## Antes del evento

**24 horas antes**
- [ ] Abrir la app en Streamlit Cloud (duerme sin tráfico; el primer arranque tarda ~1 min).
- [ ] `python demos/pruebas_de_humo.py`.
- [ ] Verificar saldo y límites de la key en `console.anthropic.com`.

**1 hora antes**
- [ ] Correr ambas demos en **modo real**, de punta a punta.
- [ ] Probar el **modo respaldo** con el WiFi apagado.
- [ ] Abrir el cuaderno en Colab con la sesión de Google iniciada.
- [ ] Dejar corriendo `streamlit run demos/app.py` en local como plan C.

---

Los datos son sintéticos. Ninguna cifra corresponde a una empresa real.
Contacto: [benjamin@analiticaboutique.com.mx](mailto:benjamin@analiticaboutique.com.mx)
