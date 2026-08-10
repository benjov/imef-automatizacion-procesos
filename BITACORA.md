# Bitácora de construcción

Registro de cómo se armó este repositorio: qué se decidió, con qué medición y
qué se descartó. El `README.md` explica **qué hace** el proyecto; este documento
explica **por qué está hecho así**.

Se escribe porque la mitad del valor de una demo técnica está en las decisiones
que no se ven, y porque dentro de seis meses nadie —incluido quien lo escribió—
va a recordar por qué el umbral de materialidad viene en cero.

---

## Objetivo

Sostener con código la tesis de la charla: **el 90% de un proceso financiero lo
resuelve una regla; el 10% que la rompe es donde la IA vale.** No bastaba
afirmarlo: había que poder medirlo en vivo, delante de un comité técnico, con el
cronómetro y el costo a la vista.

De ahí las tres restricciones que gobernaron todo lo demás:

1. **Medible.** Cada cifra de la presentación tenía que salir de una corrida
   real y reproducible, no de un benchmark de tercero.
2. **Sobrevivible.** Una sesión virtual puede quedarse sin ancho de banda justo
   en la demo. Todo tiene que poder correr sin red.
3. **Auditable.** El público firma conciliaciones. Si el sistema no puede
   explicar de dónde salió una propuesta, no sirve de ejemplo.

---

## Cronología

### 8 de agosto de 2026 — construcción

Se armó en este orden, que resultó ser el correcto: **datos → motor → modelo →
agente → interfaz**. Construir el motor antes de tocar la API obligó a definir
qué era "excepción" con precisión aritmética, y eso fue lo que hizo posible que
el prompt fuera corto.

| Paso | Resultado |
|---|---|
| Generador de datos con semilla fija | 226 movimientos y 10 casos sembrados |
| Motor determinista | 212/226 (93.8%) en 0.3 ms |
| Clasificación de excepciones con salida estructurada | 12 partidas desde 14 excepciones |
| Agente con 4 herramientas | 7–8 llamadas por corrida |
| Interfaz y modo respaldo | Dos páginas, corridas reales grabadas |
| Cuaderno de Colab | Adaptador escrito por el modelo, verificado contra el original |

### 9 de agosto de 2026 — ajustes

Se retiró el hueco para un anuncio comercial en la presentación y se documentó
la fuga de ruta absoluta que el cuaderno de respaldo guardaba en sus salidas.

Se agregaron los **cuatro formatos de exportación bancaria**
(`demos/data/formatos_reales/`). La demo arrancaba con un CSV limpio, que es
justo lo que nadie recibe: faltaba mostrar el problema antes de resolverlo. No
alimentan al motor —son narrativa— pero son el argumento visual de por qué la
primera capa determinista existe.

Los nombres de institución quedaron genéricos por una razón de credibilidad, no
de estilo: los patrones de formato son reales y reconocibles, pero afirmar "así
exporta tal banco" es una afirmación verificable que basta con que falle una vez,
delante de alguien que usa ese banco a diario, para costar la confianza del resto
de la sesión.

---

## Decisiones, con su medición

### El motor va primero y la IA después

No es sólo arquitectura, es la tesis hecha demostración: primero se ve el acto
barato (93.8% gratis, en menos de un milisegundo) y sólo entonces el caro.

Tiene además una ventaja escénica que se descubrió ensayando: el análisis del
modelo tarda ~38 segundos, y si la tabla de excepciones ya está en pantalla, esa
espera se llena con contenido en vez de con silencio.

### Esfuerzo `low`, no `medium`

Medido sobre las 14 excepciones reales:

| Esfuerzo | Tiempo | Costo | Calidad |
|---|---|---|---|
| `low` | ~38 s | ~$2.12 MXN | Los 10 casos sembrados, correctos |
| `medium` | ~61 s | ~$2.83 MXN | Idéntica |

`medium` tardó 60% más sin ganar nada observable. Frente a público, 23 segundos
son la diferencia entre una demo ágil y una incómoda. La constante vive en
`demos/shared/config.py` con la medición anotada al lado.

### Todo el dinero en centavos enteros

Comparar flotantes es exactamente cómo aparecen las diferencias de un peso que
nadie puede explicar. El motor convierte a entero al leer y nunca vuelve a
flotante hasta presentar.

### El umbral de materialidad viene en CERO

El motor sabe conciliar por tolerancia (nivel 4), pero llega apagado. Cada peso
conciliado por tolerancia es un peso que ningún humano revisó: encenderlo es una
decisión de control interno, no un ajuste técnico.

Se dejó como control deslizante en la interfaz precisamente para poder mostrar
ese intercambio en vivo — subirlo mejora el porcentaje del reporte y empeora el
control.

### Sin gráficas

Una conciliación se lee en tablas y cifras. Además: menos superficie de falla en
vivo y mejor legibilidad cuando la videollamada comprime la imagen. Se quitó
`plotly` de las dependencias.

### El prompt y el esquema viven en un solo lugar

`shared/analisis.py` los define y tanto la interfaz como `record_run.py` los
importan. En el proyecto anterior había dos copias que se mantenían
sincronizadas a mano, y era cuestión de tiempo que divergieran: el modo respaldo
habría dejado de corresponder a lo que la demo hace en vivo.

### El control de autorización, en código

`registrar_asiento_borrador` verifica que el asiento cuadre, aplica los umbrales
de la política 7.2 y se niega a regularizar un movimiento no reconocido — pase
lo que pase por el prompt. Un guardarraíl que depende de que el modelo se porte
bien no es un control interno.

---

## Hallazgos

Cinco cosas que no estaban previstas y que cambiaron el código o la forma de
operarlo. Las tres primeras acabaron siendo contenido de la charla.

### 1. El clasificador rechaza peticiones inocuas, de forma intermitente

Al preparar el cuaderno de Colab, pedir *"escribe una función que lea este CSV
de estado de cuenta"* devolvió `stop_reason: "refusal"` con categoría `cyber`.
Se probaron dos redacciones alternativas: ambas rechazadas. Se reintentó más
tarde con una variante mínima: pasó.

**Es intermitente, no determinista.** Y afecta justo lo que hacen estas demos:
datos transaccionales y generación de código.

Respuesta: `fallbacks="default"` en las tres rutas, que reencamina la petición a
otro modelo dentro de la misma llamada. No cuesta nada cuando no se dispara.
**Se activó de verdad** en la corrida grabada del cuaderno — la evidencia está
en la salida de `notebooks/adapta_el_conciliador_RESPALDO.ipynb`.

Regla que quedó en todo el repo: **nunca leer `content[0]` sin revisar antes
`stop_reason`.** Si la cadena entera declina, `content` viene vacío.

### 2. Una herramienta mal diseñada produce un modelo que "razona mal"

La primera versión de `consultar_cartera` sólo devolvía la coincidencia exacta.
El agente buscaba el depósito de $93,600, veía **una sola** factura, concluía
—correctamente— que no había ambigüedad, y lo aplicaba.

Pero existe otra factura por $93,615, y la política 7.6 prohíbe aplicar cuando
hay candidatas parecidas. El modelo no estaba fallando: **razonaba bien sobre
información incompleta.** La herramienta le escondía justo lo que la política le
pedía detectar.

Ahora la herramienta amplía la banda de búsqueda por su cuenta, sin depender de
que quien llama pida la tolerancia correcta. El comentario en el código conserva
la historia porque es la lección más transferible del proyecto: **diseñar la
herramienta es diseñar el control.**

### 3. `max_tokens` corto puede devolver cero texto

Con el razonamiento activo por defecto, `max_tokens` acota la respuesta
**completa**, razonamiento incluido. Con un límite de 2,000 el modelo lo gastó
entero pensando y devolvió cero bloques de texto: la llamada "funcionó" y no
trajo nada.

Se subió el margen y se agregó comprobación explícita en lugar de indexar a
ciegas.

### 4. Streamlit Cloud no reinicia el proceso al hacer pull

Al publicar los formatos de exportación, la app desplegada empezó a fallar con:

```
ImportError: cannot import name 'DIR_FORMATOS' from 'shared.config'
```

El código del repo estaba **completo y correcto** —`DIR_FORMATOS` existía en
`config.py` y el import funcionaba en local—, lo que hizo perder tiempo buscando
un error que no estaba ahí.

La causa está en la bitácora de despliegue: `Uvicorn server started` aparece una
sola vez, al arranque. Cuando llega un push, Community Cloud hace `git pull` y
vuelve a **ejecutar el script**, pero no levanta un proceso nuevo. Las páginas se
re-ejecutan con el código nuevo; los módulos de `shared/` siguen en `sys.modules`
con la versión vieja. Resultado: una página nueva importando de un módulo viejo.

Solución: *Reboot app*. Y la regla que quedó en el `README.md`: **todo push que
toque `demos/shared/` exige reinicio, y el día del evento no se hace push** — un
`ImportError` mata la página entera antes de dibujar el panel lateral, así que
ni siquiera el modo respaldo lo salva.

### 5. Menos herramientas por vuelta, menos latencia

La primera versión de `consultar_politica` recibía **una** sección por llamada,
y el agente pedía las siete de una en una: 14–15 llamadas y ~55 s por corrida.
Cambiada a recibir un arreglo de secciones, bajó a 7–8 llamadas y ~44 s, con el
mismo resultado.

---

## Lo que se probó y se descartó

| Se probó | Por qué se descartó |
|---|---|
| Esfuerzo `medium` | 60% más lento, misma calidad |
| Gráficas con `plotly` | No aportan a una conciliación; más riesgo en vivo |
| Reformular el prompt para esquivar el rechazo | Dos variantes, ambas rechazadas: no era la redacción |
| `use_container_width` | Deprecado; sustituido por `width="stretch"` |
| Ventana de conciliación amplia para el traspaso de corte | La ventana de 3 días lo conciliaba y se perdía el caso; se dejó fuera de periodo, que es como ocurre de verdad |

---

## Cómo se verificó

Nada de esto se dio por bueno sin correrlo:

```bash
python demos/data/generar_datos.py    # determinista: mismo hash siempre
python demos/pruebas_de_humo.py       # ejecuta ambas páginas, sin gastar tokens
python demos/record_run.py            # corridas reales contra la API
```

Las pruebas de humo usan `streamlit.testing`: **ejecutan las páginas de verdad**
en modo respaldo, no sólo comprueban que el módulo importe. Una demo que se cae
en vivo por un `KeyError` no la salva ningún respaldo.

El cuaderno de respaldo se ejecutó de punta a punta y su última celda compara el
resultado del archivo traducido contra el original: **212 conciliados y 14
excepciones en ambos.** Si la traducción hubiera perdido un movimiento, ahí se
habría visto.

---

## Lo que falta

- Desplegar: GitHub Pages (`main` / `/docs`) y Streamlit Community Cloud, y
  pegar las URLs reales en el bloque `const URLS` de `docs/index.html`.
- Correr ambas demos en **modo real** de punta a punta el día previo, y el modo
  respaldo con el WiFi apagado.

El checklist completo previo al evento está al final del `README.md`.

---

## Concurrencia: qué pasa si entran cien personas a la vez

El enlace se reparte por QR a una sesión entera, así que hay que diseñar para
ese momento. Los dos riesgos no son del mismo tamaño.

**El serio no es de recursos, es de la API.** Todas las visitas comparten una
sola key. Si cada asistente pudiera lanzar corridas en vivo, cada clic cobraría
a esa key y decenas de llamadas simultáneas chocarían contra los límites de tasa
— justo mientras el ponente demuestra. El daño no es la factura: es que la demo
se cae sola, en el peor momento.

Mitigación: **la app arranca en modo respaldo** para cualquier visitante
(`shared/respaldo.py`, `modo_vivo_autorizado`). Reproduce corridas reales
grabadas, se ve idéntico y cuesta cero. El modo en vivo se abre sólo con
`CLAVE_MODO_VIVO` en la URL.

Tiene un efecto secundario feliz: el modo respaldo, que se construyó como red
contra la caída de red, resultó ser también la respuesta a la concurrencia.

**El de recursos se atiende con caché.** Community Cloud da 1 GB compartido por
app. El cruce, las señales y la lectura de archivos están en `@st.cache_data`,
que se comparte entre sesiones: el trabajo se hace una vez, no una por
visitante.

**Y la recomendación operativa que vale más que las dos anteriores:** el ponente
demuestra desde local. Así queda aislado del tráfico de su propia audiencia.
