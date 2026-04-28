# Definición de Alcance y Arquitectura — Web App de Gestión de Partes Diarios

> **Versión:** 0.1 (draft pivot)
> **Fecha:** 2026-04-27
> **Autor:** Data Engineering
> **Contexto:** El proyecto deja de ser un ETL batch (carpetas + Parquet locales orquestados por `run_pipeline.py`) y se convierte en una **aplicación transaccional con motor de procesamiento embebido**. Razón del pivot: ahora hay conexión directa a SIGEC/Oracle, lo que habilita validar/cruzar **en vivo** y exige un flujo con auditoría, autenticación y corrección manual.

---

## 0. Resumen Ejecutivo

Se construirá una **aplicación web 3 capas** (SPA + API + Worker) que reemplaza al pipeline batch sin perder su lógica de cruces (Cruce A/B/C, dedup `Repetido X Sumi`, USES, hamming). El motor Pandas existente (`etapa3_core.py`, `etapa4_control_obs.py`) se **reusará intacto**, pero se invocará desde un **job asíncrono** disparado por una subida de Excel del usuario.

Decisiones clave:
- **Persistencia transaccional** en PostgreSQL (no más Parquet en `gold/`). Parquet queda solo como cache analítico para Power BI.
- **Procesamiento desacoplado** vía cola de jobs (RQ/Celery) para que la HTTP request no bloquee con un Excel pesado.
- **SIGEC/Oracle en vivo** como sistema de referencia (lectura), con seeds materializadas localmente para joins masivos del Core (no cambia la estrategia actual del `etapa0_seeds`).
- **Auditoría inmutable** (`auditoria_cambios`) sobre toda corrección manual — soporta el flag `FUE_CORREGIDO` que hoy vive solo en la fact.

---

## 1. Alcance del Sistema y Requerimientos

### 1.1 Actores

| Actor | Permisos típicos |
|---|---|
| **Operador de carga** | Subir lotes, ver estado de su lote, descargar reporte de su lote. |
| **Auditor / Analista de calidad** | Resolver conflictos, marcar `FUE_CORREGIDO`, sobrescribir `TRAZA_CALIDAD`, anular partes. |
| **Supervisor** | Ver dashboards, exportar a Power BI / Excel, gestionar reglas de observaciones (`reglas_cod_obs_app`). |
| **Admin** | ABM de usuarios, contratistas, mapeo de códigos (`mapeo_codigos_master`), conexión Oracle. |

### 1.2 Módulo A — ABMC / Drag&Drop de Ingesta

**Objetivo:** sustituir la ejecución de `etapa2_adapter_*.py` desde CLI por una experiencia web con feedback inmediato y validación sintáctica antes de que el archivo entre al pipeline.

**Casos de uso:**

| ID | Caso de uso | Entrada | Salida / efecto |
|---|---|---|---|
| **A-01** | Subir uno o varios Excel de un contratista | Drag&drop (`.xlsx`/`.xls`/`.csv`), selección de contratista | Crea registro en `lotes_archivos` (estado=`RECIBIDO`), persiste binario en object storage, dispara job. |
| **A-02** | Validación de Formato y Esquema Estricto | (post-upload, en worker) | Control estricto de formato en la primera capa donde aterrizan los datos mediante schemas (ej. Pydantic o Pandera). Limpia strings, tipa fechas y rechaza filas con datos inválidos ANTES de pisar la BD, garantizando consistencia. Si falla → `lotes_archivos.estado=RECHAZADO_SINTAXIS`. |
| **A-03** | Detección de duplicados (idempotencia) | Hash SHA256 del archivo + `ID_Externo`/`ID_PARTE_HASH` por fila | Si ya está cargado → re-procesa sólo deltas o bloquea según política (configurable por contratista). |
| **A-04** | Re-procesar lote | `lote_id` | Marca filas como `superseded_at`, dispara nuevo run con misma traza. |
| **A-05** | Cancelar / eliminar lote en estado pendiente | `lote_id`, motivo | Soft-delete + entrada en `auditoria_cambios`. |
| **A-06** | ABM de mapeo de códigos | CRUD sobre `mapeo_codigos_master` | Cada cambio versionado (slowly changing dim tipo 2). |

**Requerimientos no funcionales:**
- Subida resiliente para Excels de hasta ~50 MB (chunked upload con `tus.io` o `multipart` simple).
- Validación sintáctica < 10 s para que el usuario no espere a ciegas.
- Procesamiento completo (Core + Control Obs) puede tardar minutos → se hace **asíncrono** con polling/SSE para el estado.

### 1.3 Módulo B — Resolución de Conflictos y Auditoría

**Objetivo:** cubrir el gap operativo más fuerte hoy: las trazas distintas a `Original OK` salen del Core y nadie las puede tocar sin re-correr el pipeline. Acá el auditor las gestiona desde la web.

**Casos de uso:**

| ID | Caso de uso | Detalle |
|---|---|---|
| **B-01** | Bandeja de partes a auditar | Filtros por `TRAZA_CALIDAD` (ej. `Sin Orden Asociada`, `Repetido X Sumi`, `Error Sumi Y Nro Medidor`), contratista, periodo, lote. |
| **B-02** | Vista detalle de un parte | Muestra raw + cruces aplicados (A/B/C) + diferencia con SIGEC + las observaciones (PASO 4a/4b) + sugerencia `COD_EPEC_SUGERIDO`. |
| **B-03** | **Cruce en vivo con SIGEC** | Botón "consultar Oracle ahora" (vía `OracleReadOnly`) para refrescar `dim_ord` solo del `SRV_CODIGO`/`ORD_NRO` en pantalla. Útil cuando la seed está desactualizada. |
| **B-04** | Edición Manual de Resultados | Auditor sobrescribe **cualquier campo** (medidores, traza, COD_EPEC, ORD_NRO, observaciones app, etc). **Regla Crítica**: el backend valida que los cambios no rompan nada re-ejecutando las reglas de negocio (recalcular USES, Hamming, cruces) sobre el nuevo input antes de guardarlo. Se persiste en `auditoria_cambios`. |
| **B-05** | Aprobar / rechazar parte | Cambia `ID_ESTADO` (Aprobado / Rechazado / OCR). Aprobado dispara recálculo de `cant_USE_unitario` si cambió COD_EPEC. |
| **B-06** | Re-asociar a una orden manualmente | El auditor pega un `ORD_NRO`. Sistema valida contra Oracle en vivo (TOR='CE', resultado válido) y lo asocia. |
| **B-07** | Visualizar bitácora de un parte | Línea de tiempo: ingresó (lote X) → cruce A matcheó → auditor Y cambió Z el día W. Inmutable. |
| **B-08** | Anular parte (soft-delete) | No borra: `estado=ANULADO`, motivo obligatorio. Sale de KPIs pero queda en auditoría. |

**Reglas duras:**
- `auditoria_cambios` es **append-only**. No se actualiza ni se borra desde la app (sólo desde superusuario DB con justificación).
- Toda corrección dispara recomputación de **dependencias**: `Control Obs` (PASO 5/6) y `cant_USE_unitario`.
- Conflictos de edición concurrente: `optimistic locking` con columna `version` en `partes_diarios_procesados`.

### 1.4 Módulo C — Dashboard y Métricas (Visualización Operativa)

**Objetivo:** Replicar y evolucionar las 6 pestañas principales del sistema actual (Power BI) para realizar el análisis operativo directamente en la web app.

**Las 6 Vistas / Pestañas:**

1. **Calidad de Datos (Overview)**
   - **Objetivo:** Mostrar la salud general del proceso de ingesta y la clasificación de los partes.
   - **KPIs:** Efectividad Calidad (%), % Aprobados Corregidos, % Rechazo.
   - **Gráficos:** Detalle mensual de aprobados (columnas), Detalles por Contratista con toggle Trabajos/USES (barras). Árbol de descomposición (Total → Estado → Traza).
   - **Tablas:** Referencia rápida del maestro de Códigos EPEC (Descripción y Valor USE).

2. **Análisis de Trabajo de Operarios**
   - **Objetivo:** Medir rendimiento y calidad a nivel ejecutante.
   - **KPIs:** Ritmo Último Mes, Ritmo USES, Tasa de Corrección (con sparklines/tendencias).
   - **Grilla:** Nombre, Tasa de Corrección (Semáforo), Cant. Ingresada/Aprobada, USES Aprobadas, Desviación USES, Índice de Asimetría, Impacto Sobre/Subvaloración. Filtro por Operario.

3. **Detalles Operativos (ABMC / Grilla Central)**
   - **Objetivo:** Vista tabular granular de todos los partes aprobados para auditoría (base del Módulo B).
   - **Filtros:** Operario, Suministro, Nro. Ordenativo, Medidor.
   - **Grilla:** Fechas, IDs, Códigos, Equipos, Actores, Estado.

4. **Mapa de Suministros**
   - **Objetivo:** Geolocalización de trabajos y detalle del cambio físico.
   - **Visuales:** Mapa interactivo. "Ficha Técnica" visual mostrando Medidor Retirado → Colocado, con metadatos clave.

5. **Observaciones (Análisis de Discrepancias)**
   - **Objetivo:** Analizar impacto económico de las diferencias entre declarado y sugerido (App).
   - **KPIs:** Índice Asimetría, Partes Controlados, Impacto Sub/Sobrevaloración.
   - **Gráficos:** Anillo de discrepancias, Columnas agrupadas (Sobre/Sub vs Contratista), Tabla de cruce exacto (Cod Origen vs Sugerido).

6. **Evolución de Observaciones**
   - **Objetivo:** Trend analysis de errores de valoración para auditoría a largo plazo.
   - **KPIs:** Mes Mayor Asimetría, Tendencia 3 meses, Diferencia Neta.
   - **Gráficos:** Evolución mensual (Líneas para %, Áreas para USES). Tabla histórica.

### 1.5 Módulo D — Reportes y Exportación

**Objetivo:** Permitir la descarga de los datos procesados a Excel para su consumo fuera del sistema.

**Casos de uso:**
- **D-01: Exportación Detallada (Full):** Excel con todos los detalles de cada parte diario (raw, ordenativo asociado, resultados de cruces, observaciones de app, geo).
- **D-02: Exportación de Relevamientos (Futuro):** Reporte enfocado a trabajo de campo (solo detalle del parte, ordenativo, observaciones y geo).

---

## 2. Propuesta de Arquitectura Técnica

### 2.1 Principios de Desarrollo y Arquitectura Limpia

El proyecto debe ser desarrollado garantizando mantenibilidad y extensibilidad:
- **Código Limpio y SOLID:** Priorizar principios SOLID durante todo el ciclo de vida del código (ej. Inyección de dependencias, Responsabilidad única en validadores).
- **Arquitectura en Capas:** Estructura clara separando Controladores (API), Casos de Uso (Servicios de negocio), Repositorios (Persistencia), y el Motor Analítico (Core).
- **Documentación Continua:** Se creará y mantendrá una carpeta específica (ej. `docs/webapp/`) para documentar progreso, decisiones arquitectónicas y endpoints (Swagger), evitando perder contexto entre jornadas laborales.

### 2.2 Stack tecnológico

| Capa | Elección | Razón |
|---|---|---|
| **Frontend SPA** | **React 18 + TypeScript + Vite + TanStack Query + shadcn/ui (Tailwind)** | Reactivo, minimalista, ecosistema maduro para data-grids virtualizados (TanStack Table) — clave para la bandeja de auditoría con miles de filas. |
| **API HTTP** | **FastAPI (Python 3.12)** | Mismo lenguaje que el motor Pandas → reuso 1:1 de `etapa3_core.py` y `etapa4_control_obs.py` sin re-escribir. Tipado fuerte (Pydantic v2) y OpenAPI gratis. |
| **Worker / Cola** | **RQ + Redis** (alternativa: Celery si aparecen workflows con cadenas complejas) | RQ es mucho más simple que Celery, encaja con el volumen previsto (decenas de jobs/día). Redis ya sirve además para cache y pub/sub del estado del job. |
| **Base transaccional** | **PostgreSQL 16** | JSONB para payloads raw del Excel, particionamiento nativo por fecha del parte, full-text search para libre búsqueda en observaciones. |
| **Object storage** | **MinIO** (compat S3) en local; migrable a S3/Azure Blob si se cloudifica | Para guardar los Excel originales y reportes de validación, fuera de Postgres. |
| **Acceso Oracle** | **`src/oracle_io.OracleReadOnly`** existente (read-only de 4 capas) | Ya validado, no se toca. La API expone endpoints que internamente usan esta clase. |
| **Cache analítico** | **Parquet en `data/gold/`** (vía `io_lakehouse.write_table`) | Power BI sigue consumiendo de acá. Se regenera con un job nocturno desde Postgres. |
| **Auth** | **OAuth2 / OIDC** contra el IdP corporativo (si existe) o **JWT local** con roles (`operador`, `auditor`, `supervisor`, `admin`). | RBAC sobre los casos de uso del §1. |
| **Observabilidad** | Logging estructurado (`structlog` + JSON), Prometheus metrics, Sentry para errores | Necesario para ver por qué un job de procesamiento se trabó. |
| **Despliegue** | Docker Compose en local (dev y on-prem inicial). Migración futura a K8s opcional. | El usuario está en entorno local Windows; Docker Desktop o WSL2 es lo más simple. |

### 2.2 Diagrama lógico

```
┌──────────────┐       HTTPS       ┌─────────────────┐
│  React SPA   │ ◄───────────────► │   FastAPI API   │
│  (Vite)      │   JSON / SSE      │   (uvicorn)     │
└──────────────┘                   └────────┬────────┘
                                            │
                          ┌─────────────────┼──────────────────────┐
                          │                 │                      │
                          ▼                 ▼                      ▼
                  ┌──────────────┐  ┌───────────────┐    ┌──────────────────┐
                  │ PostgreSQL   │  │ Redis (RQ +   │    │ MinIO            │
                  │ (transacc.)  │  │ pub/sub)      │    │ (Excel raw +     │
                  └──────────────┘  └───────┬───────┘    │  reportes)       │
                          ▲                 │            └────────▲─────────┘
                          │                 ▼                     │
                          │         ┌────────────────┐            │
                          │         │ Worker Python  │────────────┘
                          │         │ (Pandas Core + │
                          └─────────│  Control Obs)  │
                                    └────┬───────────┘
                                         │ READ-ONLY
                                         ▼
                                ┌─────────────────┐
                                │ Oracle SIGEC    │
                                │ (PRODEBS_SEE)   │
                                └─────────────────┘
```

### 2.3 Comunicación API ↔ motor de validación

**Patrón:** *Request/Response* para acciones síncronas; *Job + Polling/SSE* para procesamiento pesado.

**Flujo de una subida típica (Caso A-01 → Auditoría):**

1. SPA hace `POST /api/lotes` con multipart (archivo + contratista). API persiste el binario en MinIO, crea fila en `lotes_archivos` con `estado=RECIBIDO` y devuelve `lote_id` + `job_id`.
2. API encola en Redis: `enqueue(procesar_lote, lote_id)`.
3. SPA suscribe SSE `GET /api/lotes/{lote_id}/stream` (o polling cada 2s sobre `/api/lotes/{lote_id}`).
4. Worker:
   - Lee binario de MinIO.
   - **Validación sintáctica** (módulo `validacion_sintactica.py`) → si falla, persiste detalle y termina.
   - **Stage**: invoca la lógica refactorizada de `etapa2_adapter_*.py` pero escribiendo a `partes_diarios_raw` (tabla, no Parquet).
   - **Core**: ejecuta `ejecutar_core_para_contratista(...)` (de `etapa3_core.py`) sobre el subset del lote. Las seeds (`dim_ord`, `eqp_equipos_ultimos_10`, etc.) se siguen leyendo de Parquet en `data/seed/` (no cambian en el día a día — refresh por job programado).
   - **Persiste** filas en `partes_diarios_procesados` (NO `merge_table` a Parquet — se hace `INSERT ... ON CONFLICT (id_parte_hash) DO UPDATE` en Postgres).
   - **Control Obs**: corre `etapa4_control_obs.run(lote_id)`.
   - Publica eventos a Redis pub/sub que el SSE retransmite al SPA (`stage:ok`, `core:ok`, `obs:ok`, `done`).
5. SPA recibe `done`, redirige a la bandeja del Módulo B con filtro `lote_id=<id>`.

**Punto importante:** el motor Pandas **no se re-escribe**. Se refactoriza para:
- Recibir un DataFrame de entrada en vez de leer un Parquet (parámetro inyectado).
- Devolver un DataFrame de salida en vez de hacer `merge_table`.
- La persistencia a Postgres queda en el worker (capa de adaptación), no dentro del Core. Esto preserva la testabilidad y la "paridad numérica" exigida por `CLAUDE.md`.

---

## 3. Modelo de Datos Transaccional (MER)

### 3.1 Principios

- **Separación raw / procesado:** preservamos el dato como vino del Excel (`partes_diarios_raw`) y como quedó después del Core (`partes_diarios_procesados`). Permite re-procesar sin re-subir.
- **Trazabilidad inmutable:** todo cambio post-Core va a `auditoria_cambios`. La fila procesada siempre lleva `version` y `updated_by`.
- **FK lógicas a SIGEC, no físicas:** `ord_nro`, `srv_codigo`, `usr_id` son enteros sin FK formal (Oracle es otra base). La validez se verifica en vivo o contra seeds.
- **Slowly Changing Dim 2** para el mapeo de códigos: cambios en `mapeo_codigos_master` no rompen la auditoría histórica.

### 3.2 Diagrama entidad–relación (lógico)

```
┌────────────────────┐       ┌────────────────────────┐
│  contratistas      │       │  usuarios_app          │
│  (catálogo)        │       │  (auth + roles)        │
└─────────┬──────────┘       └────────────┬───────────┘
          │ 1                             │ 1
          │                               │
          │ N                             │ N
┌─────────▼──────────┐       ┌────────────▼───────────┐
│  lotes_archivos    │◄──────│  auditoria_cambios     │
│  (1 upload)        │  1..N │  (append-only log)     │
└─────────┬──────────┘       └────────────▲───────────┘
          │ 1                             │
          │                               │ 0..N
          │ N                             │
┌─────────▼──────────────┐  1  ┌──────────┴────────────┐
│  partes_diarios_raw    │◄───►│ partes_diarios_       │
│  (snapshot del Excel)  │  1  │ procesados (post-Core)│
└────────────────────────┘     └──────────┬────────────┘
                                          │ N
                                          │
                                          │ 1
                               ┌──────────▼────────────┐
                               │ control_obs_resultado │
                               │ (post-PASO 6)         │
                               └───────────────────────┘

   ┌──────────────────────┐    ┌──────────────────────┐
   │ mapeo_codigos_master │    │ reglas_cod_obs_app   │
   │ (versionado SCD2)    │    │ (versionado SCD2)    │
   └──────────────────────┘    └──────────────────────┘

   ┌──────────────────────┐    Seeds materializadas (parquet) → no en Postgres
   │ seed_refresh_log     │    (dim_ord, eqp_equipos_ultimos_10, sigec_general,
   │ (estado de cada seed)│     dim_stk_stock_equipos, usuarios_gral, pivot_resul_app_movil)
   └──────────────────────┘
```

### 3.3 Tablas core (DDL resumida)

```sql
-- ─────────────── Catálogos ───────────────
CREATE TABLE contratistas (
    contratista_id      SMALLSERIAL PRIMARY KEY,
    codigo              VARCHAR(20) UNIQUE NOT NULL,   -- 'CONECTAR', 'COOPLYF'
    nombre              TEXT NOT NULL,
    activo              BOOLEAN DEFAULT TRUE
);

CREATE TABLE usuarios_app (
    usuario_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               CITEXT UNIQUE NOT NULL,
    nombre              TEXT NOT NULL,
    rol                 VARCHAR(20) NOT NULL CHECK (rol IN ('operador','auditor','supervisor','admin')),
    activo              BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- ─────────────── Ingesta ───────────────
CREATE TABLE lotes_archivos (
    lote_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contratista_id      SMALLINT REFERENCES contratistas,
    nombre_archivo      TEXT NOT NULL,
    sha256_archivo      CHAR(64) NOT NULL,                 -- idempotencia
    storage_uri         TEXT NOT NULL,                     -- s3://bucket/lote/<id>.xlsx
    bytes               BIGINT,
    subido_por          UUID REFERENCES usuarios_app,
    subido_at           TIMESTAMPTZ DEFAULT now(),
    estado              VARCHAR(30) NOT NULL,
    -- RECIBIDO | VALIDANDO | RECHAZADO_SINTAXIS | EN_STAGE | EN_CORE | EN_OBS | OK | ERROR_SISTEMA | ANULADO
    error_detalle       JSONB,
    job_id              TEXT,                              -- RQ job id
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    metricas            JSONB                              -- {filas_leidas, filas_ok, ...}
);
CREATE INDEX ix_lotes_estado ON lotes_archivos(estado);
CREATE INDEX ix_lotes_contratista_subido ON lotes_archivos(contratista_id, subido_at DESC);

-- ─────────────── Raw (snapshot del Excel) ───────────────
CREATE TABLE partes_diarios_raw (
    raw_id              BIGSERIAL PRIMARY KEY,
    lote_id             UUID NOT NULL REFERENCES lotes_archivos ON DELETE CASCADE,
    fila_excel          INT NOT NULL,                       -- nº de fila para mapear back al archivo
    payload             JSONB NOT NULL,                     -- todas las columnas tal cual salieron del Excel
    id_externo          CHAR(16),                           -- COOPLYF
    id_parte_hash       CHAR(64),                           -- calculado en stage si ya hay datos suficientes
    valido_sintactico   BOOLEAN NOT NULL,
    errores_sintacticos JSONB,
    UNIQUE (lote_id, fila_excel)
);
CREATE INDEX ix_raw_id_parte_hash ON partes_diarios_raw(id_parte_hash) WHERE id_parte_hash IS NOT NULL;

-- ─────────────── Procesado (post-Core) ───────────────
-- Una fila por ID_PARTE_HASH. Es el equivalente transaccional de fact_partes_diarios_full.
CREATE TABLE partes_diarios_procesados (
    id_parte_hash       CHAR(64) PRIMARY KEY,
    raw_id              BIGINT NOT NULL REFERENCES partes_diarios_raw,
    lote_id             UUID NOT NULL REFERENCES lotes_archivos,
    contratista_id      SMALLINT NOT NULL REFERENCES contratistas,

    -- Identificadores SIGEC (sin FK física a Oracle)
    srv_codigo          BIGINT,
    ord_nro             BIGINT,
    usr_id              BIGINT,
    sec_codigo_origen   VARCHAR(20),

    -- Negocio
    fecha               DATE NOT NULL,
    nro_eqp_colocado    BIGINT,
    nro_eqp_retirado    BIGINT,
    codigo_contratista  VARCHAR(50),
    codigo_epec         VARCHAR(20),
    cant_use_unitario   NUMERIC(12,4),
    traza_calidad       VARCHAR(60) NOT NULL,
    ord_tipo_detectado  VARCHAR(10),
    fase                VARCHAR(10),
    id_estado           SMALLINT NOT NULL,                  -- FK lógica a dim_estado
    suministro_raw      TEXT,

    -- Auditoría / corrección manual
    fue_corregido       BOOLEAN NOT NULL DEFAULT FALSE,
    corregido_por       UUID REFERENCES usuarios_app,
    corregido_at        TIMESTAMPTZ,
    motivo_correccion   TEXT,

    -- Versionado optimista
    version             INT NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at       TIMESTAMPTZ,                        -- soft delete por re-procesamiento
    superseded_by_lote  UUID REFERENCES lotes_archivos
) PARTITION BY RANGE (fecha);

-- Particionamiento mensual; Postgres maneja >100M sin problema con esto
CREATE TABLE partes_diarios_procesados_2026_04 PARTITION OF partes_diarios_procesados
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX ix_pdp_traza ON partes_diarios_procesados(traza_calidad) WHERE superseded_at IS NULL;
CREATE INDEX ix_pdp_lote ON partes_diarios_procesados(lote_id);
CREATE INDEX ix_pdp_srv_fecha ON partes_diarios_procesados(srv_codigo, fecha);
CREATE INDEX ix_pdp_ord_nro ON partes_diarios_procesados(ord_nro) WHERE ord_nro IS NOT NULL;

-- ─────────────── Control de Observaciones ───────────────
CREATE TABLE control_obs_resultado (
    id_parte_hash       CHAR(64) PRIMARY KEY REFERENCES partes_diarios_procesados,
    sin_obs             BOOLEAN NOT NULL,
    cod_epec_sugerido   VARCHAR(20),
    descripcion_sugerida TEXT,
    valor_uses_origen   NUMERIC(12,4),
    valor_uses_obs      NUMERIC(12,4),
    diferencia_uses     NUMERIC(12,4),
    hamming_dist        SMALLINT,
    discrepancia_codigo VARCHAR(40),
    detalle_obs         JSONB,                              -- _APP_GABINETE, _APP_..., faltantes/excedentes
    calculado_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_cor_discrepancia ON control_obs_resultado(discrepancia_codigo);

-- ─────────────── Auditoría inmutable ───────────────
CREATE TABLE auditoria_cambios (
    auditoria_id        BIGSERIAL PRIMARY KEY,
    entidad             VARCHAR(40) NOT NULL,               -- 'partes_diarios_procesados' | 'lotes_archivos' | 'mapeo_codigos_master' | ...
    entidad_id          TEXT NOT NULL,                      -- id_parte_hash, lote_id, ...
    accion              VARCHAR(20) NOT NULL,               -- CREATE | UPDATE | ANULAR | APROBAR | RECHAZAR | REPROCESAR
    campo               VARCHAR(50),                        -- columna afectada (NULL si es change-set entero)
    valor_anterior      JSONB,
    valor_nuevo         JSONB,
    motivo              TEXT,
    usuario_id          UUID REFERENCES usuarios_app,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id          UUID                                 -- correlación con el request HTTP
);
CREATE INDEX ix_aud_entidad ON auditoria_cambios(entidad, entidad_id, ts DESC);

-- BLOQUEO: sin UPDATE/DELETE permitido (sólo el rol superuser puede)
REVOKE UPDATE, DELETE ON auditoria_cambios FROM app_user;

-- ─────────────── Maestros (SCD2) ───────────────
CREATE TABLE mapeo_codigos_master (
    mapeo_id            BIGSERIAL PRIMARY KEY,
    contratista_id      SMALLINT NOT NULL REFERENCES contratistas,
    cod_contratista     VARCHAR(50) NOT NULL,
    fase                VARCHAR(10) NOT NULL,               -- MON | TRI | AMBAS
    cod_epec            VARCHAR(20) NOT NULL,
    descripcion         TEXT,
    valor_uses          NUMERIC(12,4),
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to            TIMESTAMPTZ,                        -- NULL = vigente
    creado_por          UUID REFERENCES usuarios_app
);
CREATE UNIQUE INDEX ux_mapeo_vigente ON mapeo_codigos_master(contratista_id, cod_contratista, fase)
    WHERE valid_to IS NULL;

CREATE TABLE reglas_cod_obs_app ( /* análoga a la anterior, con SCD2 */ );

-- ─────────────── Estado de seeds ───────────────
CREATE TABLE seed_refresh_log (
    seed_nombre         VARCHAR(60) PRIMARY KEY,            -- 'dim_ord', 'eqp_equipos_ultimos_10', ...
    last_refresh_at     TIMESTAMPTZ,
    filas               BIGINT,
    duracion_seg        NUMERIC(10,2),
    bytes_parquet       BIGINT,
    estrategia          VARCHAR(40)                         -- 'bootstrap', 'incremental', 'full'
);
```

### 3.4 Trazabilidad hacia SIGEC

- **`srv_codigo`, `ord_nro`, `usr_id`**: enteros que mapean al canónico documentado en el plan (`SRV_CODIGO`, `ORD_NUMERO`, `USR_NUMERO`).
- **No FK física** porque Oracle es otra base. La integridad se valida:
  - **En batch:** join contra seeds materializadas (`dim_ord`, `usuarios_gral`).
  - **En vivo (Caso B-03):** llamada puntual a `OracleReadOnly.read_sql(...)` desde la API cuando el auditor lo solicita.
- **Geolocalización:** `seed/sigec_general.parquet` se sigue usando para `LATITUD/LONGITUD/CALLE/DPTO`. El dashboard puede mostrarla on-demand (no se duplica en Postgres).

### 3.5 Cómo conviven Postgres y Parquet

| Tipo de uso | Storage | Refresh |
|---|---|---|
| OLTP (lotes, auditoría, correcciones) | **Postgres** | en vivo |
| Lookups masivos del Core (`dim_ord`, `eqp_*`) | **Parquet en `data/seed/`** | job de seeds programado (diario `dim_ord`, semanal `pivot_resul_app_movil`) |
| Consumo Power BI | **Parquet en `data/gold/`** materializado nocturnamente desde Postgres | nightly job |
| Cache de vistas pesadas | Materialized views en Postgres | refresh on-demand |

Esto evita el peor de los mundos: cargar 2.2M filas de stock_equipos a Postgres innecesariamente, o quedarnos atados a un Parquet inmutable cuando el negocio exige correcciones diarias.

---

## 4. Roadmap de Implementación (MVP)

> Cada fase es un milestone entregable y demoable. La fase 1 ya da valor (web upload + procesamiento básico), aún sin auditoría avanzada.

### Fase 1 — *MVP funcional end-to-end* (3–4 semanas)

**Objetivo:** un operador sube un Excel desde la web y al final ve filas procesadas en una tabla. Demo-able.

- [ ] Scaffold proyecto: monorepo `apps/api` (FastAPI) + `apps/web` (Vite/React) + `apps/worker`. Docker Compose con Postgres + Redis + MinIO.
- [ ] Migraciones iniciales (Alembic): `contratistas`, `usuarios_app`, `lotes_archivos`, `partes_diarios_raw`, `partes_diarios_procesados`, `auditoria_cambios`.
- [ ] **Refactor del motor:** envolver `etapa3_core.ejecutar_core_para_contratista` y `etapa4_control_obs.run` para que reciban DataFrames y devuelvan DataFrames (en vez de leer/escribir Parquet). Mantener el Parquet sólo para seeds.
- [ ] Endpoint `POST /api/lotes` + worker RQ que ejecute el flujo completo (validación sintáctica → stage → Core → Control Obs → persistencia Postgres).
- [ ] SPA: pantalla drag&drop, lista de lotes con polling de estado, vista detalle del lote (lista de partes con `traza_calidad`).
- [ ] Auth básica JWT con dos roles (`operador`, `admin`).
- [ ] **Tests de paridad** sobre un lote de referencia: el resultado en Postgres debe dar los mismos KPIs que la corrida batch (mismo conteo por `TRAZA_CALIDAD`, mismo `sum(cant_USE_unitario)` con 4 decimales).

**Criterio de salida:** un Excel real procesa end-to-end vía web, paridad numérica con `run_pipeline.py` actual.

### Fase 2 — *Resolución de conflictos y auditoría* (3 semanas)

**Objetivo:** el auditor puede corregir partes desde la web y todo cambio queda registrado.

- [ ] Bandeja de auditoría (Módulo B): tabla virtualizada con filtros, búsqueda y paginación server-side.
- [ ] Vista detalle de parte con timeline de cambios (`auditoria_cambios`).
- [ ] Endpoints de corrección: `PATCH /api/partes/{id}` con motivo obligatorio + optimistic locking (`If-Match` con `version`).
- [ ] Recálculo automático de `cant_USE_unitario` y `control_obs_resultado` cuando cambia `codigo_epec`.
- [ ] Cruce en vivo con SIGEC (Caso B-03): endpoint `GET /api/sigec/orden/{ord_nro}` que usa `OracleReadOnly`.
- [ ] Acciones: aprobar / rechazar / anular / re-asociar a orden.
- [ ] Roles `auditor` y `supervisor`, permisos finos en endpoints.
- [ ] SCD2 para `mapeo_codigos_master` con UI de ABM (versionado).

**Criterio de salida:** un auditor corrige 10 partes con distintas trazas, se ve la línea de tiempo, los KPIs reflejan los cambios y nada se pierde.

### Fase 3 — *Dashboards de calidad y exportación* (2 semanas)

**Objetivo:** vista operativa de KPIs + cierre del loop con Power BI.

- [ ] Dashboard KPIs (Módulo C): mosaicos C-01 a C-08, todos drill-able a la bandeja.
- [ ] Materialización nocturna `partes_diarios_procesados` → `data/gold/fact_partes_diarios_full.parquet` (job RQ programado con `rq-scheduler`).
- [ ] Endpoint `GET /api/lotes/{id}/reporte` que devuelve un Excel con el detalle del lote (incluye trazabilidad `FUE_CORREGIDO`).
- [ ] SLA de auditoría: alertas si hay partes pendientes >48h.
- [ ] Salud de seeds (C-07): leer `seed_refresh_log` y mostrar antigüedad.

**Criterio de salida:** un supervisor entra al dashboard, ve la salud del día, baja a un parte concreto desde un KPI y lo audita en 3 clics.

### Fase 4 — *Endurecimiento y operaciones* (2 semanas)

**Objetivo:** dejar el sistema apto para producción on-prem.

- [ ] Observabilidad: Prometheus + Grafana, alertas (cola RQ trabada, conexión Oracle caída, seeds vencidas).
- [ ] OAuth2/OIDC contra IdP corporativo (si aplica). Sino, gestión de usuarios/passwords con bcrypt + reset por email.
- [ ] Refresh automático de seeds (RQ Scheduler): `dim_ord` cada 4 días, `eqp_equipos_ultimos_10` post-stage de cada lote, `pivot_resul_app_movil` semanal.
- [ ] Backups Postgres (`pg_basebackup` + WAL archiving) + retención MinIO.
- [ ] Particionamiento automático de `partes_diarios_procesados` (creación mensual con `pg_partman`).
- [ ] Tests E2E (Playwright) sobre los flujos críticos del Módulo A y B.
- [ ] Documentación de runbook: cómo re-procesar un lote, qué hacer si Oracle no responde, cómo auditar un cambio sospechoso.
- [ ] Migración de datos histórica: cargar a Postgres lo que hoy está en `data/gold/fact_partes_diarios_full.parquet` con `id_estado`/`fue_corregido` defaults.

**Criterio de salida:** sistema corriendo en el servidor on-prem objetivo, con monitoreo, backups y un corte de luz no rompe datos.

---

## 5. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Pérdida de paridad numérica** al refactorizar el Core para recibir DataFrame en vez de leer Parquet | Tests de paridad de Fase 1 son no-negociables. Los snapshots `tests/fixtures/kpis_snapshot.json` pasan antes y después del refactor. |
| **Performance del Core con un solo lote** (era diseñado para procesar todo el contratista) | Profilar. Si es lento porque carga seeds enteras para 200 partes: cachear seeds en memoria del worker (lifetime > 1 job). |
| **Concurrencia en correcciones** | Optimistic locking con `version`. Si dos auditores chocan, el segundo recibe 409 y refresca. |
| **Cambio frecuente de `mapeo_codigos_master`** invalida partes ya procesados | SCD2 + endpoint "re-procesar lote con mapeo vigente al día X" (consulta histórica con `valid_from <= X < valid_to`). |
| **Oracle caído** | Toda llamada en vivo está envuelta en circuit-breaker; el cruce en vivo (B-03) degrada a "no disponible" pero el batch sigue funcionando con seeds. |
| **Tamaño de auditoría** crece sin techo | Particionamiento por `ts` en `auditoria_cambios` y archivado anual a object storage en frío. |

---

## 6. Decisiones Pendientes

Antes de arrancar, conviene cerrar:

1. **IdP corporativo**: ¿hay Azure AD / Keycloak disponible o vamos JWT local?
2. **Despliegue**: ¿servidor Windows on-prem (entorno actual) o Linux? Impacta MinIO, Docker, paths.
3. **Política de re-procesamiento**: ¿re-subir un Excel idéntico (mismo SHA256) bloquea o re-procesa silencioso?
4. **Acceso del operador a Oracle en vivo (B-03)**: ¿solo `auditor`/`supervisor`, o también el operador para auto-diagnóstico?
5. **Retención**: ¿cuánto tiempo guardamos `partes_diarios_raw` (los Excel originales pueden ocupar)?

---

**Próximo paso recomendado:** revisar este documento, marcar los puntos del §6 y, al cerrar, abrir tickets para Fase 1 (scaffold + refactor del motor + endpoint POST `/lotes`). El refactor del motor es el camino crítico — es donde más se juega la paridad y donde menos margen de error hay.

