# Descripción Detallada del Flujo — Pipeline Partes Diarios (Python Local)

Este documento explica de forma extensa y detallada el funcionamiento del pipeline completo (end-to-end), desde la ingesta de archivos Excel crudos hasta la valoración económica de los controles de observaciones y la generación del modelo en estrella final.

El pipeline ha sido migrado de PySpark (Fabric) a un entorno Python local utilizando Pandas, guardando los datos en formato Parquet a nivel local (`data/`).

---

## Índice

1. [Etapa 0: Extracción de Seeds (Oracle)](#etapa-0-extracción-de-seeds-oracle)
2. [Etapa 1: Generación de Maestros](#etapa-1-generación-de-maestros)
3. [Etapa 2: Adapters (Ingesta)](#etapa-2-adapters-ingesta)
4. [Etapa 3: Core Waterfall (Cruce y Deduplicación)](#etapa-3-core-waterfall-cruce-y-deduplicación)
5. [Etapa 4: Control de Observaciones (USES)](#etapa-4-control-de-observaciones-uses)
6. [Catálogo de Reglas y Trazas](#catálogo-de-reglas-y-trazas)

---

## Etapa 0: Extracción de Seeds (Oracle)

Esta es la única etapa que se conecta al exterior. Utiliza las credenciales en `.env` para conectarse a las bases de datos de EPEC (SIGEC y GEOREF) en modo solo lectura.

**¿Qué hace?**
Extrae volcados (seeds) de las tablas transaccionales para usarlas en el pipeline.
1. `dim_ord`: Universo base de todos los ordenativos de trabajo (CE, IC, CX, etc.). Se traen millones de registros.
2. `sigec_general`: Datos comerciales y de georreferenciación de cada suministro activo.
3. `dim_stk_stock_equipos`: Inventario maestro de medidores, contiene si el medidor es Monofásico (MON) o Trifásico (TRI).
4. `eqp_equipos_ultimos_10`: Una tabla pivoteada y preprocesada en base de datos con los últimos 10 medidores que pasaron por cada suministro. Es crucial para el "Cruce C" del waterfall.
5. `pivot_resul_app_movil`: Las observaciones reales cargadas por el operario en campo usando la app móvil.
6. `usuarios_gral`: Directorio de usuarios para traducir IDs de operarios a nombres reales.

**Archivos generados**: `data/seed/*.parquet`

---

## Etapa 1: Generación de Maestros

Lee archivos de configuración (Excel) estáticos provistos por el área de negocio y los convierte en tablas maestras.

1. **mapeo_codigos_master**: Un diccionario unificado que le dice al pipeline "si CONECTAR reporta el código 15 y COOPLYF reporta el código 18, ambos equivalen al COD_EPEC 43, que tiene una valoración de 0.04 USES".
2. **reglas_cod_obs_app**: Es la matriz de la verdad para el control de observaciones. Define para cada `COD_EPEC` cuáles de los 8 flags de observaciones (`_APP_GABINETE`, `_APP_ACOMETIDA`, etc.) deberían estar encendidos (1) o apagados (0) si el trabajo fue realizado correctamente en campo.

**Archivos generados**: `data/master/*.parquet`

---

## Etapa 2: Adapters (Ingesta)

Los contratistas envían lotes diarios de archivos Excel con el trabajo realizado por sus operarios. Cada contratista tiene su formato.

**¿Qué hace?**
- Estandariza nombres de columnas a un formato común (`Suministro`, `Fecha`, `codTiposManoObra`, `medidorColocado`, `medidorRetirado`).
- Castea tipos de datos (fechas, strings, números).
- Limpia strings (elimina espacios extras, estandariza mayúsculas).
- Guarda un registro (bitácora) en `data/stage/_bitacora_carga.json` para saber qué archivos ya fueron procesados y evitar duplicados en la ingesta, a menos que se fuerce con el flag `--reproceso`.

**Archivos generados**: `data/stage/staging_conectar.parquet` y `data/stage/staging_cooplyf.parquet`

---

## Etapa 3: Core Waterfall (Cruce y Deduplicación)

Este es el cerebro del proceso. Su objetivo es tomar la "declaración jurada" del contratista (los partes en el staging) y cruzarla contra la verdad del sistema de EPEC (las seeds de Oracle) para decidir si se le aprueba el pago.

### 3.1 El Waterfall de Cruces (Sub-bloque 3.3)

El pipeline pasa cada parte diario por una "cascada" de reglas. La primera regla que matchea se lleva el parte.

#### Cruce A (Match Perfecto)
Intenta cruzar el parte contra un ordenativo `CE` (Cambio de Equipo) que pertenezca a la misma contratista. La ventana de tolerancia de fecha es de ±15 días.
- **Regla de Oro (IN)**: Si el ordenativo cruzado tiene `ORD_RESULTADO = IN` (Informado), cruza exitosamente pero se marca con la traza `Informado - No Ejecutado` y se **rechaza**, porque el operario nunca fue al campo.
- Si el ordenativo es ejecutado (`E`), se comparan los números de medidor (Colocado/Retirado) del parte contra lo que dice SIGEC (`eqp_equipos_ultimos_10`):
  - **`Original OK`**: Los medidores son idénticos.
  - **`Corregido Nro EQP Invertidos`**: Escribió los dos bien, pero al revés.
  - **`Corregido Nro Medidor`**: Uno o ambos están mal en el parte; SIGEC tiene la razón, así que se corrigen.
  - **`Corregido Medidor Vacio`**: No declaró medidor, se asume el de SIGEC.

#### Cruce B (Fuera de Alcance)
Los partes que sobrevivieron al Cruce A (porque no encontraron un ordenativo CE), se buscan contra **cualquier ordenativo no-CE** (ej. IC, RX, CX).
- Si encuentran uno, se marcan como **`No Corresponde TOR CE`** y se descartan (estaban haciendo otra tarea que no nos compete).

#### Cruce C (Rescate Técnico)
Para los partes que siguen sueltos, se hace un intento de "rescate" asumiendo que el operario escribió mal el número de suministro, pero escribió bien el número de medidor.
- Se busca en SIGEC a qué suministro real pertenece ese medidor.
- Luego se busca si ese suministro real tiene un ordenativo CE pendiente.
- Si lo tiene, se asigna la traza **`Corregido Sumi`** o **`Corregido Sumi Nro EQP`**.

#### Los Huérfanos
Si después de los 3 cruces el parte sigue suelto, es porque EPEC no tiene constancia de esa orden. Se marcan como rechazados: **`Sin Orden Asociada`** o **`Error Sumi Y Nro Medidor`**.

### 3.2 Reglas Adicionales y Deduplicación

Antes de finalizar la etapa 3, se aplican reglas de enriquecimiento y limpieza:

1. **Regla "Otro Origen"**: Si el ordenativo tiene un sector de origen distinto a `PROTELEM`, la traza se pisa a **`Otro Origen`** y el parte es descartado.
2. **Enriquecimiento**: Se joinea con maestros para agregar el nombre del operario, la fase real del medidor (MON/TRI), y el código unificado de EPEC con su valor en USES.
3. **Deduplicación ("Informados con ORD-SUMI aprobado")**: A veces las contratistas mandan el mismo suministro varias veces en distintos días. El sistema los agrupa y elige al **mejor candidato** (prioriza códigos que no sean "Informado", fecha más reciente y row ID más alto). El ganador sigue vivo, todos los perdedores reciben la traza **`Informados con ORD-SUMI aprobado`** y son rechazados.

### 3.3 Creación de Dimensiones y Fact Table

Todos los partes, aprobados y rechazados, se vuelcan en la tabla de hechos central `fact_partes_diarios_full`.
Luego se actualizan las dimensiones: calendario, geografía, estado, etc.

**Archivos generados**: `data/gold/fact_partes_diarios_full.parquet`, `data/dim/*.parquet`

---

## Etapa 4: Control de Observaciones (USES)

El control de observaciones actúa **únicamente sobre los partes que fueron aprobados** en la Etapa 3.
El problema de negocio a resolver es: *El operario cobró un Cambio de Equipo Trifásico Completo (0.12 USES), pero al ver la app móvil, no marcó que haya cambiado ni el gabinete, ni la acometida. ¿Realmente hizo ese trabajo?*

### Flujo de Valoración Económica

1. **Join de Aprobados**: Se cruzan los partes aprobados de la fact contra `pivot_resul_app_movil`.
2. **Normalización App**: Las observaciones cargadas (ej. "Tapa Rota", "Gabinete Nuevo") se traducen a 8 columnas binarias booleanas 0/1 (`_APP_GABINETE`, `_APP_ACOMETIDA`, etc.).
3. **Cálculo de Distancia Hamming**: Por cada parte, el sistema evalúa su perfil binario contra las 21 reglas teóricas del maestro de observaciones. La regla teórica que tenga menos "diferencias" (distancia Hamming más baja) se convierte en el `COD_EPEC_SUGERIDO`.
4. **Valoración Económica**:
   - `VALOR_USES_ORIGEN`: Lo que declaró el contratista que iba a cobrar.
   - `VALOR_USES_OBS`: Lo que el sistema calcula que debe cobrar basado en el `COD_EPEC_SUGERIDO`.
   - `DIFERENCIA_USES = VALOR_USES_ORIGEN - VALOR_USES_OBS`.
5. **Clasificación de la Discrepancia**:
   - **`Sin Discrepancia`**: Lo declarado coincide con lo sugerido.
   - **`Sobrevaloración`**: El contratista declaró un código caro, pero las observaciones sugieren un código barato (pérdida económica para EPEC).
   - **`Subvaloración`**: El contratista declaró un código barato, pero hizo más trabajo del reportado (pérdida económica para la contratista).
   - **`Error Operativo`**: Códigos distintos, pero valen la misma cantidad de USES (impacto $0).
   - **`Sin Observaciones`**: El operario olvidó usar la app o cargar datos.

Esta etapa permite auditar y ajustar los pagos a los contratistas.

**Archivos generados**: `data/gold/control_obs_app.parquet` y `data/dim/dim_img_app_pd.parquet` (fotos de la app).

---

## Catálogo de Reglas y Trazas

### Estados Finales (`ESTADO_PROCESO`)
- **Aprobado**: Matcheó un ordenativo CE válido y no fue deduplicado.
- **Rechazado**: El parte tiene errores severos, fue duplicado o es un ordenativo Informado (`IN`).
- **Revisión**: Trazas de OCR, requieren chequeo manual.
- **Fuera de Alcance**: Ordenativos de otra área (Otro Origen) o de otro tipo (No Corresponde TOR CE).

### Trazas de Calidad
- **`Original OK`**: Match perfecto en Cruce A.
- **`Corregido Nro EQP Invertidos` / `Corregido Nro Medidor` / `Corregido Medidor Vacio`**: Match en Cruce A, pero se forzaron los medidores de SIGEC.
- **`Corregido Sumi` / `Corregido Sumi Nro EQP`**: Match en Cruce C (rescate por medidor).
- **`Informado - No Ejecutado`**: Ordenativo `IN`, se rechaza el parte porque no hubo trabajo de campo.
- **`Informados con ORD-SUMI aprobado`**: Perdedor en la deduplicación (ya se pagó otro parte para este suministro).
- **`No Corresponde TOR CE`**: El ordenativo cruzado no era CE (Cruce B).
- **`Otro Origen`**: La orden no pertenece a sector `PROTELEM`.
- **`Sin Orden Asociada` / `Error Sumi...`**: Huérfanos, no cruzaron contra nada.
