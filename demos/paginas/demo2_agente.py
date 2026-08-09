"""Demo 2 — El agente de cierre: se le da un objetivo, no un procedimiento.

En la Demo 1 el flujo lo decidimos nosotros. Aquí sólo se entrega la meta y un
cinturón de herramientas, y el modelo arma el plan. Lo que hay que hacer notar
en voz alta mientras corre:

  · La primera herramienta que llama ejecuta el MOTOR de la Demo 1. El agente
    no concilia: orquesta código determinista y auditable.
  · `registrar_asiento_borrador` valida los umbrales de la política 7.2 dentro
    del código. Si el modelo propone algo que la política prohíbe, la
    herramienta lo rechaza — el control no depende de la buena conducta del
    modelo.
  · No se escribe nada en ningún sistema. El agente propone; firmar es humano.
"""

import json
import time

import pandas as pd
import streamlit as st

from shared import agente, estilos, respaldo, texto
from shared.cliente import obtener_cliente
from shared.config import BANCO, CUENTA, EMPRESA, PERIODO, costo_mxn

estilos.aplicar()
modo_respaldo = respaldo.toggle_respaldo()

st.title("Agente de cierre")
st.caption(f"{EMPRESA} · {BANCO} {CUENTA} · {PERIODO}")

ICONO = {
    "ejecutar_conciliacion": "⚙️",
    "consultar_cartera": "📇",
    "consultar_politica": "📕",
    "registrar_asiento_borrador": "🔒",
}
NOMBRE = {
    "ejecutar_conciliacion": "Ejecutar el motor de conciliación",
    "consultar_cartera": "Consultar la cartera de clientes",
    "consultar_politica": "Leer el manual de políticas",
    "registrar_asiento_borrador": "Encolar asiento en borrador",
}

# --------------------------------------------------------------------------
st.subheader("La instrucción")
etiqueta = st.radio("¿Qué le pides al agente?", list(agente.INSTRUCCIONES),
                    horizontal=True, label_visibility="collapsed")
instruccion = agente.INSTRUCCIONES[etiqueta]
st.info(f"«{instruccion}»", icon="💬")

with st.expander("Las cuatro herramientas que tiene disponibles"):
    for h in agente.HERRAMIENTAS:
        st.markdown(f"**{ICONO.get(h['name'], '🔧')} `{h['name']}`** — "
                    f"{h['description']}")
    st.caption(
        "El modelo nunca ve los archivos: ve descripciones de herramientas y "
        "decide cuáles llamar, con qué argumentos y en qué orden. El diseño de "
        "este cinturón es, en la práctica, el diseño del control interno."
    )


# --------------------------------------------------------------------------
def pintar_paso(ev: dict, contenedor) -> None:
    if ev["tipo"] == "texto":
        with contenedor:
            texto.markdown(ev["texto"])
        return

    nombre = ev["nombre"]
    res = ev["resultado"]
    titulo = f"{ICONO.get(nombre, '🔧')}  {NOMBRE.get(nombre, nombre)}"

    # El control de autorización se pinta aparte: es el momento importante.
    if nombre == "registrar_asiento_borrador":
        estatus = res.get("estatus", "")
        with contenedor:
            if estatus == "RECHAZADO":
                st.error(f"**{titulo} → RECHAZADO POR CONTROL INTERNO**\n\n"
                         f"{res.get('motivo', '')}", icon="🛑")
            else:
                st.success(
                    f"**{titulo}**\n\n{ev['args'].get('concepto', '')}\n\n"
                    f"${res.get('importe', 0):,.2f} — pendiente de autorización de "
                    f"**{res.get('autoriza', '—')}**", icon="🔒")
            if ev["args"].get("renglones"):
                st.dataframe(
                    pd.DataFrame(ev["args"]["renglones"]).rename(
                        columns={"cuenta": "Cuenta", "cargo": "Cargo", "abono": "Abono"}),
                    hide_index=True, width="stretch",
                    column_config={
                        "Cargo": st.column_config.NumberColumn(format="$ %.2f"),
                        "Abono": st.column_config.NumberColumn(format="$ %.2f"),
                    })
        return

    with contenedor:
        with st.expander(titulo, expanded=False):
            st.caption("Argumentos que el modelo eligió")
            st.code(json.dumps(ev["args"], ensure_ascii=False, indent=2), language="json")
            st.caption("Lo que devolvió la herramienta")
            if nombre == "ejecutar_conciliacion":
                r = res
                a, b, c = st.columns(3)
                a.metric("Conciliado", f"{r['tasa_automatica']:.1%}")
                b.metric("Tiempo", f"{r['milisegundos']} ms")
                c.metric("Excepciones", len(r["partidas_sin_conciliar"]))
                st.dataframe(
                    pd.DataFrame([{"ID": p["id"], "Fecha": p["fecha"],
                                   "Importe": p["monto"], "Concepto": p["descripcion"]}
                                  for p in r["partidas_sin_conciliar"]]),
                    hide_index=True, width="stretch",
                    column_config={"Importe": st.column_config.NumberColumn(format="$ %.2f")})
            elif nombre == "consultar_cartera":
                if res.get("advertencia"):
                    st.warning(res["advertencia"], icon="⚠️")
                st.dataframe(pd.DataFrame(res.get("candidatas", [])),
                             hide_index=True, width="stretch")
            elif nombre == "consultar_politica":
                for clave, cuerpo in res.get("secciones", {}).items():
                    st.markdown(f"*Sección {clave}*")
                    st.text(cuerpo[:700])
            else:
                st.code(json.dumps(res, ensure_ascii=False, indent=2)[:1500],
                        language="json")


# --------------------------------------------------------------------------
if st.button("▶  Poner a trabajar al agente", type="primary", width="stretch"):
    st.session_state.pop("demo2", None)
    bitacora = st.container()

    if modo_respaldo:
        grabado = respaldo.cargar("demo2")["corridas"].get(etiqueta)
        if not grabado:
            st.error(f"El respaldo no tiene grabada la instrucción «{etiqueta}».")
            st.stop()
        with st.status("Reproduciendo corrida grabada…", expanded=True) as s:
            for ev in grabado["pasos"]:
                pintar_paso(ev, bitacora)
                time.sleep(0.5)
            s.update(label="Corrida reproducida", state="complete")
        st.session_state["demo2"] = grabado
    else:
        with st.status("El agente está trabajando…", expanded=True) as s:
            try:
                salida = agente.correr(
                    obtener_cliente(), instruccion,
                    al_paso=lambda ev: pintar_paso(ev, bitacora),
                )
            except Exception as e:                        # noqa: BLE001
                st.error(f"Falló la llamada a la API: {e}\n\n"
                         "Activa el **Modo respaldo** en el panel lateral.")
                st.stop()
            s.update(label="El agente terminó", state="complete")
        st.session_state["demo2"] = salida

# --------------------------------------------------------------------------
salida = st.session_state.get("demo2")
if salida:
    llamadas = [p for p in salida["pasos"] if p["tipo"] == "herramienta"]
    encolados = [p for p in llamadas
                 if p["nombre"] == "registrar_asiento_borrador"
                 and p["resultado"].get("estatus") == "EN BORRADOR"]
    rechazados = [p for p in llamadas
                  if p["nombre"] == "registrar_asiento_borrador"
                  and p["resultado"].get("estatus") == "RECHAZADO"]

    st.markdown("---")
    st.subheader("Resultado de la corrida")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Llamadas a herramientas", len(llamadas))
    k2.metric("Asientos en borrador", len(encolados),
              f"{len(rechazados)} rechazados por control" if rechazados else None,
              delta_color="off")
    k3.metric("Costo de la corrida",
              f"${costo_mxn(salida['tokens_entrada'], salida['tokens_salida']):.2f} MXN",
              f"{salida['tokens_entrada']:,} + {salida['tokens_salida']:,} tokens")
    k4.metric("Tiempo", f"{salida.get('segundos', 0):.0f} s"
              if salida.get("segundos") else "—")

    if encolados:
        st.markdown("##### Pendientes de autorización")
        st.dataframe(
            pd.DataFrame([{
                "Concepto": p["args"]["concepto"],
                "Importe": p["resultado"].get("importe", 0),
                "Autoriza": p["resultado"].get("autoriza", ""),
                "Estatus": "Borrador — sin afectar contabilidad",
            } for p in encolados]),
            hide_index=True, width="stretch",
            column_config={"Importe": st.column_config.NumberColumn(format="$ %.2f")})
        st.caption(
            "Ninguno de estos asientos tocó la contabilidad. El agente los dejó "
            "en cola; la firma que los convierte en realidad es de una persona "
            "facultada, y queda en bitácora."
        )

    st.markdown("##### Acta de conciliación")
    texto.markdown(salida["acta"])
    st.download_button(
        "⬇  Descargar el acta (Markdown)",
        salida["acta"].encode("utf-8"),
        f"acta_conciliacion_{PERIODO.lower().replace(' ', '_')}.md",
        "text/markdown", width="stretch",
    )
