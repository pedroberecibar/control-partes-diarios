# Guía de Estados y Trazas de Calidad (Partes Diarios)

Este documento detalla la lógica central del Motor Analítico (Backend) respecto a cómo se clasifican los Partes Diarios en **Estados de Proceso** y qué **Trazas de Calidad** (casos o motivos) caen dentro de cada estado.

> **Nota importante:** Este documento refleja la **fuente de verdad del Backend** (definida en `src/config.py` y `src/etapa3_core.py`). Cualquier discrepancia con el Frontend debe ser ajustada en la UI para reflejar esta lógica de negocio.

---

## 🟢 ESTADO: Aprobado (ID: 1)
Partes que han superado con éxito las validaciones del motor y se consideran **listos para pago/liquidación** de forma automática, sin requerir intervención humana.

*   **Original OK (Traza 1):** El parte ingresado por el operario cruzó perfectamente (por Suministro y Fecha) con una Orden de Trabajo "CE" en Oracle. No hubo necesidad de alterar los datos.
*   **Corregido Nro EQP Invertidos (Traza 2):** El operario se equivocó al cargar los datos en la app/Excel anotando el medidor retirado en el casillero del colocado, y viceversa. El motor detectó la inversión y la corrigió automáticamente.
*   **Corregido Nro Medidor (Traza 3):** El número de suministro declarado hizo match con Oracle, pero el número de medidor difería. El motor corrigió el medidor utilizando la base técnica de la compañía.
*   **Corregido Sumi (Traza 4):** El número de medidor declarado era correcto, pero el suministro estaba mal escrito. El motor hizo ingeniería inversa, identificó el suministro real al que pertenece ese medidor, y lo corrigió.
*   **Corregido Medidor Vacio (Traza 12):** El campo del medidor colocado vino vacío desde el contratista, pero el suministro era válido y se logró rescatar el medidor colocado desde Oracle.

---

## 🟡 ESTADO: Revisión (ID: 2)
Partes que pudieron ser rescatados o corregidos parcialmente por el motor, pero la corrección no es 100% segura. Requieren **verificación humana** antes de pasar a Aprobado o Rechazado.

*   **Corregido Sumi Nro EQP (Traza 5):** Tanto el suministro como los medidores declarados eran incorrectos o no cuadraban de forma directa, pero el motor logró inferir un candidato en base a cruces indirectos. Al tener alta probabilidad de error humano, se bloquea el pago hasta que un auditor valide la foto del medidor.
*   **Rescatado por Oracle (Traza 19):** El motor logró encontrar un match usando heurísticas muy forzadas (como tolerancias de fecha extremas o cruces difusos en la DB), pero la regla de negocio requiere revisión humana obligatoria.
*   **Múltiples Candidatos Oracle (Traza 20):** La consulta arrojó múltiples órdenes idénticas para el mismo suministro en el mismo día y el motor no puede desambiguar con certeza cuál se está rindiendo, requiriendo intervención manual.

---

## ⚪ ESTADO: Fuera de Alcance (ID: 4)
Partes que corresponden a órdenes de trabajo válidas pero que **no pertenecen al contrato actual de lectura y cambio de medidores** (TOR CE), o cuyo código de tarea no forma parte del alcance operativo contratado.

*   **No Corresponde TOR CE (Traza 6):** La orden de trabajo existe en Oracle, pero es de otro tipo (por ejemplo: Conexiones nuevas, Cortes por morosidad, Reclamos técnicos, etc.).
*   **Otro Origen (Traza 11):** La orden proviene de un sistema satélite u origen distinto (ej. no es PROTELEM) que está excluido del circuito de facturación automatizada actual.
*   **Código de Tarea No Mapeado (Traza 14):** El código operativo reportado por el contratista en el Excel (ej. "MT-04") no existe en el archivo maestro de conversiones EPEC. No es un error de ejecución del operario, sino un descarte sistémico: el trabajo reportado no forma parte del alcance operativo contratado.

---

## 🔴 ESTADO: Rechazado (ID: 3)
Partes que **no son pagables**. Contienen errores críticos, son duplicados sistémicos, o simplemente no tienen sustento técnico en Oracle.

### Errores Operativos / No Recuperables
*   **Sin Orden Asociada (Traza 7):** No se encontró ninguna orden en Oracle que coincida con el Suministro/Medidor declarado dentro de la ventana de tiempo tolerable (+/- 15 días).
*   **Error Sumi Sin Nro Medidor (Traza 8):** El suministro falló en el cruce de Oracle y, además, no hay número de medidor para intentar el rescate técnico inverso.
*   **Error Sumi Y Nro Medidor (Traza 9):** Ni el suministro ni el medidor declarados existen o concuerdan con registros técnicos en los sistemas de la compañía.
*   **Informado - No Ejecutado (Traza 13):** La orden existe en Oracle, pero su resultado oficial es "IN" (Incompleto / No Ejecutado). La contratista no puede cobrar un trabajo que figura como fallido.
*   **Fecha Inválida (Traza 15):** La fecha de ejecución reportada no es una fecha válida o cae muy fuera de la ventana operativa lógica del lote.
*   **Datos Clave Faltantes (Traza 17):** Faltan datos estructurales en la fila del Excel (ej. campos obligatorios como suministro, medidor o fecha en blanco) impidiendo siquiera intentar el cruce. Nota: El campo operario es opcional y puede venir en blanco.

### Errores Sistémicos y Duplicados
*   **Informados con ORD-SUMI aprobado (Traza 10):** *Duplicado de negocio (Repetido por Suministro)*. Dentro del mismo lote, se reportó varias veces el mismo suministro/medidor. El motor ya aprobó a la "mejor" fila candidata, por lo que esta fila se descarta para evitar pagar dos veces la misma orden.
*   **Duplicado Exacto en Archivo Origen (Traza 16):** La fila es un calco exacto (100% idéntica) de otra fila dentro del mismo Excel subido.
*   **Registro Ya Procesado en Lote Anterior (Traza 18):** El operario está intentando volver a cobrar un parte que ya fue enviado, validado y guardado en un lote de días anteriores.

---

## ✅ Sincronización Backend/Frontend Completada

La lógica documentada arriba es ahora la **fuente de verdad unificada**. Anteriormente existían discrepancias donde el frontend agrupaba ciertas trazas (5, 10, 13, 19, 20) en categorías incorrectas, pero tras la última refactorización, los 4 estados principales (Aprobado, Revisión, Rechazado y Fuera de Alcance) están completamente alineados tanto en el motor de clasificación del backend (`config.py`) como en la visualización del dashboard web (`DetalleLote.jsx` y mocks de UI).
