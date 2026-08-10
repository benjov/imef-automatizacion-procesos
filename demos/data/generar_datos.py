"""Genera los datasets sintéticos de la conciliación bancaria (deterministas).

Un solo script produce los dos lados de la conciliación a partir de la MISMA
lista de operaciones, de modo que los casos sembrados sean internamente
consistentes: si el auxiliar dice $45,890 y el banco dice $48,590, es porque
aquí sembramos una transposición de dígitos, no porque los archivos se
desincronizaron.

Correr:  python demos/data/generar_datos.py
Semilla fija -> mismo resultado siempre. Si cambias algo aquí, hay que
regrabar los respaldos (`python demos/record_run.py`).
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent

EMPRESA = "Industrias del Norte, S.A. de C.V."
BANCO = "BBVA México"
CUENTA = "0198 4471 92"
PERIODO = "Septiembre 2026"
SALDO_INICIAL = 4_182_650.00

SEMILLA = 20260813
random.seed(SEMILLA)

# --------------------------------------------------------------------------
# Catálogos: nombres reconocibles pero ficticios.
# --------------------------------------------------------------------------
CLIENTES = [
    "Grupo Ferretero del Bajío", "Constructora Peninsular", "Distribuidora Alfa Norte",
    "Comercializadora Sonora", "Aceros y Perfiles del Golfo", "Refacciones Industriales MTY",
    "Suministros Eléctricos Querétaro", "Grupo Logístico Altamira",
]
PROVEEDORES = [
    "Aceros Monclova", "Transportes Rápidos del Centro", "Energía Industrial SA",
    "Empaques y Cartón Bajío", "Servicios Técnicos Ramírez", "Papelería Corporativa MX",
    "Mantenimiento Industrial Torres", "Seguros Patrimoniales del Norte",
]

# Días hábiles de septiembre 2026 (1 = martes; 16 de sep es festivo en México).
FESTIVOS = {date(2026, 9, 16)}


def habiles(anio: int, mes: int) -> list[date]:
    dias, d = [], date(anio, mes, 1)
    while d.month == mes:
        if d.weekday() < 5 and d not in FESTIVOS:
            dias.append(d)
        d += timedelta(days=1)
    return dias


HABILES = habiles(2026, 9)


def habil_mas(d: date, n: int) -> date:
    """Suma n días hábiles a d (n puede ser negativo)."""
    if n == 0:
        return d
    paso = 1 if n > 0 else -1
    faltan, cur = abs(n), d
    while faltan:
        cur += timedelta(days=paso)
        if cur.weekday() < 5 and cur not in FESTIVOS:
            faltan -= 1
    return cur


# --------------------------------------------------------------------------
# Estructuras. `flujo` es el monto con signo desde la caja de la empresa:
#   +  entra dinero      -  sale dinero
# En el estado de cuenta eso se presenta como abono/cargo; en el auxiliar
# contable la cuenta de Bancos se carga cuando entra y se abona cuando sale
# (la inversión clásica que confunde a quien no es contador).
# --------------------------------------------------------------------------
banco: list[dict] = []   # filas del estado de cuenta
libros: list[dict] = []  # filas del auxiliar contable

_folio_poliza = [0]


def poliza(prefijo: str) -> str:
    _folio_poliza[0] += 1
    return f"{prefijo}-{_folio_poliza[0]:04d}"


def mov_banco(f: date, referencia: str, descripcion: str, flujo: float) -> None:
    banco.append({"fecha": f, "referencia": referencia,
                  "descripcion": descripcion, "flujo": round(flujo, 2)})


def mov_libros(f: date, pol: str, concepto: str, tercero: str, flujo: float) -> None:
    libros.append({"fecha": f, "poliza": pol, "concepto": concepto,
                   "tercero": tercero, "flujo": round(flujo, 2)})


def par(f_banco: date, f_libros: date, referencia: str, desc_banco: str,
        pol: str, concepto: str, tercero: str, flujo: float) -> None:
    """Operación que SÍ debe conciliar (el caso normal: ~90% del volumen)."""
    mov_banco(f_banco, referencia, desc_banco, flujo)
    mov_libros(f_libros, pol, concepto, tercero, flujo)


# --------------------------------------------------------------------------
# 1) Volumen normal del mes: cobranza, pagos, nómina, impuestos, servicios.
#    Una parte con desfase de 1–3 días hábiles entre banco y libros, que es
#    lo que obliga al motor a tener tolerancia de fechas.
# --------------------------------------------------------------------------
folio_fac = 2250
folio_spei = 700000

for f in HABILES:
    # Cobranza de clientes: 2–4 depósitos por día hábil.
    for _ in range(random.randint(2, 4)):
        folio_fac += 1
        folio_spei += random.randint(3, 19)
        cliente = random.choice(CLIENTES)
        monto = round(random.uniform(38_000, 320_000), 2)
        desfase = random.choices([0, 1, 2], weights=[78, 16, 6])[0]
        par(f, habil_mas(f, -desfase) if desfase else f,
            f"SPEI {folio_spei}",
            f"SPEI RECIBIDO {cliente[:22].upper()}",
            poliza("ING"), f"Cobro FAC-{folio_fac}", cliente, monto)

    # Pagos a proveedores: 1–3 por día hábil.
    for _ in range(random.randint(1, 3)):
        folio_spei += random.randint(3, 19)
        prov = random.choice(PROVEEDORES)
        monto = round(random.uniform(15_000, 210_000), 2)
        desfase = random.choices([0, 1, 2, 3], weights=[70, 18, 8, 4])[0]
        par(f, habil_mas(f, -desfase) if desfase else f,
            f"SPEI {folio_spei}",
            f"SPEI ENVIADO {prov[:22].upper()}",
            poliza("EGR"), f"Pago proveedor {prov}", prov, -monto)

# Nómina quincenal.
for f, importe in [(date(2026, 9, 15), 1_284_500.00), (date(2026, 9, 30), 1_291_240.00)]:
    par(f, f, "DISP NOMINA", "DISPERSION NOMINA ELECTRONICA",
        poliza("NOM"), f"Nómina {f.strftime('%d/%m/%Y')}", "Personal", -importe)

# Impuestos y cuotas (fechas de ley).
par(date(2026, 9, 17), date(2026, 9, 17), "PAGO SAT 0398412",
    "PAGO REFERENCIADO SAT", poliza("IMP"), "ISR e IVA agosto 2026", "SAT", -742_318.00)
par(date(2026, 9, 21), date(2026, 9, 21), "PAGO IMSS 55120",
    "PAGO REFERENCIADO IMSS", poliza("IMP"), "Cuotas IMSS agosto 2026", "IMSS", -268_940.00)

# Servicios recurrentes.
par(date(2026, 9, 8), date(2026, 9, 8), "DOM CFE 4471",
    "DOMICILIACION CFE", poliza("EGR"), "Energía eléctrica agosto", "CFE", -96_430.00)
par(date(2026, 9, 10), date(2026, 9, 10), "DOM TELMEX 8890",
    "DOMICILIACION TELMEX", poliza("EGR"), "Telefonía e internet agosto", "Telmex", -18_260.00)
par(date(2026, 9, 24), date(2026, 9, 24), "ARREND OFICINA",
    "TRANSFERENCIA ARRENDAMIENTO", poliza("EGR"), "Renta oficinas septiembre",
    "Inmobiliaria del Valle", -145_000.00)

# --------------------------------------------------------------------------
# 2) CASOS SEMBRADOS. Cada bloque es un tipo de partida que un contador
#    reconoce de inmediato. Están numerados igual que en el README.
# --------------------------------------------------------------------------

# CASO 1 — Depósito uno-a-muchos: un solo abono del banco liquida 3 facturas.
#          Lo resuelve el MOTOR (búsqueda de subconjuntos), no la IA.
mov_banco(date(2026, 9, 11), "SPEI 748219",
          "SPEI RECIBIDO GRUPO FERRETERO DEL BAJIO", 487_300.00)
for fol, imp in [("FAC-2291", 198_400.00), ("FAC-2295", 143_700.00), ("FAC-2301", 145_200.00)]:
    mov_libros(date(2026, 9, 11), poliza("ING"), f"Cobro {fol}",
               "Grupo Ferretero del Bajío", imp)

# CASO 2 — Comisiones bancarias e IVA: están en el banco, nunca en libros.
mov_banco(date(2026, 9, 30), "COM 0930", "COMISION MANEJO DE CUENTA", -1_450.00)
mov_banco(date(2026, 9, 30), "COM SPEI", "COMISION SPEI ENVIADOS (87 OPS)", -890.00)
mov_banco(date(2026, 9, 30), "IVA COM", "IVA COMISIONES", -374.40)

# CASO 3 — Cheque en tránsito: expedido y registrado, aún no cobrado.
mov_libros(date(2026, 9, 29), poliza("EGR"), "Cheque 10847 - anticipo obra",
           "Mantenimiento Industrial Torres", -67_800.00)

# CASO 4 — Cobro duplicado del banco: dos cargos idénticos el mismo día.
for _ in range(2):
    mov_banco(date(2026, 9, 18), "CARGO SERV", "CARGO SERVICIO ADMON EMPRESARIAL", -12_500.00)
mov_libros(date(2026, 9, 18), poliza("EGR"), "Servicio admón. empresarial", BANCO, -12_500.00)

# CASO 5 — Transposición de dígitos: libros 45,890 vs banco 48,590.
#          La diferencia (2,700) es divisible entre 9: firma clásica del error
#          de captura. Es el caso que hace levantar la ceja a un contador.
mov_banco(date(2026, 9, 22), "SPEI 751904", "SPEI ENVIADO ACEROS MONCLOVA", -48_590.00)
mov_libros(date(2026, 9, 22), poliza("EGR"), "Pago parcial OC-8841",
           "Aceros Monclova", -45_890.00)

# CASO 6 — Diferencia cambiaria en un pago en dólares (bajo materialidad).
mov_banco(date(2026, 9, 25), "SPEI INT 4402",
          "PAGO INTERNACIONAL USD 9,600.00", -184_320.50)
mov_libros(date(2026, 9, 25), poliza("EGR"), "Pago USD 9,600 OC-8902 (TC 19.1953)",
           "Global Bearings Corp", -184_275.00)

# CASO 7 — Depósito sin identificar: el banco no trae referencia utilizable.
#          El monto coincide EXACTAMENTE con una factura abierta del auxiliar
#          de clientes (ver cuentas_por_cobrar.csv). Ese cruce no lo puede
#          hacer el motor — vive en otro sistema — pero sí un agente con
#          acceso a la cartera.
mov_banco(date(2026, 9, 14), "DEP 0471", "DEPOSITO EFECTIVO SUCURSAL 0471", 93_600.00)

# Cartera abierta al cierre: el catálogo contra el que se resuelve el CASO 7.
CUENTAS_POR_COBRAR = [
    ("FAC-2288", "Grupo Ferretero del Bajío", "2026-08-28", "2026-09-27", 93_600.00),
    ("FAC-2304", "Constructora Peninsular", "2026-09-03", "2026-10-03", 412_850.00),
    ("FAC-2311", "Distribuidora Alfa Norte", "2026-09-09", "2026-10-09", 187_240.00),
    ("FAC-2318", "Comercializadora Sonora", "2026-09-15", "2026-10-15", 76_930.00),
    ("FAC-2325", "Aceros y Perfiles del Golfo", "2026-09-22", "2026-10-22", 254_100.00),
    ("FAC-2329", "Grupo Logístico Altamira", "2026-09-26", "2026-10-26", 93_615.00),
]

# CASO 8 — Intereses ganados de la inversión overnight: en banco, no en libros.
mov_banco(date(2026, 9, 30), "INT GAN", "INTERESES GANADOS INVERSION", 8_742.15)
mov_banco(date(2026, 9, 30), "ISR INT", "ISR RETENIDO INTERESES", -1_223.90)

# CASO 9 — Cargo no reconocido. Alta severidad: nadie debe "resolverlo" solo.
mov_banco(date(2026, 9, 19), "REF 88213", "CARGO NO RECONOCIDO REF 88213", -34_900.00)

# CASO 10 — Partida de corte: el traspaso a la cuenta de inversión salió del
#           banco el 30/sep pero se registró en la póliza de OCTUBRE, es decir
#           fuera del periodo que se está conciliando. Por eso NO aparece en
#           el auxiliar de septiembre: es una diferencia de corte, no un error.
mov_banco(date(2026, 9, 30), "TRASP INV", "TRASPASO A CUENTA INVERSION 7781", -250_000.00)


# --------------------------------------------------------------------------
# 3) Escritura de archivos.
# --------------------------------------------------------------------------
def escribir_formatos_reales() -> None:
    """Los mismos movimientos, tal como los entregan cuatro instituciones.

    Sirven SÓLO para la narrativa de la demo: antes de conciliar hay que
    normalizar, y ese pegamento es trabajo real que nadie ve en las
    presentaciones. Cada archivo reproduce un patrón que quien concilia
    reconoce de inmediato.

    Los nombres de banco son genéricos a propósito. Los patrones de formato
    son reales y reconocibles; atribuirlos a una institución concreta sería
    afirmar algo que no se puede verificar, y basta con que una persona del
    público use ese banco a diario para que la demo pierda credibilidad.
    """
    dir_f = DIR / "formatos_reales"
    dir_f.mkdir(exist_ok=True)
    muestra = banco[:14]

    # --- Banco A: CSV con preámbulo. La primera fila NO son los encabezados. --
    with (dir_f / "banco_a_export.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ESTADO DE CUENTA ENLACE EMPRESARIAL"])
        w.writerow(["CLIENTE:", EMPRESA.upper()])
        w.writerow(["No. DE CUENTA:", CUENTA, "PERIODO:", PERIODO.upper()])
        w.writerow(["SALDO INICIAL:", f"{SALDO_INICIAL:,.2f}"])
        w.writerow([])
        w.writerow(["FECHA", "DESCRIPCION", "CARGO", "ABONO", "SALDO"])
        saldo = SALDO_INICIAL
        for r in muestra:
            saldo = round(saldo + r["flujo"], 2)
            w.writerow([r["fecha"].strftime("%d/%m/%Y"), r["descripcion"],
                        f"{-r['flujo']:,.2f}" if r["flujo"] < 0 else "",
                        f"{r['flujo']:,.2f}" if r["flujo"] > 0 else "",
                        f"{saldo:,.2f}"])
        w.writerow([])
        w.writerow(["", "", "", "SALDO FINAL:", f"{saldo:,.2f}"])

    # --- Banco B: una sola columna de monto, con signo. Y DOS fechas. --------
    with (dir_f / "banco_b_movimientos.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha_operacion", "fecha_aplicacion", "referencia",
                    "concepto", "monto", "divisa"])
        for r in muestra:
            aplicacion = habil_mas(r["fecha"], 1) if r["flujo"] < 0 else r["fecha"]
            w.writerow([r["fecha"].isoformat(), aplicacion.isoformat(),
                        r["referencia"], r["descripcion"],
                        f"{r['flujo']:.2f}", "MXN"])

    # --- Banco C: importes con signo ARRASTRADO y concepto truncado. --------
    #     Herencia de sistemas mainframe: el negativo va al final del número.
    with (dir_f / "banco_c_export.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["FEC_OPER", "FOLIO", "DESC", "IMPORTE", "IND"])
        for r in muestra:
            importe = f"{abs(r['flujo']):,.2f}" + ("-" if r["flujo"] < 0 else "")
            w.writerow([r["fecha"].strftime("%Y%m%d"), r["referencia"],
                        r["descripcion"][:24], importe,
                        "D" if r["flujo"] < 0 else "C"])

    # --- Banco D: ancho fijo extraído de un PDF, con encabezados repetidos. --
    lineas = []
    saldo = SALDO_INICIAL
    for pagina in range(2):
        lineas += [
            "BANCO D, S.A.  INSTITUCION DE BANCA MULTIPLE".center(78),
            f"ESTADO DE CUENTA AL {date(2026, 9, 30):%d/%m/%Y}".center(78),
            f"CUENTA {CUENTA}".center(78),
            "",
            "FECHA      CONCEPTO                                RETIRO    DEPOSITO",
            "-" * 78,
        ]
        for r in muestra[pagina * 7:(pagina + 1) * 7]:
            saldo = round(saldo + r["flujo"], 2)
            retiro = f"{-r['flujo']:,.2f}" if r["flujo"] < 0 else ""
            deposito = f"{r['flujo']:,.2f}" if r["flujo"] > 0 else ""
            lineas.append(f"{r['fecha']:%d/%m/%y}   {r['descripcion'][:36]:<36} "
                          f"{retiro:>11} {deposito:>11}")
        lineas += ["", f"Pagina {pagina + 1} de 7".rjust(78),
                   "ESTE DOCUMENTO ES UNA REPRESENTACION IMPRESA DE UN CFDI".center(78),
                   "\f"]
    (dir_f / "banco_d_extracto.txt").write_text("\n".join(lineas), encoding="utf-8")

    print(f"Formatos reales  :    4 archivos     ->  formatos_reales/")


def escribir() -> None:
    banco.sort(key=lambda r: (r["fecha"], r["referencia"]))
    libros.sort(key=lambda r: (r["fecha"], r["poliza"]))

    saldo = SALDO_INICIAL
    with (DIR / "estado_cuenta.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha", "referencia", "descripcion", "cargo", "abono", "saldo"])
        for r in banco:
            saldo = round(saldo + r["flujo"], 2)
            cargo = f"{-r['flujo']:.2f}" if r["flujo"] < 0 else ""
            abono = f"{r['flujo']:.2f}" if r["flujo"] > 0 else ""
            w.writerow([r["fecha"].isoformat(), r["referencia"],
                        r["descripcion"], cargo, abono, f"{saldo:.2f}"])

    with (DIR / "auxiliar_contable.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # En el auxiliar de Bancos: cargo = entra dinero, abono = sale.
        w.writerow(["fecha", "poliza", "concepto", "tercero", "cargo", "abono"])
        for r in libros:
            cargo = f"{r['flujo']:.2f}" if r["flujo"] > 0 else ""
            abono = f"{-r['flujo']:.2f}" if r["flujo"] < 0 else ""
            w.writerow([r["fecha"].isoformat(), r["poliza"], r["concepto"],
                        r["tercero"], cargo, abono])

    # Los MISMOS movimientos del banco, expresados como los entrega otra
    # institución: encabezados distintos, fecha dd/mm/aaaa, importes con
    # separador de miles y columnas RETIRO/DEPOSITO en vez de cargo/abono.
    # Es el archivo del cuaderno de Colab: el conciliador no lo entiende hasta
    # que alguien escribe el mapeo — y ese "alguien" puede ser la IA.
    with (DIR / "estado_cuenta_otro_banco.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["FECHA OPERACION", "FOLIO", "CONCEPTO / DESCRIPCION",
                    "RETIRO", "DEPOSITO"])
        for r in banco:
            retiro = f"{-r['flujo']:,.2f}" if r["flujo"] < 0 else ""
            deposito = f"{r['flujo']:,.2f}" if r["flujo"] > 0 else ""
            w.writerow([r["fecha"].strftime("%d/%m/%Y"), r["referencia"],
                        r["descripcion"], retiro, deposito])

    with (DIR / "cuentas_por_cobrar.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["folio", "cliente", "fecha_emision", "fecha_vencimiento", "saldo"])
        for folio, cliente, emision, venc, saldo_fac in CUENTAS_POR_COBRAR:
            w.writerow([folio, cliente, emision, venc, f"{saldo_fac:.2f}"])

    print(f"Cartera abierta  : {len(CUENTAS_POR_COBRAR):>4} facturas     ->  cuentas_por_cobrar.csv")
    print(f"Estado de cuenta : {len(banco):>4} movimientos  ->  estado_cuenta.csv")
    print(f"Auxiliar contable: {len(libros):>4} partidas     ->  auxiliar_contable.csv")
    print(f"Saldo final banco: ${saldo:,.2f}")
    print(f"Suma libros      : ${SALDO_INICIAL + sum(r['flujo'] for r in libros):,.2f}")


if __name__ == "__main__":
    escribir()
    escribir_formatos_reales()
