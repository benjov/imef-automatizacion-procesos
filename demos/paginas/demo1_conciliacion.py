"""Demo 1 — Conciliación bancaria en dos actos.

El punto de la demo no es que la IA concilie. Es que NO concilia: el motor
determinista resuelve el 94% en menos de un milisegundo y por cero pesos, y
sólo el residuo llega al modelo. Primero se ve el acto barato, y ya con las
excepciones en pantalla se lanza el caro.

Ese orden es deliberado también por una razón escénica: mientras el modelo
piensa sus ~40 segundos, el público ya tiene enfrente la lista de partidas y
el ponente tiene de qué hablar.
"""

import json

import pandas as pd
import streamlit as st

from shared import analisis, estilos, respaldo, texto
from shared.cliente import obtener_cliente
from shared.config import (ARCHIVO_BANCO, ARCHIVO_CARTERA, ARCHIVO_LIBROS,
                           ARCHIVO_POLITICAS, BANCO, CUENTA, DIR_FORMATOS,
                           EMPRESA, FORMATOS_REALES, ICONO_CONFIANZA, PERIODO,
                           costo_mxn)
from shared.motor import cargar_banco, cargar_libros, conciliar, pistas

estilos.aplicar()
modo_respaldo = respaldo.toggle_respaldo()

st.title("Conciliación bancaria")
st.caption(f"{EMPRESA} · {BANCO} {CUENTA} · {PERIODO}")


# --------------------------------------------------------------------------
@st.cache_data
def _datos():
    banco = cargar_banco(ARCHIVO_BANCO)
    libros = cargar_libros(ARCHIVO_LIBROS)
    return banco, libros


banco, libros = _datos()

# ============================== PASO 1 =====================================
st.subheader("1 · Los dos archivos")
c1, c2 = st.columns(2)
c1.metric("Estado de cuenta", f"{len(banco)} movimientos")
c2.metric("Auxiliar contable", f"{len(libros)} partidas")

with st.expander("Ver los archivos tal como salen de los sistemas"):
    t1, t2 = st.tabs(["Estado de cuenta (banco)", "Auxiliar contable (ERP)"])
    t1.dataframe(pd.read_csv(ARCHIVO_BANCO), height=260, width="stretch")
    t2.dataframe(pd.read_csv(ARCHIVO_LIBROS), height=260, width="stretch")
    st.caption(
        "Dos sistemas que no se hablan: el banco identifica con folio SPEI, la "
        "contabilidad con número de póliza. No hay una llave común — por eso "
        "esto se concilia por importe y fecha, y por eso duele."
    )

with st.expander("⚠️  Y así llegan en realidad: cuatro bancos, cuatro formatos"):
    st.markdown(
        "Los dos archivos de arriba ya vienen limpios. **Nadie recibe eso.** "
        "Estos son los mismos movimientos tal como los entrega cada "
        "institución — y una empresa con cuentas en cuatro bancos recibe los "
        "cuatro, cada mes."
    )
    for etiqueta, tab in zip([f[0] for f in FORMATOS_REALES],
                             st.tabs([f[0] for f in FORMATOS_REALES])):
        _, archivo, lenguaje, dolor = next(f for f in FORMATOS_REALES
                                           if f[0] == etiqueta)
        with tab:
            ruta = DIR_FORMATOS / archivo
            if ruta.exists():
                crudo = ruta.read_text(encoding="utf-8")
                st.code("\n".join(crudo.splitlines()[:12]), language=lenguaje)
                texto.markdown(f"**Lo que duele:** {dolor}")
            else:
                st.warning(f"Falta `{archivo}`. Corre "
                           "`python demos/data/generar_datos.py`.")

    st.info(
        "Ninguno trae una llave que cruce contra la contabilidad, y los cuatro "
        "cambian de formato sin avisar. **Normalizar esto es la primera capa "
        "determinista** — el trabajo que nadie presume en una presentación de "
        "IA y sin el cual no hay nada que conciliar.",
        icon="🔧",
    )
    st.caption(
        "Formatos representativos, no reproducciones de ninguna institución. "
        "Los nombres de banco son genéricos; los patrones sí son reales."
    )

# ============================== PASO 2 =====================================
st.subheader("2 · El motor determinista")
st.markdown(
    '<div class="motor"><b>Sin IA.</b> Aritmética exacta en cuatro niveles: '
    'importe y fecha exactos → importe exacto con desfase de hasta 3 días '
    'hábiles → agrupación uno-a-muchos (un depósito que liquida varias '
    'facturas) → diferencias bajo el umbral de materialidad.</div>',
    unsafe_allow_html=True,
)

tolerancia = st.slider(
    "Umbral de materialidad (política 7.1)", 0, 500, 0, step=50,
    format="$%d",
    help="Diferencia máxima para dar por cuadrada una pareja. Súbelo y el "
         "porcentaje automático mejora... a costa de partidas que ya nadie mira.",
)

res = conciliar(banco, libros, tolerancia_centavos=tolerancia * 100)
todos = banco + libros

m1, m2, m3, m4 = st.columns(4)
m1.metric("Conciliado automático", f"{res.tasa:.1%}",
          f"{res.conciliados} de {res.total_movimientos}")
m2.metric("Tiempo de proceso", f"{res.segundos * 1000:.1f} ms")
m3.metric("Costo de este paso", "$0.00", "cero tokens")
m4.metric("Partidas en excepción", f"{len(res.excepciones)}",
          f"${res.monto_en_excepcion:,.0f}", delta_color="off")

st.progress(res.tasa)

with st.expander(f"Cómo se conciliaron los {res.conciliados} movimientos"):
    st.dataframe(
        pd.DataFrame([{"Nivel de cruce": k, "Movimientos": v}
                      for k, v in res.por_nivel().items()]),
        hide_index=True, width="stretch",
    )
    st.caption(
        "El nivel 3 es el que sorprende: un solo depósito de $487,300 que "
        "liquida tres facturas distintas. Encontrar esa combinación es "
        "búsqueda combinatoria — exactamente el trabajo que no debe hacer un "
        "modelo de lenguaje."
    )

if tolerancia > 0:
    st.warning(
        f"Con un umbral de ${tolerancia} el motor cuadra "
        f"{res.tasa:.1%} en vez del 93.8% estricto. Cada peso conciliado por "
        "tolerancia es un peso que ningún humano revisó: subir este número es "
        "una decisión de control interno, no un ajuste técnico.",
        icon="⚖️",
    )

# ============================== PASO 3 =====================================
st.subheader(f"3 · Las {len(res.excepciones)} partidas que rompen la regla")

df_exc = pd.DataFrame([{
    "ID": m.id,
    "Sistema": "Banco" if m.origen == "banco" else "Libros",
    "Fecha": m.fecha.strftime("%d/%m/%Y"),
    "Importe": m.monto,
    "Concepto": m.descripcion,
    "Señales del motor": " ".join(pistas(m, todos)) or "—",
} for m in res.excepciones])
st.dataframe(
    df_exc, hide_index=True, width="stretch",
    column_config={"Importe": st.column_config.NumberColumn(format="$ %.2f")},
)
st.caption(
    "Aquí es donde se va el tiempo del área: 6% de los movimientos, 100% del "
    "dolor. Cada una necesita leer un concepto en lenguaje humano, cruzarlo "
    "con la política contable y decidir. Eso sí es trabajo para el modelo."
)

# ============================== PASO 4 =====================================
st.subheader("4 · El modelo resuelve el residuo")

if st.button("▶  Analizar las partidas en conciliación", type="primary",
             width="stretch"):
    if modo_respaldo:
        with st.status("Reproduciendo corrida grabada…", expanded=False):
            st.session_state["demo1"] = respaldo.cargar("demo1")
    else:
        marcador = st.empty()
        estado = {"tok": 0, "latidos": 0}

        def al_recibir(tokens):
            if tokens:
                estado["tok"] = tokens
            else:
                estado["latidos"] += 1
            aprox = estado["tok"] or estado["latidos"] * 4
            marcador.metric(
                "Generando…", f"{aprox:,} tokens",
                f"≈ ${costo_mxn(5200, aprox):.2f} MXN acumulados",
                delta_color="off",
            )

        with st.spinner("El modelo está leyendo las partidas y el manual de políticas…"):
            try:
                st.session_state["demo1"] = analisis.analizar(
                    obtener_cliente(), res.excepciones, todos,
                    ARCHIVO_CARTERA.read_text(encoding="utf-8"),
                    ARCHIVO_POLITICAS.read_text(encoding="utf-8"),
                    al_recibir=al_recibir,
                )
            except Exception as e:                       # noqa: BLE001
                marcador.empty()
                st.error(f"Falló la llamada a la API: {e}\n\n"
                         "Activa el **Modo respaldo** en el panel lateral y vuelve a intentar.")
                st.stop()
        marcador.empty()

salida = st.session_state.get("demo1")

if salida:
    partidas = salida["partidas"]
    n_humano = sum(1 for p in partidas if p["requiere_humano"])
    costo = costo_mxn(salida["tokens_entrada"], salida["tokens_salida"])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Partidas resueltas", len(partidas),
              f"agrupadas desde {len(res.excepciones)}")
    k2.metric("Requieren decisión humana", n_humano)
    k3.metric("Costo de la corrida", f"${costo:.2f} MXN",
              f"{salida['tokens_entrada']:,} + {salida['tokens_salida']:,} tokens")
    k4.metric("Tiempo", f"{salida.get('segundos', 0):.0f} s"
              if salida.get("segundos") else "—")

    st.markdown("---")

    for p in partidas:
        clase = p["confianza"]
        icono = ICONO_CONFIANZA.get(clase, "⚪")
        monto = sum(abs(m.monto) for m in res.excepciones if m.id in p["ids"])
        etiquetas = f'<span class="etiqueta">{p["accion"].replace("_", " ")}</span>'
        if p["requiere_humano"]:
            etiquetas += '<span class="etiqueta humano">requiere firma</span>'

        st.markdown(
            f'<div class="partida {clase}">'
            f'<span class="monto">{texto.escapar(texto.pesos(monto))}</span>'
            f'<div class="titulo">{icono} {p["titulo"]}</div>'
            f'<div class="meta">{" · ".join(p["ids"])} · '
            f'{p["categoria"].replace("_", " ")}'
            + (f' · política {p["politica"]}' if p["politica"] else "")
            + f' · confianza {p["confianza"]}</div>'
            f'{etiquetas}</div>',
            unsafe_allow_html=True,
        )
        texto.markdown(p["explicacion"])

        if p["asiento"]:
            df_a = pd.DataFrame(p["asiento"]).rename(
                columns={"cuenta": "Cuenta", "cargo": "Cargo", "abono": "Abono"})
            cuadra = abs(df_a["Cargo"].sum() - df_a["Abono"].sum()) < 0.005
            st.dataframe(
                df_a, hide_index=True, width="stretch",
                column_config={
                    "Cargo": st.column_config.NumberColumn(format="$ %.2f"),
                    "Abono": st.column_config.NumberColumn(format="$ %.2f"),
                },
            )
            if not cuadra:
                st.error("El asiento propuesto no cuadra. Rechazar y devolver.")
        st.markdown("")

    # ---------------------------------------------------------------- salidas
    st.markdown("---")
    st.subheader("5 · Lo que se lleva el contralor")
    st.caption(
        "La propuesta se descarga como papel de trabajo. Nada se registró en "
        "ningún sistema: la autorización sigue siendo un acto humano, y queda "
        "en bitácora quién la propuso, quién la autorizó y cuándo (política 7.7)."
    )

    filas = [{
        "IDs": " ".join(p["ids"]), "Partida": p["titulo"],
        "Categoría": p["categoria"], "Acción": p["accion"],
        "Confianza": p["confianza"], "Requiere humano": p["requiere_humano"],
        "Política": p["politica"], "Explicación": p["explicacion"],
    } for p in partidas]

    d1, d2 = st.columns(2)
    d1.download_button(
        "⬇  Papel de trabajo (CSV)",
        pd.DataFrame(filas).to_csv(index=False).encode("utf-8"),
        "partidas_en_conciliacion.csv", "text/csv", width="stretch",
    )
    d2.download_button(
        "⬇  Propuesta completa (JSON)",
        json.dumps(salida, ensure_ascii=False, indent=2).encode("utf-8"),
        "conciliacion_propuesta.json", "application/json", width="stretch",
    )

    with st.expander("¿Por qué JSON y no un texto?"):
        st.markdown(
            "Al modelo no se le pidió que *escribiera* la respuesta: se le pasó "
            "un **esquema** y la API garantiza que lo que devuelve cumple ese "
            "esquema. Categoría y acción son listas cerradas, el asiento es un "
            "arreglo de renglones con cuenta, cargo y abono.\n\n"
            "Eso cambia la naturaleza del entregable. Un párrafo hay que leerlo "
            "y creerle. Un objeto validado se compara entre periodos, se suma, "
            "se audita y se conecta al ERP sin que nadie interprete nada."
        )
        st.code(json.dumps(analisis.ESQUEMA["properties"]["partidas"]["items"]
                           ["properties"]["accion"], ensure_ascii=False, indent=2),
                language="json")
