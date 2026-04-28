# Plan de Migración a Entorno Local (PySpark/Fabric → Pandas)

> Objetivo: portar el pipeline de Partes Diarios (4 etapas) desde Microsoft Fabric (PySpark + Delta + `mssparkutils` + Sharepoint) a un entorno **100% local** basado en **Python puro + Pandas**, preservando de forma **estricta** la lógica de negocio (especialmente los cruces del Core y la valoración económica USES), pero aprovechando para modularizar, vectorizar y optimizar memoria.
>
> Destinatario: `python-version/` (proyecto vacío salvo `requirements.txt`).
> Origen: `pyspark-version/` (4 scripts + este plan).

---

## 0. Estado del Proyecto (snapshot al 2026-04-23)

> Fuente de verdad rápida del avance. Cuando se avance, marcar las casillas e ir
> moviendo los items de "pendiente" a "hecho". El detalle de cada fase está
> más abajo en el plan, esto es solo el panel de control.

### 0.1 Resumen por fase

| Fase | Descripción                                       | Estado          | Notas / Bloqueos                                                                 |
|------|---------------------------------------------------|-----------------|----------------------------------------------------------------------------------|
| 0    | Scaffolding (config, io_lakehouse, hashing)       | ✅ Hecho        | Capas creadas; `data/seed/`, `data/dim/`, `data/gold/` existen como dirs vacíos.|
| 1    | Etapa 1 — Maestros                                | ✅ Hecho        | Genera `mapeo_codigos_master.parquet` y `reglas_cod_obs_app.parquet`.            |
| 2A   | Etapa 2 — Adapter CONECTAR                        | ✅ Hecho        | 5 archivos en bitácora; `pd_conectar_aux.parquet` poblado.                        |
| 2B   | Etapa 2 — Adapter COOPLYF                         | ✅ Hecho        | 4 archivos en bitácora; `pd_cooplyf_aux.parquet` poblado.                         |
| 2.5  | **Seeds desde SIGEC** (dim_ord, eqp, stk, …)      | ✅ Hecho        | `etapa0_seeds.py` operativo. 6/6 seeds en `data/seed/` (~739 MB total). Bootstrap dim_ord 5.7M filas; eqp filtrado por SRV del staging. Ver §0.3.2.|
| 3    | Etapa 3 — Core Waterfall                          | ⛔ No iniciado  | Necesita seeds. Próximo gran hito.                                                |
| 3.4  | dim_suministros_geo + dim_calendario              | ⛔ No iniciado  | Depende del Core (Geo) y de la fact (calendario).                                |
| 4    | Etapa 4 — Control de observaciones                | ⛔ No iniciado  | Depende del Core. Reglas estáticas ya están en `master/`.                         |
| 5    | Orquestador, logging, CLI                         | 🟡 Parcial     | `run_pipeline.py` ya tiene `--solo-etapa {1,2}` + `--reproceso` y logging a archivo. Falta: flag `--contratista`, fail-fast explícito, dict de métricas estandarizado y un README de uso. |
| Tests| Suite `pytest` para cada fase                    | ⛔ No iniciado  | Crear `tests/` con fixtures mínimos para cuando estén las seeds.                  |

### 0.2 Inventario actual del proyecto

```
python-version/
├── data/
│   ├── input/
│   │   ├── conectar/   ← 5 xlsx + 1 minuta (poblado)
│   │   ├── cooplyf/    ← 4 xlsx (poblado)
│   │   └── maestros/   ← OP_MI + conversion_codigos (poblado)
│   ├── master/         ← mapeo_codigos_master.parquet, reglas_cod_obs_app.parquet ✅
│   ├── stage/          ← pd_conectar_aux.parquet, pd_cooplyf_aux.parquet, _historial_procesados.parquet ✅
│   ├── seed/           ← (vacío, por crear)
│   ├── dim/            ← (vacío, por crear)
│   ├── gold/           ← (vacío, por crear)
│   └── logs/           ← run_*.log (3 corridas registradas)
├── docs/
│   ├── masters_actualization.md    ← consultas Oracle (dsn=STBY) para las 6 seeds
│   ├── oracle_conection_exaple.md  ← ejemplo `oracledb` + service_name PRODEBS_SEE
│   ├── cuadernos/                  ← post-procesos PySpark de eqp_equipos (referencia)
│   └── ejemplo_consulta_VM_GEOREFERENCIA/.json
├── src/
│   ├── config.py                ✅
│   ├── io_lakehouse.py          ✅ (read/write/merge/truncate)
│   ├── hashing.py               ✅ (id_parte_hash + id_externo_cooplyf)
│   ├── adapters_common.py       ✅ (bitácora _historial_procesados)
│   ├── etapa1_maestros.py       ✅
│   ├── etapa2_adapter_conectar.py ✅
│   └── etapa2_adapter_cooplyf.py  ✅
├── run_pipeline.py              🟡 (corre etapas 1 y 2)
└── requirements.txt             ✅
```

### 0.2.1 Glosario / mapeo de columnas (extraído del código PySpark)

> El mismo concepto de negocio aparece con varios nombres a lo largo del
> pipeline (input Excel → staging → seeds Oracle → fact → dimensiones BI).
> Esta tabla es el "diccionario": al leer cualquier módulo, traducir mentalmente
> al nombre canónico de la columna fact (columna derecha).

| Concepto                             | Origen Oracle / SIGEC               | Excel / staging input                                      | Aliases internos en el Core                                       | Schema canónico (`COLS_FACT`)        |
|--------------------------------------|--------------------------------------|------------------------------------------------------------|-------------------------------------------------------------------|--------------------------------------|
| **Suministro** (cuenta del cliente)  | `SRV_CODIGO` en la mayoría de tablas; `SUMI` en `sigec_general`; **`SUMINISTRO`** en `GEOREF.VM_SUMINISTROS` | `Suministro` (CONECTAR/COOPLYF), `NIS`, `idSuministros`, `Cuenta` (alias COOPLYF) | `Suministro_Norm`, `Suministro_Final`, `srv_tecnico`, `ord_suministro` | `SRV_CODIGO` (long)                  |
| **Suministro raw** (texto sin normalizar) | —                                | igual al anterior pero sin cast a long                    | —                                                                 | `SUMINISTRO_RAW` (string)             |
| Número de orden                      | `ORD_NUMERO` (`xxsigec.ordenativos`) | —                                                          | `NUMERO_ORDEN`                                                    | `ORD_NRO`                            |
| Tipo de orden                        | `TOR_CODIGO`                         | —                                                          | `TIPO_ORDEN_DETECTADO`, `ORD_TIPO_DETECTADO`                       | `ORD_TIPO_DETECTADO`                 |
| Resultado de la orden                | `ORD_RESULTADO` (E/IN/D/EH/EI = válido para CE) | —                                                | (sin renombre, solo se filtra)                                    | (no llega a la fact)                  |
| Sector origen                        | `SEC_CODIGO_ORIGEN` (= `PROTELEM` para app móvil) | —                                                | `col_origen_expr`                                                 | `SEC_CODIGO_ORIGEN`                   |
| Fecha de fin / "ejecución" de orden  | `ORD_FECHA_FIN`                      | —                                                          | `ord_fecha_ref` (vía `to_date`)                                   | `ORD_FECHA_FIN`                       |
| Fecha de inicio                      | `ORD_FECHA_INICIO`                   | —                                                          | (fallback de `ord_fecha_ref` cuando ORD_FECHA_FIN es null)        | (no llega a la fact)                  |
| Fecha del parte (input)              | —                                    | `Fecha`, `fecha`, `FECHA`                                  | `Fecha_Norm`                                                      | `FECHA`                               |
| Usuario ejecutor de orden            | `USR_NUMERO_EJEC_ORD` (en dim_ord)   | —                                                          | `ID_OPERARIO_RAW`                                                 | `USR_ID`                              |
| Usuario maestro (id)                 | `USR_NUMERO` (en `XXCO_USUARIOS_V`)  | —                                                          | (sin renombre)                                                    | `USR_ID` (vía join)                   |
| Sector del usuario (= contratista)   | `SEC_CODIGO`                         | —                                                          | (filtra `df_usr_pool` por contratista)                            | (no llega a la fact)                  |
| Equipo / medidor (id de stock)       | `STE_NUMERO` (en `STOCK_EQUIPOS`, `EQUIPOS`) | —                                                | `MEDIDOR_STOCK`                                                   | `NRO_EQP_*` (vía pivot)               |
| Fases del medidor                    | `STE_FASES`                          | —                                                          | `FASE_SIGEC`                                                      | (auxiliar, no a fact)                 |
| Equipo último instalado (pivot)      | `STE_NUMERO_ULTIMO` (derivado)       | —                                                          | `db_colocado`                                                     | `NRO_EQP_COLOCADO`                    |
| Equipo anterior 1 (pivot)            | `STE_NUMERO_ANTERIOR_1` (derivado)   | —                                                          | `db_retirado`                                                     | `NRO_EQP_RETIRADO`                    |
| Medidor colocado (input)             | —                                    | `Colocado`, `Medidor Colocado`, `nroMedidorColocado`       | `medidorColocado`                                                 | `NRO_EQP_COLOCADO`                    |
| Medidor retirado (input)             | —                                    | `Retirado`, `Medidor Retirado`, `nroMedidorRetirado`       | `medidorRetirado`                                                 | `NRO_EQP_RETIRADO`                    |
| Código de tarea / mano de obra       | —                                    | `Codigo`, `código`, `Tarea`, `codTiposManoObra`            | `codTiposManoObra`                                                | `CODIGO_CONTRATISTA`                  |
| Código EPEC                          | `CODIGOS_F218` (Excel maestro)        | (resultado de mapeo)                                       | `COD_EPEC`                                                        | `CODIGO_EPEC`                         |
| Tipo de trabajo                      | —                                    | `Tipo de trabajo`, `codTiposTrabajos`                      | `TipoTrabajo`                                                     | (no llega a fact)                     |
| Lat / Lon                            | `LATITUD`, `LONGITUD` (con coma decimal) | —                                                       | (cast a double con `regexp_replace(',', '.')`)                    | `LATITUD`, `LONGITUD` (en dim_geo)    |
| Departamento                         | `DPTO`                                | —                                                          | (renombrado)                                                      | `DEPARTAMENTO`                        |
| Imagen 1..5 (URL Firebase)           | `'APP4OBS_80..84'_TOB_DESCRIPCION` (cols del pivot) | —                                          | `IMAGEN_1..5` (en `dim_img_app_pd`)                                | —                                     |
| Hash idempotente del parte           | —                                    | —                                                          | SHA256(`ORIGEN_ARCHIVO|SRV_CODIGO|FECHA|medidorColocado|cod`)     | `ID_PARTE_HASH`                       |

> **Observación clave (confirmada por usuario el 2026-04-23):** *Suministro* y
> *SRV_CODIGO* son sinónimos. Cualquier columna que se llame "Suministro",
> "SUMI" o "SUMINISTRO" en una tabla origen mapea al `SRV_CODIGO` canónico (cast
> a `long`).

### 0.3 Próximos pasos accionables (en orden)

> Aquí es donde encaja el archivo `python-version/docs/masters_actualization.md`
> que el usuario armó: contiene las **6 consultas Oracle a SIGEC standby** que
> hay que ejecutar para poblar `data/seed/` antes de empezar la Fase 3.

1. **(P0) Crear `src/etapa0_seeds.py`** — extractor Oracle → Parquet.
   - Lee credenciales de `.env` (ya creado), conecta vía `src/oracle_io.py`
     (`OracleReadOnly`, sesión READ ONLY garantizada).
   - Ejecuta consultas adaptadas de `docs/masters_actualization.md` con la
     estrategia local (más eficiente que el dump full original):

     | # | Tabla destino                              | Fuente Oracle                                                              | Filtro / estrategia                                                                                  |
     |---|--------------------------------------------|----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
     | 1 | `seed/dim_ord.parquet`                     | `xxsigec.ordenativos`                                                       | **Bootstrap (1ª vez):** `ORD_FECHA_FIN >= 2025-01-01 OR ORD_FECHA_INICIO >= 2025-01-01 OR ORD_ULTIMA_ACTUALIZACION >= 2025-01-01`. **Refresh incremental:** `>= sysdate-4` y MERGE local por `ORD_NUMERO`. |
     | 2 | `seed/eqp_equipos_ultimos_10.parquet`      | `XXSIGEC.EQUIPOS`                                                           | **Filtrado por SRV_CODIGO** del staging+fact (no full table). Función `refresh_eqp(srv_codigos)`. Pivot top-10 local por SRV_CODIGO (portar v2 de `docs/cuadernos/eqp_equipos_tabla_pivot_ultimo_10_med.py`). |
     | 3 | `seed/dim_stk_stock_equipos.parquet`       | `XXSIGEC.STOCK_EQUIPOS` (full, 2.2M filas, ~250MB Parquet)                  | Overwrite (refresh ocasional, no por run)                                                            |
     | 4 | `seed/usuarios_gral.parquet`               | `XXSIGEC.XXCO_USUARIOS_V` (full, 952 filas)                                  | Overwrite                                                                                            |
     | 5 | `seed/sigec_general.parquet`               | `GEOREF.VM_SUMINISTROS` (full, 1.2M × 91 cols)                              | Overwrite. Ojo nombre: el Core PySpark consume tabla "sigec_general" con cols `SUMI/LATITUD/LONGITUD/CALLE/...`. Mapear `VM_SUMINISTROS.SUMINISTRO` → `SUMI` (= SRV_CODIGO) al persistir, o ajustar el Core para leer `SUMINISTRO` directo. |
     | 6 | `seed/pivot_resul_app_movil.parquet`       | pivot sobre `xxco_observaciones_ordenativ_v` ⨝ `ordenativos` (TOR='CE')      | Overwrite. **Query lenta (~65s)**, agendar refresh semanal salvo cambio de reglas.                   |

   - **Por qué cambió la estrategia vs el .md original** (Fabric vs local):
     - dim_ord en Fabric era incremental sobre un baseline ya existente. Acá no
       tenemos baseline, así que el bootstrap inicial trae todo desde Enero
       2025 (decisión validada con usuario el 2026-04-24, balance entre
       cobertura histórica y volumen).
     - `eqp_equipos_ultimos_10` en Fabric corría dos cuadernos sobre la tabla
       FULL `eqp_equipos_gral`. Acá optimizamos: solo traemos las filas de
       `XXSIGEC.EQUIPOS` correspondientes a los SRV_CODIGO que aparecen en el
       staging+fact (típicamente unos miles, no millones), y hacemos el pivot
       local. El Core solo usa 3 columnas del pivot (`SRV_CODIGO`,
       `STE_NUMERO_ULTIMO`, `STE_NUMERO_ANTERIOR_1`), así que esto es
       perfectamente equivalente para los downstream.

   - **Orden de ejecución importante**: por 2.2.2, `etapa0_seeds.refresh_eqp()`
     debe correr DESPUÉS de etapa2 (necesita los SRV_CODIGOs del staging) y
     ANTES de etapa3. El resto de las seeds pueden refrescarse en cualquier
     momento. Sugerencia para `run_pipeline.py`:

     ```
     etapa1 → etapa2 → etapa0_seeds.refresh_dim_ord/etc (si --refrescar-seeds)
                     → etapa0_seeds.refresh_eqp(srv_codigos del staging)
                     → etapa3 → etapa4
     ```

   - Para la seed 5, si por alguna razón no se puede acceder a
     `GEOREF.VM_SUMINISTROS` (permisos), dejar como fallback el `.json` de
     `docs/ejemplo_consulta_VM_GEOREFERENCIA/` con un loader que lo convierta
     a Parquet.

2. **(P0) Validador de seeds** — `src/etapa0_validar_seeds.py` (rápido, no toca
   Oracle): verifica existencia de los 6 parquet, columnas mínimas y
   `len() > 0`. Falla temprano si algo falta.

3. **(P1) Comenzar Fase 3 — Core Waterfall** — ver §3 del plan. Subdividirlo en
   tickets pequeños (3.1 Dimensiones estáticas → 3.2 dim_archivo → 3.3a Cruce A
   → 3.3b Cruce B → 3.3c Cruce C → 3.3d ensamblado + dedup + MERGE → 3.4 dims
   geo/calendario → 3.5 panel). Cada uno con su test de paridad.

4. **(P2) Tests de Etapa 1 y 2** retroactivos. Snapshot de `mapeo_codigos_master`
   y `pd_*_aux` con los archivos actuales del repo, y diff vs futuros runs.

5. **(P3) Cierre Fase 5** — flag `--contratista`, README de uso, métricas
   estandarizadas (dict `{leidas, escritas, segundos}` por etapa).

### 0.3.1 Conexión Oracle — verificada el 2026-04-24

Implementado en `src/oracle_io.py` + `scripts/test_oracle_seeds.py` + `.env`.

**Defensa en profundidad para evitar escrituras accidentales** (jefe avaló
apuntar a `PRODEBS_SEE` para lectura):

| Capa | Mecanismo                             | Detalle |
|------|---------------------------------------|---------|
| 1    | `SET TRANSACTION READ ONLY` server-side | Toda DML cae con ORA-01456. Como `autocommit=False` y nunca commiteamos, dura toda la sesión. |
| 2    | `Connection` y `Cursor` no expuestos    | La clase no tiene método para obtenerlos — no hay handle desde el cual hacer `commit()` o `execute(INSERT...)`. |
| 3    | Validador client-side de la query      | Rechaza cualquier query que no arranque con `SELECT`/`WITH` o que tenga tokens `INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/ALTER/TRUNCATE/GRANT/REVOKE/COMMIT/...` |
| 4    | API mínima: solo `read_sql(q)`         | No hay `execute()`, `cursor()`, `commit()`. |

**Volúmenes y latencias observados** (test del 2026-04-24 08:10):

| Seed                       | Filas      | Cols | t (s) | Notas                                           |
|----------------------------|-----------:|-----:|------:|-------------------------------------------------|
| dim_ord (incr. 4d)         |   167,998  |   58 |  1.31 | Filtrado por `sysdate-4`                        |
| eqp_equipos_raw (incr. 10d)|    12,112  |   13 |  3.51 | Filtrado por `sysdate-10`                       |
| dim_stk_stock_equipos      | 2,235,149  |   26 |  2.46 | Full table — `~250MB` en Parquet estimado       |
| usuarios_gral              |       952  |    7 |  0.12 | Vista                                           |
| dim_suministros_geo        | 1,197,026  |   91 |  2.06 | Tabla más ancha (91 cols)                       |
| pivot_resul_app_movil      |   284,478  |   34 | 64.80 | **Pivot pesado**, agendar refresh espaciado     |

**Convenciones**:
- Credenciales en `python-version/.env` (NO commitear). Plantilla en `.env.example`.
- Instant Client en `C:\Oracle\instantclient_23_6` (override por `OR_INSTANT_CLIENT`).
- `init_oracle_client()` se llama una sola vez por proceso (con guard).
- El nombre de columnas del pivot llega con comillas literales (`"'APP4SITIO_1'"`) — coincide con `OBS_COLS` de `config.py`. ✅

### 0.3.2 Etapa 0 (seeds) — bootstrap inicial completado el 2026-04-24

`src/etapa0_seeds.py` + `src/oracle_io.py` + `src/io_lakehouse.write_table_chunked` ya en `main`.

**Resultado del bootstrap inicial** (corrida secuencial, single-threaded):

| Seed (en `data/seed/`)        | Filas       | Cols | Tamaño Parquet | Tiempo (s) | Estrategia                                      |
|--------------------------------|------------:|-----:|---------------:|-----------:|-------------------------------------------------|
| `usuarios_gral.parquet`        |       952   |    7 | 47 KB          |       0.27 | full overwrite                                  |
| `dim_stk_stock_equipos.parquet`| 2,235,149   |   26 | 12 MB          |      57.23 | full streaming (chunked 100k)                   |
| `pivot_resul_app_movil.parquet`|   284,491   |   34 | 77 MB          |      71.0  | full overwrite                                  |
| `sigec_general.parquet`        | 1,197,026   |   91 | 153 MB         |     136.5  | full streaming (chunked 100k)                   |
| `dim_ord.parquet`              | 5,707,802   |   58 | 491 MB         |     365.4  | bootstrap (>=2025-01-01) streaming              |
| `eqp_equipos_ultimos_10.parquet`|     76,979 |  101 | 6.8 MB         |     227.8  | filtrado por 77,753 SRV del staging + pivot top-10 local |
| **Total**                      |             |      | **~740 MB**    |  **~14 min** |                                                 |

**Issues que aparecieron y se resolvieron** (registrar para no tropezar de nuevo):

1. **`ALTER SESSION SET READ ONLY` no existe en Oracle** → reemplazado por
   `SET TRANSACTION READ ONLY`. Como `autocommit=False` y nunca se commitea,
   la transacción dura toda la sesión y bloquea cualquier DML con ORA-01456.
2. **Schema drift entre chunks de `pd.read_sql(chunksize=...)`**: la misma
   columna salía `int64` en un chunk y `float64` en otro (al aparecer un NaN).
   Fix: `pa.concat_tables(promote_options="permissive")` en
   `io_lakehouse.write_table_chunked` para promover al tipo más amplio.
3. **Timestamps fuera del rango `datetime64[ns]`**: Oracle devuelve fechas
   sentinel (año 0010, año 2919, etc.) que no caben en ns. Fix:
   `_normalizar_fechas` en `etapa0_seeds.py` clipa a `[1899-12-30, 9999-12-31]`
   y fuerza resolución `[us]`. Replica el patrón de los cuadernos Fabric.
4. **Timeouts intermitentes en uno de los nodos del SCAN listener** (RAC):
   `OracleReadOnly.__enter__` ahora reintenta hasta 4 veces con backoff lineal
   (2s, 4s, 6s, 8s) cuando el error es ORA-12170 / DPY-6005.

**Correr de nuevo** (refresco incremental — útil cada N días):

```
python -m src.etapa0_seeds --seed dim_ord                # MERGE incremental por sysdate-4
python -m src.etapa0_seeds --seed eqp_equipos_ultimos_10  # rehace pivot con SRV actuales
python -m src.etapa0_seeds --seed all                     # todas las seeds
python run_pipeline.py --refrescar-seeds                  # 1+2+seeds end-to-end
```

### 0.4 Decisiones tomadas / convenciones que ya están en el código

- Bitácora de adapters → `stage/_historial_procesados.parquet` (no se lee de
  la fact, para evitar dependencia circular Etapa 2 ↔ Etapa 3).
- `merge_table` borra los `key` viejos antes del concat → semántica
  `whenMatchedUpdateAll` exacta (último gana).
- `write_table` es atómico vía `<archivo>.parquet.tmp` + `os.replace`.
- COOPLYF: `parsear_fechas_smart` mantenido byte-a-byte; hash ID_Externo
  vectorizado a `hashing.id_externo_cooplyf` (ver `src/hashing.py`).
- Adapters en modo **append** por defecto (incremental); `--reproceso` cambia a
  **overwrite** y vacía la bitácora implícita (el set queda vacío).

---

## 1. Resumen de la Arquitectura Local Propuesta

### 1.1 Principio rector

El Lakehouse de Fabric (`datos_generales.*`) se simula con un **Datalake en disco** hecho de carpetas. Cada tabla Delta pasa a ser un **archivo Parquet** (con snappy). Sharepoint (`abfss://...`) se reemplaza por carpetas de entrada locales. No se introduce ninguna base de datos real: el objetivo es desarrollo/pruebas rápido, reproducible y sin credenciales cloud.

### 1.2 Estructura de carpetas

```
python-version/
├── data/                                  # “Datalake” local
│   ├── input/                             # Reemplaza Sharepoint (raw)
│   │   ├── conectar/                      # Excel CONECTAR (pd_ce)
│   │   ├── cooplyf/                       # CSV/Excel COOPLYF
│   │   └── maestros/                      # Excels estáticos
│   │       ├── conversion_codigos_contratista_a_PD_PBI.xlsx
│   │       └── OP_MI.xlsx
│   │
│   ├── seed/                              # Dumps de tablas SIGEC/ERP
│   │   ├── dim_ord.parquet                # Ordenativos (exportado una vez)
│   │   ├── usuarios_gral.parquet
│   │   ├── eqp_equipos_ultimos_10.parquet
│   │   ├── dim_stk_stock_equipos.parquet
│   │   ├── sigec_general.parquet          # Geolocalización
│   │   └── pivot_resul_app_movil.parquet  # Observaciones app móvil
│   │
│   ├── stage/                             # Capa A — auxiliares
│   │   ├── pd_conectar_aux.parquet
│   │   ├── pd_cooplyf_aux.parquet
│   │   └── _historial_procesados.parquet  # Bitácora de archivos ya cargados
│   │
│   ├── master/                            # Capa B — maestros
│   │   ├── mapeo_codigos_master.parquet
│   │   └── reglas_cod_obs_app.parquet
│   │
│   ├── dim/                               # Capa C — dimensiones BI
│   │   ├── dim_empresa_bi.parquet
│   │   ├── dim_estado_bi.parquet
│   │   ├── dim_traza_calidad_bi.parquet
│   │   ├── dim_usuarios_bi.parquet
│   │   ├── dim_archivo_bi.parquet
│   │   ├── dim_calendario.parquet
│   │   ├── dim_suministros_geo.parquet
│   │   └── dim_img_app_pd.parquet
│   │
│   ├── gold/                              # Capa D — resultados
│   │   ├── fact_partes_diarios_full.parquet
│   │   ├── control_obs_app.parquet
│   │   ├── partes_diarios_general_conectar.parquet
│   │   ├── partes_diarios_general_cooplyf.parquet
│   │   ├── partes_diarios_rechazados_conectar.parquet
│   │   ├── partes_diarios_rechazados_cooplyf.parquet
│   │   ├── partes_diarios_para_ocr_conectar.parquet
│   │   └── partes_diarios_para_ocr_cooplyf.parquet
│   │
│   └── logs/
│       └── run_YYYYMMDD_HHMMSS.log
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Rutas, constantes, listas TRAZAS_*
│   ├── io_lakehouse.py          # read_table / write_table / merge_table
│   ├── hashing.py               # ID_PARTE_HASH (SHA256 determinista)
│   ├── etapa1_maestros.py
│   ├── etapa2_adapter_conectar.py
│   ├── etapa2_adapter_cooplyf.py
│   ├── etapa3_core.py
│   ├── etapa3_dims_geo_calendario.py
│   └── etapa4_control_obs.py
│
├── tests/
│   ├── fixtures/                # Mini-Excels de entrada
│   ├── test_etapa1_maestros.py
│   ├── test_etapa2_adapters.py
│   ├── test_etapa3_core.py      # Critico: casos de cruces A/B/C
│   └── test_etapa4_control.py   # Critico: hamming + USES
│
├── run_pipeline.py              # Orquestador (sustituye la “canalización” Fabric)
├── requirements.txt
└── README.md
```

### 1.3 Equivalencias de API (tabla de traducción)

| PySpark / Fabric                                 | Local / Pandas                                                      |
|--------------------------------------------------|---------------------------------------------------------------------|
| `spark.table("datos_generales.X")`               | `io_lakehouse.read_table("X")` → `pd.read_parquet(DATA/<capa>/X.parquet)` |
| `df.write.format("delta").mode("overwrite").saveAsTable(...)` | `io_lakehouse.write_table(df, "X", mode="overwrite")`  |
| `DeltaTable...merge(... whenMatchedUpdateAll())` | `io_lakehouse.merge_table(df_new, "X", key="ID_PARTE_HASH")` → concat + `drop_duplicates(..., keep="last")` + atomic write |
| `spark.sql("TRUNCATE TABLE X")`                  | `Path(...).unlink(missing_ok=True)` o `write_table(pd.DataFrame(), "X")` |
| `mssparkutils.fs.ls(ruta)` / `.cp(...)`          | `pathlib.Path(ruta).glob("*")` (no hace falta copiar a /tmp)       |
| `spark.createDataFrame(pdf)`                     | No aplica (ya estamos en Pandas)                                    |
| `broadcast(df)`                                  | No aplica (todo es in-memory)                                       |
| `F.col(...)`, `F.when(...).otherwise(...)`       | `np.where(...)` / `pd.Series.mask` / `df.loc[cond, "col"] = ...`    |
| `Window.partitionBy(A).orderBy(B)` + `row_number()` | `df.sort_values(...).groupby(A, sort=False).cumcount()`          |
| `F.datediff(a, b)`                               | `(a - b).dt.days`                                                   |
| `F.abs(...)`, `F.coalesce(...)`                  | `.abs()`, `Series.combine_first(...)` o `.fillna(otra)`            |
| `F.sha2(F.concat_ws("|", ...), 256)`             | `hashlib.sha256("|".join(...).encode()).hexdigest()` (vectorizado con `.agg` o numpy) |
| `monotonically_increasing_id()`                  | Evitarlo: usar `df.reset_index(drop=False).rename(...="_row_id")`    |
| `explode(split(col, ","))`                       | `df.assign(c=df.c.str.split(",")).explode("c")`                    |
| `explode(sequence(date_min, date_max))`          | `pd.date_range(min, max, freq="D")`                                |
| `regexp_replace`                                 | `Series.str.replace(regex=True)`                                   |
| `crossJoin`                                      | `pd.merge(A, B, how="cross")`                                      |
| `display(df)`                                    | `print(df.head(20))` o `IPython.display.display` si hay notebook    |

### 1.4 Orquestador local

`run_pipeline.py` sustituye a la “canalización” de Fabric. Invoca secuencialmente:

```python
# run_pipeline.py (esqueleto)
from src import (
    etapa1_maestros, etapa2_adapter_conectar, etapa2_adapter_cooplyf,
    etapa3_core, etapa3_dims_geo_calendario, etapa4_control_obs,
)

def main(modo_reproceso: bool = False):
    etapa1_maestros.run()
    etapa2_adapter_conectar.run(modo_reproceso=modo_reproceso)
    etapa2_adapter_cooplyf.run(modo_reproceso=modo_reproceso)
    etapa3_core.run()
    etapa3_dims_geo_calendario.run()
    etapa4_control_obs.run()
```

---

## 2. Fases de Migración (paso a paso)

**Principio:** migrar en orden de dependencia de datos, dejando para el final lo más sensible (Core y valoración). Cada etapa debe quedar ejecutable, testeable y producir archivos Parquet que la siguiente etapa consuma — así podemos avanzar sin tener que re-correr todo desde cero.

### FASE 0 — Scaffolding (½ día)

**Objetivo:** tener un esqueleto de proyecto funcional, sin lógica.

1. Crear la estructura de carpetas de `data/` (vacía, pero lista para recibir datos).
2. Crear `src/config.py` con **todas** las constantes migradas 1:1 desde los scripts originales:
   - `LISTA_CONTRATISTAS`, `DIAS_TOLERANCIA = 15`.
   - Listas `TRAZAS_OK`, `TRAZAS_OCR`, `TRAZAS_RECHAZO`, `TRAZAS_DESCARTE_TECNICO`, `TRAZAS_CORRECCION_MEDIDOR`.
   - `COLS_FACT` (schema canónico, **mismo orden**).
   - `VALOR_USES_COD_11 = 0.0100`.
   - `OBS_COLS` (tuplas `("'APP4SITIO_3'", "GABINETE")`, …).
   - Rutas base: `ROOT = Path(__file__).resolve().parents[1] / "data"` y subrutas derivadas.
3. Crear `src/io_lakehouse.py`:
   ```python
   # firma mínima
   def read_table(nombre: str, capa: str) -> pd.DataFrame: ...
   def write_table(df: pd.DataFrame, nombre: str, capa: str, mode: str = "overwrite") -> None: ...
   def merge_table(df_new: pd.DataFrame, nombre: str, capa: str, key: str) -> None: ...
   def table_exists(nombre: str, capa: str) -> bool: ...
   ```
   - `write_table` escribe primero a `<archivo>.parquet.tmp` y renombra → atomicidad básica en Windows.
   - `merge_table`: lee si existe, concatena, `drop_duplicates(subset=[key], keep="last")`, reescribe.
4. Crear `src/hashing.py` con un único helper vectorizado:
   ```python
   def id_parte_hash(origen, srv, fecha, medidor_colocado, cod) -> pd.Series: ...
   ```
   Reproducir **exactamente** `sha2(concat_ws("|", ORIGEN_ARCHIVO, Suministro_Final, to_date(Fecha), coalesce(medidorColocado, "NULL"), codTiposManoObra), 256)`.
5. Sembrar manualmente en `data/seed/` los dumps de tablas externas que en Fabric venían de otros pipelines (`dim_ord`, `usuarios_gral`, `eqp_equipos_ultimos_10`, `dim_stk_stock_equipos`, `sigec_general`, `pivot_resul_app_movil`). En Fabric estas las mantenía el equipo de ERP/SIGEC; aquí el usuario debe exportar un snapshot (CSV/Parquet) y dejarlo en `seed/`.

**Salida:** proyecto que corre `python run_pipeline.py` sin errores pero sin hacer nada.

---

### FASE 1 — Etapa 1: Maestros (`act_mapeo_cod_contratistas_epec.py`) (½ día)

**Por qué primero:** es el más simple, sus outputs (`mapeo_codigos_master`) son input de todos los demás.

Archivo destino: `src/etapa1_maestros.py`.

Pasos de migración:

1. **Eliminar** `from pyspark.sql...` y `spark.createDataFrame`. El script ya usa `pd.read_excel` — conservar esa lectura tal cual.
2. **Rutas**: reemplazar `/lakehouse/default/Files/...` por `DATA/input/maestros/*.xlsx`.
3. **Explode de `CODIGOS_CONTRATISTA`**:
   ```python
   df_mapeo_base = (
       df.assign(COD_CONTRATISTA_INDIVIDUAL=df["CODIGOS_CONTRATISTA"].str.split(","))
         .explode("COD_CONTRATISTA_INDIVIDUAL")
         .assign(
             COD_CONTRATISTA_INDIVIDUAL=lambda d: d["COD_CONTRATISTA_INDIVIDUAL"].str.strip(),
             FASE=lambda d: d["FASE"].str.strip(),
         )
         .rename(columns={"CODIGOS_F218": "COD_EPEC"})
         [["CONTRATISTA", "COD_CONTRATISTA_INDIVIDUAL", "FASE", "COD_EPEC", "DESCRIPCION_CODIGO"]]
         .drop_duplicates()
   )
   ```
4. **Procesar USES** (Excel OP_MI, Hoja2): la lógica ya es Pandas puro, solo quitar el `spark.createDataFrame`. Conservar `str.replace(',', '.')` y `pd.to_numeric(errors="coerce").fillna(0.0)` idénticos.
5. **Left join** por `COD_EPEC.astype(str)` ↔ `CODIGO_JOIN` con `pd.merge(..., how="left")`. Borrar columnas auxiliares al final.
6. **Guardado**: `write_table(df_mapeo_final, "mapeo_codigos_master", capa="master")`.
7. Añadir validación `count_con_use` (misma métrica impresa) y guardar también la tabla de reglas de observaciones (Celda 1 de `control_obs_pd_ce.py`) como `reglas_cod_obs_app.parquet` — es una tabla estática definida con literales, ideal para dejarla junto con los maestros.

**Test de aceptación:** el mapeo final tiene el mismo `len()`, mismas columnas y mismo `count_con_use` que en Fabric para un Excel de referencia.

---

### FASE 2 — Etapa 2: Adapters (1 día cada uno, 2 días en total)

**Por qué segundo:** genera las tablas `pd_conectar_aux` y `pd_cooplyf_aux` que el Core consumirá. Una vez migrados, podemos iterar el Core con datos reales sin depender del siguiente paso.

#### 2.A — `ingesta_adapter_CONECTAR.py` → `src/etapa2_adapter_conectar.py`

1. **Escaneo de archivos**: reemplazar `mssparkutils.fs.ls(RUTA_ORIGEN)` por:
   ```python
   archivos_detectados = [
       p for p in Path(INPUT_CONECTAR).glob("*")
       if p.suffix.lower() in {".xlsx", ".xls"} and not p.name.startswith("~")
   ]
   ```
   No hace falta copiar a `/tmp`: `pd.read_excel(path)` ya funciona directo contra el filesystem local.
2. **Historial de procesados**: reemplazar `SELECT DISTINCT ORIGEN_ARCHIVO FROM partes_diarios_general_conectar` por:
   ```python
   def obtener_historial_procesados():
       if table_exists("_historial_procesados", capa="stage"):
           return set(read_table("_historial_procesados", capa="stage")["ORIGEN_ARCHIVO"])
       return set()
   ```
   Actualizar la bitácora **al final** del run, añadiendo los nuevos nombres (upsert).
3. **`obtener_codigos_habilitados()`**: `read_table("mapeo_codigos_master", capa="master").query("CONTRATISTA=='CONECTAR'")["COD_CONTRATISTA_INDIVIDUAL"].dropna().astype(str).unique().tolist()`.
4. **`procesar_excel_conectar_robusto`**: ya está en Pandas; quitar el `mssparkutils.fs.cp` + `/tmp`. Mantener intactos: `header=2`, renombrado vía `MAPEO_COLUMNAS`, casting a texto, `pd.to_datetime(..., errors="coerce").dt.date`, `df[df['codTiposManoObra'].isin(codigos_validos)]`.
5. **Guardado**: `write_table(df_lote, "pd_conectar_aux", capa="stage", mode="overwrite")`. Inmediatamente después, upsertear la bitácora.
6. Eliminar `spark.sql("TRUNCATE TABLE...")` — ya no aplica: el Core la vaciará tras consumirla (ver Fase 3).

**Optimización sugerida** (sin romper fidelidad):
- `pd.concat([df_lote, df_temp])` en bucle es **O(n²)**. Reemplazar por acumulación en lista y un único `pd.concat(lista, ignore_index=True, copy=False)` fuera del bucle.
- Leer el Excel una sola vez y pasar `dtype=str` donde sea posible para evitar el ping-pong de tipos.

#### 2.B — `ingesta_adapter_COOPLYF.py` → `src/etapa2_adapter_cooplyf.py`

Mismo patrón que CONECTAR + estas particularidades:

1. Soporte CSV/Excel ya implementado (`leer_archivo_desde_tmp`): conservar tal cual, renombrar a `leer_archivo` y recibir directamente la ruta (sin copia a tmp).
2. `parsear_fechas_smart`: **NO TOCAR LA LÓGICA**. Mantener el criterio “el formato que produce menos NaT gana; empate → dayfirst=True”. Este fue un fix crítico, documentado en el código.
3. `ID_Externo` via SHA256 (16 chars) **determinista**: mantener **exactamente** la misma composición de campos `nombre_archivo|Suministro|Fecha|medidorColocado|codTiposManoObra`. Si se cambia el orden o se omite un campo, el MERGE del Core explotará con duplicados.
4. Historial: aquí la tabla histórica de referencia es `fact_partes_diarios_full` (gold). Usar `read_table("fact_partes_diarios_full", capa="gold")["ORIGEN_ARCHIVO"].unique()` si existe. Si no, set vacío.
   > **Nota:** en Fabric el historial se leía ya de la fact. En local, para evitar un ciclo de dependencia entre Etapa 2 y Etapa 3, conviene mantener `_historial_procesados.parquet` en `stage/` como fuente de verdad del adapter, y que el Core lo actualice cuando termine el MERGE sobre la fact.
5. `df.apply(lambda row: hashlib.sha256(...).hexdigest()[:16], axis=1)` es lento. Vectorizar usando:
   ```python
   concat = (
       nombre_archivo + "|" +
       df["Suministro"].fillna("").astype(str) + "|" +
       df["Fecha"].fillna("").astype(str) + "|" +
       df["medidorColocado"].fillna("").astype(str) + "|" +
       df["codTiposManoObra"].fillna("").astype(str)
   )
   df["ID_Externo"] = concat.map(lambda s: hashlib.sha256(s.encode()).hexdigest()[:16])
   ```
   Mantiene la **misma salida byte-a-byte** por fila, pero evita `apply(axis=1)`.

**Test de aceptación:** misma cantidad de filas post-filtro, mismas columnas, mismos hashes de ID_Externo para un archivo de referencia.

---

### FASE 3 — Etapa 3: Core Waterfall (`procesar_pd_gral_refactor.py`) (3–4 días)

**Punto crítico del proyecto.** Concentra el 80% del riesgo. Migración por sub-bloques, con tests por cruce. El diff vs. PySpark debe ser **cero** para los KPIs finales.

Archivo destino: `src/etapa3_core.py` (+ `etapa3_dims_geo_calendario.py` para Celdas 5–6).

#### 3.1 Dimensiones estáticas (Celda 2)

Triviales: diccionarios literales → `pd.DataFrame(data, columns=[...])` → `write_table(..., capa="dim")`. Incluye `dim_empresa_bi`, `dim_estado_bi`, `dim_traza_calidad_bi`.

`dim_usuarios_bi`: `read_table("usuarios_gral", capa="seed")[["USR_NUMERO","USR_NOMBRE"]].drop_duplicates(subset=["USR_NUMERO"])`. **Mantener `drop_duplicates(["USR_NUMERO"])`** (fix documentado [FIX-F] — usar `.drop_duplicates()` sobre ambas columnas replica el bug histórico).

#### 3.2 `actualizar_dim_archivo(nombres_nuevos)`

Idempotencia: cargar la dim existente, calcular `max_id`, asignar IDs secuenciales a los nuevos (ordenados por nombre, para determinismo), reescribir solo si hay nuevos. Migración 1:1 — no usa nada de Spark en realidad salvo el read/write.

#### 3.3 `ejecutar_core_para_contratista(...)` — Waterfall

Esta es la función con más carga de Spark. Plan de migración **por secciones**, manteniendo el mismo nombre de variables para facilitar la revisión diff:

**(a) Carga de entradas**

```python
df_pd    = read_table(f"pd_{sufijo}_aux", capa="stage")
df_mc    = read_table("mapeo_codigos_master", capa="master").query("CONTRATISTA==@contratista")
df_tec   = read_table("eqp_equipos_ultimos_10", capa="seed")[["SRV_CODIGO","STE_NUMERO_ULTIMO","STE_NUMERO_ANTERIOR_1"]]
df_usr   = read_table("usuarios_gral", capa="seed")[["USR_NUMERO","USR_NOMBRE","SEC_CODIGO"]]
df_fases = read_table("dim_stk_stock_equipos", capa="seed")[["ste_numero","ste_fases"]].drop_duplicates()
df_ord   = read_table("dim_ord", capa="seed")
```

Casteos: `df_tec` a float64, `df_ord["ORD_FECHA_FIN"]` → `pd.to_datetime`, etc. **Respetar los mismos nombres y casts** que el original para evitar sorpresas en joins.

**(b) `df_usr_pool`**

```python
df_usr_pool = df_usr.loc[df_usr["SEC_CODIGO"] == contratista, ["USR_NUMERO"]].drop_duplicates()
```

**(c) `df_ord_ce` y `df_ord_ce_propia` (FIX-A)**

```python
df_ord_ce = df_ord[
    (df_ord["TOR_CODIGO"] == "CE")
    & (df_ord["ORD_RESULTADO"].isin(["E","IN","D","EH","EI"]))
].rename(columns={"ORD_NUMERO":"NUMERO_ORDEN","SRV_CODIGO":"ord_suministro",
                  "USR_NUMERO_EJEC_ORD":"ID_OPERARIO_RAW"})
df_ord_ce["ord_fecha_ref"] = pd.to_datetime(df_ord_ce["ORD_FECHA_FIN"]).dt.normalize()

df_ord_ce_propia = df_ord_ce.merge(
    df_usr_pool, left_on="ID_OPERARIO_RAW", right_on="USR_NUMERO", how="inner"
).drop(columns="USR_NUMERO")
```

**(d) `df_ord_rechazo_tor` (FIX-G coalesce)**

```python
df_ord_rechazo_tor = df_ord[df_ord["TOR_CODIGO"] != "CE"].assign(
    ord_fecha_ref=lambda d: pd.to_datetime(d["ORD_FECHA_FIN"]).fillna(pd.to_datetime(d["ORD_FECHA_INICIO"])).dt.normalize()
).rename(columns={"ORD_NUMERO":"NUMERO_ORDEN","SRV_CODIGO":"ord_suministro","TOR_CODIGO":"TIPO_ORDEN_DETECTADO"})
```

**(e) `df_base` con `_row_id`**

Evitar `monotonically_increasing_id()`:
```python
df_base = df_pd.copy()
df_base["_row_id"] = np.arange(len(df_base), dtype=np.int64)
df_base["Suministro_Norm"] = pd.to_numeric(df_base["Suministro"], errors="coerce").astype("Int64")
df_base["medidorColocado"] = pd.to_numeric(df_base["medidorColocado"], errors="coerce")
df_base["medidorRetirado"] = pd.to_numeric(df_base["medidorRetirado"], errors="coerce")
df_base["Fecha_Norm"] = pd.to_datetime(df_base["Fecha"], errors="coerce").dt.normalize()
```

**(f) Cruce A, B y C — helper común**

El patrón `join + filter(|dias|<=15) + row_number.asc(dias_diff) + rank==1` aparece 3 veces. Extraer helper:

```python
def rank_one_by_dias(df_join: pd.DataFrame, key: str = "_row_id") -> pd.DataFrame:
    df_join = df_join.assign(
        dias_diff=(df_join["Fecha_Norm"] - df_join["ord_fecha_ref"]).dt.days.abs()
    )
    df_join = df_join.loc[df_join["dias_diff"] <= DIAS_TOLERANCIA]
    # equivalente a Window.partitionBy(_row_id).orderBy(dias_diff asc) → rank == 1
    df_join = df_join.sort_values([key, "dias_diff"], kind="mergesort")
    return df_join.drop_duplicates(subset=[key], keep="first")
```

> ⚠ **Usar `kind="mergesort"`** (estable). El `row_number` de Spark en caso de empate es no determinista salvo que se añadan tie-breakers; aquí el estable reproduce el comportamiento de Fabric siempre que el input tenga el mismo orden. Documentar esto en el módulo.

Cruce A: `df_base.merge(df_ord_ce_propia, left_on="Suministro_Norm", right_on="ord_suministro", how="inner")` → `rank_one_by_dias(...)` → `merge(df_tecnica, how="left")` → construir `TRAZA_CALIDAD` con `np.select` (equivalente a `F.when().when().otherwise()`):

```python
cond = [
    df["medidorColocado"].isna(),
    (df["medidorColocado"] == df["db_colocado"]) & (df["medidorRetirado"] == df["db_retirado"]),
    (df["medidorColocado"] == df["db_retirado"]) & (df["medidorRetirado"] == df["db_colocado"]),
]
choice = ["Corregido Medidor Vacio", "Original OK", "Corregido Nro EQP Invertidos"]
df["TRAZA_CALIDAD"] = np.select(cond, choice, default="Corregido Nro Medidor")
```

`df_pendientes_A` = anti-join via `~df_base["_row_id"].isin(df_resultados_A["_row_id"])`.

Cruce B y Cruce C: mismo patrón (`df_ord_rechazo_tor` y `df_tecnica` respectivamente), con los mismos fixes de `ORD_TIPO_DETECTADO` y `Corregido Sumi` / `Corregido Sumi Nro EQP`.

**(g) Ensamblado final**

`unionByName` → `pd.concat([df_A, df_B, df_C_rescate], ignore_index=True, sort=False)` y luego `df_base.merge(df_resultados, on="_row_id", how="left")`.

`coalesce(TRAZA_CALIDAD, when(...))` → `np.select` con prioridad: si ya viene, dejarla; si no, aplicar las reglas huérfano (`Sin Orden Asociada` / `Error Sumi Sin Nro Medidor` / `Error Sumi Y Nro Medidor`).

Regla de origen (`SEC_CODIGO_ORIGEN != "PROTELEM"` → `Otro Origen`): `df.loc[mask, "TRAZA_CALIDAD"] = "Otro Origen"`.

Inyección de medidores corregidos: `df.loc[df["TRAZA_CALIDAD"].isin(TRAZAS_CORRECCION_MEDIDOR), ["medidorColocado","medidorRetirado"]] = df.loc[..., ["db_colocado","db_retirado"]].values`.

**(h) Enriquecimiento y deduplicación `Repetido X Sumi`**

Fase heurística con `np.where(df["codTiposManoObra"].str.contains("01", na=False), "TRI", "MON")` como fallback de `FASE_SIGEC`.

Join con `df_mc`: la condición `(FASE_DESCUBIERTA == FASE) | (FASE == "AMBAS")` no se mapea directo a `merge`. Estrategia: duplicar las filas de `df_mc` con `FASE=="AMBAS"` (una copia para "MON" y otra para "TRI") y luego hacer `merge(on=["codTiposManoObra","FASE_DESCUBIERTA"], how="left")`. Esto replica la semántica del OR sin crear un producto cartesiano.

Window de deduplicación (`Repetido X Sumi`):
```python
df_para = df_con_precio.loc[~df_con_precio["TRAZA_CALIDAD"].isin(TRAZAS_DESCARTE_TECNICO)].copy()
df_para["prioridad_cod"] = np.where(df_para["COD_EPEC"].astype("string") != "11", 1, 0)
df_para = df_para.sort_values(
    ["Suministro_Final","prioridad_cod","Fecha","_row_id"],
    ascending=[True, False, False, False], kind="mergesort",
)
df_para["posicion"] = df_para.groupby("Suministro_Final", sort=False).cumcount() + 1
df_para.loc[df_para["posicion"] > 1, "TRAZA_CALIDAD"] = "Repetido X Sumi"
df_final = pd.concat([df_para.drop(columns=["prioridad_cod","posicion"]), df_descartes_directos], ignore_index=True)
```

**(i) Normalización al schema de `fact_partes_diarios_full`**

Seguir **exactamente** `COLS_FACT`. Crear `ID_PARTE_HASH` con el helper `hashing.id_parte_hash(...)`; `FUE_CORREGIDO = False`.

**(j) MERGE sobre la fact table**

`io_lakehouse.merge_table(df_lote_completo, "fact_partes_diarios_full", capa="gold", key="ID_PARTE_HASH")`.

El `whenMatchedUpdateAll` de Delta se emula con:
```python
def merge_table(df_new, nombre, capa, key):
    if table_exists(nombre, capa):
        df_old = read_table(nombre, capa)
        df_old = df_old.loc[~df_old[key].isin(df_new[key])]   # quita los que van a ser pisados
        out = pd.concat([df_old, df_new], ignore_index=True)
    else:
        out = df_new
    write_table(out, nombre, capa, mode="overwrite")
```

Tras el merge confirmado, vaciar los stagings (`write_table(pd.DataFrame(), "pd_<contratista>_aux", capa="stage")`) — espejo exacto del `TRUNCATE TABLE` original. **Solo después del write**, como marca el código ([H-07]).

#### 3.4 Celdas 5–6: dim_suministros_geo y dim_calendario (`etapa3_dims_geo_calendario.py`)

- **Geo**: inner join de `SRV_CODIGO` únicos de la fact con `sigec_general` (seed). `regexp_replace(",", ".")` → `Series.str.replace(",", ".", regex=False)` + `astype(float)`. `dropDuplicates(["SRV_CODIGO"])` → `drop_duplicates(subset=["SRV_CODIGO"])`.
- **Calendario**: `pd.date_range(fecha_min, fecha_max, freq="D")` → DataFrame con columnas `Date, Año, MesNro, Mes, Semana, Periodo` (usar `dt.year`, `dt.month`, `dt.strftime("%b")`, `dt.isocalendar().week`, `dt.strftime("%Y-%m")`).

#### 3.5 Celda 7: Panel de Control

Reproducir **exactamente** los print/KPIs. Cambios:
- `countDistinct("FECHA")` → `df["FECHA"].nunique()`.
- `_sum("cant_USE_unitario")` → `df["cant_USE_unitario"].sum()`.
- `groupBy(...).agg(count, sum)` → `df.groupby(...).agg(cantidad=("X","size"), total_uses=("cant_USE_unitario","sum"))`.
- Mantener los `.replace(",", ".")` de formateo numérico español.

**Tests de aceptación Fase 3 (imprescindibles):**

Deben pasar con diff **cero** vs. un snapshot tomado de Fabric para el mismo input:

- Conteo por `TRAZA_CALIDAD` idéntico.
- Conteo por `ID_ESTADO` idéntico.
- `sum(cant_USE_unitario)` con 4 decimales idéntico.
- Para una muestra aleatoria de 50 `ID_PARTE_HASH` de Fabric, esos hashes existen en local y con el mismo `TRAZA_CALIDAD`, `COD_EPEC`, `ORD_NRO`, `USR_ID`.

---

### FASE 4 — Etapa 4: Control de observaciones (`control_obs_pd_ce.py`) (2 días)

Archivo destino: `src/etapa4_control_obs.py`.

#### 4.1 Tabla de reglas

Ya generada en Fase 1 (tabla estática). Solo `read_table("reglas_cod_obs_app", capa="master")`.

#### 4.2 Pipeline completo (PASO 1 a PASO 7)

Sub-bloques con traducción directa:

1. **Carga + join con dimensiones**: una secuencia de `pd.merge(..., how="left")`. Los joins son todos sobre IDs enteros — muy rápidos. Mantener el filtro `DESC_ESTADO == "Aprobado"` al final.
2. **Anti fan-out** `dropDuplicates(["ID_PARTE_HASH"])` → `df.drop_duplicates(subset=["ID_PARTE_HASH"])`. Mantener el chequeo pre/post y el print.
3. **Normalización de observaciones a 0/1**: bucle por `OBS_COLS` con `np.where(df[col_app].notna(), 1, 0)`. Mantener los **mismos nombres** `_APP_<campo>`.
4. **`_SIN_OBS`**: `df[[f"_APP_{cr}" for _,cr in OBS_COLS]].sum(axis=1) == 0`.
5. **`VALOR_USES_ORIGEN`**: lookup via `df.merge(reglas[["COD_EPEC","VALOR_USES"]].drop_duplicates(), ...)`.
6. **PASO 4a — faltantes/excedentes vs código declarado**:
   - Join restringido contra variantes del código declarado.
   - `_REGLA_MATCH = df["_DECL_COD"].notna()` ([FIX v5]).
   - `_HAMMING_DECL = np.where(_REGLA_MATCH, suma_abs, np.nan)`.
   - `sort_values([ID_PARTE_HASH, _HAMMING_DECL, _DECL_DESC], na_position="last") + drop_duplicates(ID_PARTE_HASH)`.
   - Cálculo de `_FALTA_<cr>` y `_EXCEDE_<cr>` con la regla especial **[FIX v5]**: si `~_REGLA_MATCH`, tratar `decl_col` como `1` (todo requerido). **Esta regla NO se puede simplificar** — es la que garantiza que registros sin regla aparezcan con faltantes.
7. **PASO 4b — cross join vs TODAS las reglas**:
   ```python
   df_cross = df.merge(reglas_cross, how="cross")
   ```
   ⚠ Esto multiplica filas. Si `fact_aprobados` tiene N filas y reglas tiene 21, resulta 21·N. Para los volúmenes típicos (50k partes × 21 = 1M filas) Pandas maneja sin problema, pero **monitorear RAM** y usar `dtype` económicos (int8 para las columnas binarias).
8. **`HAMMING_DIST` global** + `sort_values([ID_PARTE_HASH, HAMMING_DIST, _REGLA_DESCRIPCION]) + drop_duplicates(ID_PARTE_HASH, keep="first")`.
9. **PASO 5 — COD_EPEC_SUGERIDO**:
   ```python
   df["COD_EPEC_SUGERIDO"]     = np.where(df["_SIN_OBS"], 11, df["_REGLA_COD_EPEC"])
   df["DESCRIPCION_SUGERIDA"]  = np.where(df["_SIN_OBS"], "Sin Observaciones Cargadas", df["_REGLA_DESCRIPCION"])
   df["VALOR_USES_OBS"]        = np.where(df["_SIN_OBS"], VALOR_USES_COD_11, df["_REGLA_VALOR_USES"])
   ```
10. **PASO 6 — Clasificación `DISCREPANCIA_CODIGO`**: `np.select` con **el mismo orden de condiciones** que Spark (importante — `np.select` aplica la primera que matchee, igual que `F.when().when()...`):
    ```python
    condlist = [
        df["VALOR_USES_ORIGEN"].isna(),
        ~df["_REGLA_MATCH"],
        df["_SIN_OBS"],
        df["CODIGO_EPEC"] == df["COD_EPEC_SUGERIDO"],
        df["DIFERENCIA_USES"] == 0,
        df["DIFERENCIA_USES"] > 0,
    ]
    choicelist = [
        "Sin Regla Definida",
        "Sin Regla para Código Declarado",
        "Sin Observaciones",
        "Sin Discrepancia",
        "Error Operativo",
        "Sobrevaloración",
    ]
    df["DISCREPANCIA_CODIGO"] = np.select(condlist, choicelist, default="Subvaloración")
    ```
11. **PASO 7 — guardado** de `control_obs_app` en `gold/`.
12. **Panel** (groupby + prints): traducción 1:1.
13. **`dim_img_app_pd`**: `split(col, " - ").getItem(0)` → `df[col].str.split(" - ", n=1).str[0]`. `regexp_replace("?alt:media", "?alt=media")` → `Series.str.replace("?alt:media", "?alt=media", regex=False)`. `left_semi join` → `df_img[df_img["ORD_NRO"].isin(df_control["ORD_NRO"])]`.

**Test de aceptación Fase 4:**
- Conteo por `DISCREPANCIA_CODIGO` **exactamente** igual al de Fabric.
- `sum(DIFERENCIA_USES_ABS)` por tipo de discrepancia con error < 1e-6.
- `HAMMING_DIST` mediano y máximo idénticos.

---

### FASE 5 — Orquestación, logging, CLI (½ día)

1. `run_pipeline.py` con `argparse`: flags `--solo-etapa {1,2,3,4}`, `--reproceso`, `--contratista {CONECTAR,COOPLYF,ambas}`.
2. Logging a `data/logs/run_<ts>.log` + consola (usar `logging.basicConfig`).
3. Cada `etapaN_*.run()` devuelve un dict de métricas (filas leídas / escritas / tiempo) para un resumen final.
4. Hacer el orquestador **fail-fast**: si Etapa 1 falla, no correr Etapa 2.

---

## 3. Puntos Críticos y Riesgos

> Lista de lugares donde la traducción PySpark → Pandas puede silenciosamente cambiar el resultado. Cada uno va acompañado de la mitigación y el test que debe pasar.

### 3.1 Determinismo en `row_number()` sobre empates

**Riesgo:** Spark's `Window.orderBy(col.asc())` no define un orden entre empates — puede devolver cualquiera de las filas empatadas. Pandas `sort_values` con `kind="mergesort"` sí es estable, pero el orden depende del orden de ingreso de las filas (que en Spark también puede variar por partición).

**Impacto:** Cruces A/B/C (empates en `dias_diff`), dedup `Repetido X Sumi` (empates en fecha), PASO 4a/4b de Etapa 4 (empates en Hamming).

**Mitigación:** en cada `sort_values` añadir **todos los tie-breakers** que el código original usa (`_DECL_DESC`, `_REGLA_DESCRIPCION`, `_row_id`) y usar `kind="mergesort"`. Documentar en el código cuáles son los tie-breakers para cada cruce.

**Test:** diff fila-a-fila para partes con `dias_diff` empatado en la muestra de referencia.

### 3.2 `monotonically_increasing_id()` no determinista

**Riesgo:** en PySpark genera IDs que dependen del número de particiones. En COOPLYF se usaba para `ID_Externo` **antes** de que se cambiara a SHA256 determinista.

**Mitigación:** COOPLYF **ya** usa SHA256 ([línea 176 del adapter]) — mantenerlo. En el Core, `_row_id` es interno (solo vive dentro de `ejecutar_core_para_contratista`), así que un `np.arange` es suficiente.

### 3.3 MERGE idempotente sobre la fact

**Riesgo:** el MERGE Delta es atómico. En local, un kill -9 entre el write temporal y el rename puede dejar la fact corrupta.

**Mitigación:** `write_table` escribe a `<archivo>.parquet.tmp` y hace `os.replace(...)` (atómico en el mismo filesystem). El merge por `ID_PARTE_HASH` se mantiene — ese hash es determinista por definición.

### 3.4 Reglas `FASE == "AMBAS"`

**Riesgo:** la condición `(FASE_DESCUBIERTA == FASE) | (FASE == "AMBAS")` no se mapea a un merge estándar. Un programador apurado la escribe como un `merge` por `codTiposManoObra` + filtro `.query(FASE in [FASE_DESCUBIERTA, "AMBAS"])`, y se rompe porque `query` no acepta variables como lista.

**Mitigación:** pre-expandir `df_mc`: duplicar las filas con `FASE == "AMBAS"` a dos filas `"MON"` y `"TRI"`, y luego merge por `(codTiposManoObra, FASE)`. Así una regla `AMBAS` machea con los dos casos sin condiciones raras.

**Test:** caso sintético con un código `"001"` de fase `"AMBAS"` y dos partes (uno MON, uno TRI) → ambos deben salir con el mismo `COD_EPEC` y `cant_USE_unitario`.

### 3.5 Coerción de tipos en joins

**Riesgo:** Spark es tolerante con la coerción implícita de tipos en joins. Pandas **no**: un merge entre `int64` y `object` puede fallar o devolver resultados parciales.

**Ejemplos en el código:**
- `Suministro_Norm` (`Int64`) ↔ `ord_suministro` (`int64`) — ojo con `NA`.
- `COD_EPEC` declarado como `long` vs. `COD_EPEC` de reglas `long` — forzado explícitamente con `.cast("long")` en el script original.
- `COD_EPEC_JOIN` vs. `CODIGO_JOIN` en Etapa 1 (ambos string) — ya está resuelto con `.astype(str).str.replace(r'\.0$', ..., regex=True)`.

**Mitigación:** al comienzo de cada módulo, centralizar casts en un bloque `prepare_types(df)`. Usar `pd.Int64` (nullable) donde Spark permite NULL en columnas numéricas.

### 3.6 Fechas con formato ambiguo (COOPLYF)

**Riesgo:** `parsear_fechas_smart` fue un fix crítico. Cualquier simplificación ("siempre `dayfirst=True`") reintroduce el bug para archivos en formato ISO.

**Mitigación:** copiar la función **byte-a-byte**. Añadir test con dos archivos (uno ISO, uno EU) que debe parsear ambos correctamente.

### 3.7 Cross join en Etapa 4

**Riesgo:** `crossJoin(broadcast(df_reglas_cross))` en Spark es barato; en Pandas es `N × 21` filas en RAM. Para 100k partes → 2.1M filas con ~30 columnas → unos 500MB.

**Mitigación:**
- Tipar las 8 columnas `_APP_<cr>` y `_REGLA_<cr>` como `int8`.
- Calcular Hamming en NumPy vectorizado (diferencia absoluta + sum over axis=1) en vez de ciclo columna por columna.
- Alternativa (si falta RAM): no cross-joinear; para cada parte calcular Hamming contra las 21 reglas vía broadcasting NumPy (`(app_matrix[:, None, :] - rule_matrix[None, :, :]).abs().sum(-1)`). Esto baja el pico de memoria pero complica el código — usar solo si 500MB es problema.

### 3.8 Lógica "Sin Regla para Código Declarado" ([FIX v5])

**Riesgo:** es una sutileza clave — cuando un código declarado no tiene reglas, el operario no puede "cumplir" ninguna regla, por lo que todas las observaciones requeridas se marcan como faltantes. Es fácil simplificarlo mal (p.ej. `np.where(_REGLA_MATCH, regla, 0)` — incorrecto, debería ser `1`).

**Mitigación:** copiar **literalmente** la expresión del script v5. Añadir un test con un `CODIGO_EPEC` inventado (no existe en reglas): el resultado debe ser `DISCREPANCIA_CODIGO == "Sin Regla para Código Declarado"` y `TOTAL_FALTANTES > 0`.

### 3.9 Dimensiones dependientes de seeds externos

**Riesgo:** `dim_ord`, `usuarios_gral`, `eqp_equipos_ultimos_10`, `dim_stk_stock_equipos`, `sigec_general`, `pivot_resul_app_movil` venían de pipelines ERP/SIGEC. Sin ellas, el Core no corre.

**Mitigación:**
- Documentar en el README cómo exportarlas a Parquet una sola vez.
- Añadir `etapa0_validar_seeds.py` que verifique existencia, columnas mínimas y ratios básicos antes de arrancar el pipeline.

### 3.10 Diferencias de zona horaria / `current_timestamp`

**Riesgo:** `F.current_timestamp()` es UTC; `datetime.now()` es local. Si los dashboards filtran por `TIMESTAMP_ETL` con una ventana de 24h puede cambiar el resultado.

**Mitigación:** usar `datetime.now(timezone.utc)` explícitamente en `TIMESTAMP_ETL` para mantener la semántica.

### 3.11 Lectura de Parquet con NaN vs. None

**Riesgo:** Pandas distingue `NaN` (floats) de `None` (objects). Tras round-trip por Parquet, columnas string con nulos vuelven como `None` y rompen comparaciones `== "X"` que antes funcionaban con NaN propagando a False.

**Mitigación:** usar `pd.read_parquet(... , dtype_backend="pyarrow")` (Pandas ≥ 2.0) o, alternativamente, normalizar al leer: `df = df.where(df.notna(), None)`.

### 3.12 Rendimiento general

- Todos los tamaños del pipeline **caben en memoria** de una máquina moderna (fact: ~50k–200k filas; reglas: 21; dim_ord: depende, pero filtrado a CE queda manejable). **No** intentar partirlo en chunks prematuramente.
- Evitar `df.apply(axis=1)` en loops internos. Usar operaciones vectorizadas.
- `pd.concat` dentro de un for-loop es O(n²): acumular en lista, concatenar una vez fuera.
- `categoricals` para columnas con cardinalidad baja (`TRAZA_CALIDAD`, `ESTADO_PROCESO`, `DESC_TRAZA`) reducen RAM y aceleran groupby.

---

## 4. Dependencias (`requirements.txt`)

```txt
# --- Core: datos + IO ---
pandas>=2.2,<3.0          # usa dtype_backend pyarrow, nullable ints, sort estable
numpy>=1.26,<3.0
pyarrow>=15.0             # motor Parquet + dtype backend nativo
openpyxl>=3.1             # lectura .xlsx (Etapa 1, Etapa 2 CONECTAR y COOPLYF)
xlrd>=2.0                 # fallback para .xls antiguos si aparecen en el input
# python-calamine>=0.2    # opcional: lector Excel ~10x más rápido que openpyxl

# --- Utilidades ---
python-dateutil>=2.9      # parseo robusto de fechas (dayfirst smart)
tqdm>=4.66                # barra de progreso opcional en bucle de archivos

# --- Logging / CLI ---
rich>=13.7                # (opcional) logging con colores, tablas
# argparse: stdlib
# pathlib: stdlib
# hashlib: stdlib
# logging: stdlib
# dataclasses: stdlib

# --- Testing ---
pytest>=8.0
pytest-cov>=4.1
pandas-stubs>=2.2         # tipos para mypy si se usa

# --- Desarrollo (no imprescindible para correr el pipeline) ---
ruff>=0.4                 # linter rápido
mypy>=1.10                # chequeo de tipos
ipykernel>=6.29           # para usar notebooks locales durante migración
# jupyterlab>=4.0         # si se quiere entorno interactivo
```

### Notas de versionado

- **Pandas 2.2+**: es el umbral recomendado para `dtype_backend="pyarrow"` estable. No volver a Pandas 1.x — muchos helpers del plan (p.ej. `Series.str.replace(regex=False)` por defecto, `dt.isocalendar().week` como DataFrame) cambiaron de firma.
- **PyArrow 15+**: necesario para escritura Parquet con tipos nullable equivalentes a los de Spark.
- **openpyxl vs. python-calamine**: si el volumen de Excels crece, `python-calamine` es ~10x más rápido y soporta los mismos archivos. Mantener `openpyxl` como default por compatibilidad.
- **Sin Spark, sin `delta-spark`, sin `notebookutils`, sin `mssparkutils`**: ninguno debe aparecer en el `requirements.txt` final. Si `pip install -r` los instala, algo quedó sin migrar.

---

## Apéndice A — Orden sugerido de implementación (gantt minimal)

| Día | Tarea                                                                 | Salida esperada |
|-----|-----------------------------------------------------------------------|-----------------|
| 1   | Fase 0: scaffolding + config + io_lakehouse + hashing + seeds         | Proyecto corre, dim/seed/ poblados |
| 1   | Fase 1: `etapa1_maestros`                                              | `master/mapeo_codigos_master.parquet` + `master/reglas_cod_obs_app.parquet` |
| 2   | Fase 2.A: adapter CONECTAR + tests                                    | `stage/pd_conectar_aux.parquet` |
| 3   | Fase 2.B: adapter COOPLYF + tests (fechas, hash determinista)         | `stage/pd_cooplyf_aux.parquet` |
| 4   | Fase 3.1–3.3: dimensiones + helpers de cruce                          | dims BI listas, helper `rank_one_by_dias` |
| 5   | Fase 3.3: Cruces A, B, C + ensamblado                                 | `gold/fact_partes_diarios_full.parquet` v0 |
| 6   | Fase 3.3: enriquecimiento + dedup + MERGE + tests de paridad          | fact table con KPIs = Fabric |
| 7   | Fase 3.4–3.5: dims geo/calendario + panel                              | dashboards-ready |
| 8   | Fase 4: control_obs + dim_img_app_pd + tests críticos                 | `gold/control_obs_app.parquet` |
| 9   | Fase 5: orquestador + logging + README de uso                         | `python run_pipeline.py` end-to-end |
| 10  | Buffer + tuning de RAM / tipos categóricos                            | Producción local lista |

---

## Apéndice B — Checklist de dependencias eliminadas

Al terminar la migración, el siguiente `grep` debe devolver **cero** resultados sobre `python-version/src/`:

```
pyspark | delta.tables | mssparkutils | notebookutils | abfss:// | /lakehouse/default | spark\. | saveAsTable | createDataFrame | F\.col | F\.when | monotonically_increasing_id
```

Si alguno aparece, la migración no está completa.
