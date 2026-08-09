# Manual de políticas contables — Industrias del Norte, S.A. de C.V.
### Sección 7: Conciliaciones bancarias (vigente desde enero 2026)

> Documento ficticio, redactado para la demostración. Reproduce la estructura
> de un manual real: umbrales, facultades y evidencia requerida.

## 7.1 Umbral de materialidad

- **Materialidad de partida individual:** $500.00 MXN.
  Las diferencias iguales o menores a este importe pueden regularizarse
  directamente contra `705-002 Otros gastos financieros` sin autorización
  adicional, siempre que se documente la causa.
- **Materialidad acumulada del periodo:** $25,000.00 MXN.
  Si la suma de partidas regularizadas por materialidad supera este importe,
  la conciliación completa debe revisarse con el Contralor antes del cierre.

## 7.2 Facultades de autorización de asientos de ajuste

| Importe del asiento | Autoriza |
|---|---|
| Hasta $50,000.00 | Contador General |
| $50,000.01 a $250,000.00 | Contralor |
| Más de $250,000.00 | Dirección de Finanzas |

Ningún asiento de ajuste derivado de una conciliación puede registrarse en
firme sin la autorización que corresponda a su importe. Los asientos
propuestos por herramientas automatizadas se registran **siempre en estatus
de borrador** y requieren autorización explícita de una persona facultada.

## 7.3 Cuentas de aplicación más frecuentes

| Concepto | Cuenta |
|---|---|
| Comisiones bancarias | `705-001 Comisiones bancarias` |
| IVA acreditable de comisiones | `118-002 IVA acreditable pagado` |
| Intereses ganados | `703-001 Productos financieros` |
| ISR retenido sobre intereses | `113-004 ISR retenido por acreditar` |
| Diferencias cambiarias | `705-003 Pérdida cambiaria` / `703-002 Utilidad cambiaria` |
| Otros gastos financieros no identificados | `705-002 Otros gastos financieros` |
| Bancos — cuenta BBVA 0198 4471 92 | `102-001 Bancos BBVA` |
| Clientes | `105-001 Clientes nacionales` |

## 7.4 Partidas en conciliación (no generan asiento)

Se dejan como partida en conciliación, sin registro contable, hasta que se
resuelvan por sí mismas:

- **Cheques en tránsito:** expedidos y registrados en libros, aún no cobrados
  en el banco. Si superan **90 días** sin cobrarse, se cancelan y se reintegra
  el pasivo.
- **Depósitos en tránsito:** registrados en libros, aún no acreditados por el
  banco al corte.
- **Partidas de corte:** movimientos del banco cuya póliza corresponde al
  periodo siguiente. Se documentan y se verifican en la conciliación del mes
  siguiente.

## 7.5 Movimientos no reconocidos

Cualquier cargo o abono del banco que no pueda vincularse a una operación
propia **debe escalarse el mismo día** al Contralor y levantarse aclaración
ante la institución bancaria. **Está prohibido** regularizar contablemente un
movimiento no reconocido, cualquiera que sea su importe, antes de agotar la
aclaración bancaria. El plazo legal para objetar cargos ante la institución
es de **90 días naturales**.

## 7.6 Cobros no identificados

Un depósito sin referencia se aplica a la factura abierta cuyo importe
coincida **exactamente** y cuyo cliente tenga saldo vencido. Si hay más de
una factura candidata con importes similares, **no se aplica**: se registra
en `205-003 Anticipos de clientes por identificar` y se solicita el
comprobante al cliente.

## 7.7 Evidencia requerida por el auditor

Toda conciliación debe conservar: (a) estado de cuenta original, (b) auxiliar
contable del periodo, (c) acta de conciliación firmada, (d) soporte de cada
partida en conciliación y (e) **bitácora de quién autorizó cada ajuste y
cuándo**. Cuando intervenga una herramienta automatizada, la bitácora debe
identificar además la versión de la herramienta y conservar su propuesta
original, incluso si fue rechazada.
