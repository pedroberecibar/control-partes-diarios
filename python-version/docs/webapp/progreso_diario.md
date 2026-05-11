# Bitácora de Progreso Diario — Web App

Este documento mantiene el contexto de los avances diarios en el desarrollo de la aplicación web, para evitar pérdida de información entre jornadas laborales.

## Jornada: 2026-04-27
**Desarrollador:** Data Engineering Team
**Objetivo del día:** Finalizar el motor analítico de partes diarios en Python local e iniciar el scaffolding de la arquitectura Web (FastAPI + React).

### Hechos
- **Motor Analítico**: Se implementó con éxito la regla de rechazo para ordenativos en estado `IN` ("Informado - No Ejecutado") en la Etapa 3.
- **Motor Analítico**: Se reemplazó la traza de deduplicación a `"Informados con ORD-SUMI aprobado"`.
- **Tests**: Se regeneraron los snapshots y el motor local pasa los 20 tests E2E de paridad numérica.
- **Documentación**: Se generó el documento `descripcion_detallada_flujo.md` con el funcionamiento end-to-end.
- **Arquitectura**: Se finalizó la definición del alcance (`definicion_alcance_arquitectura_webapp_pd.md`), incorporando edición full de partes, validaciones estrictas en la ingesta, 6 dashboards de BI y módulo de exportaciones Excel. Se definió la aplicación estricta de principios SOLID y Arquitectura Limpia.
- **Scaffolding Backend**: Se instalaron `fastapi` y `uvicorn`.
- **Scaffolding Backend**: Se crearon las carpetas `api/routers/`, `api/services/`, `api/schemas/` y el archivo `api/main.py` con los endpoints iniciales de health check.
- **Base de Datos (ORM)**: Se configuró `SQLAlchemy` con `SQLite` para el desarrollo inicial (como contingencia por restricciones de permisos locales).
- **Modelos ORM**: Se crearon las entidades base (`UsuarioApp`, `Contratista`, `LoteArchivo`) y las entidades de dominio transaccional (`ParteDiarioRaw`, `ParteDiarioProcesado`, `AuditoriaCambio`).
- **Migraciones**: Se configuró `Alembic` y se ejecutó la migración inicial, creando físicamente el archivo `data/db/webapp_pd.db` con todas las tablas.
- **Scaffolding Frontend**: Se postergó temporalmente la creación del proyecto Vite/React debido a la ausencia de Node.js en el entorno corporativo del usuario.

### Estado Actual (Fin de Jornada)
El desarrollo del backend local (Pandas) está 100% migrado, validado (tests pasando) y estabilizado. Se ha establecido exitosamente la arquitectura base de la Web App:
- **Backend**: Proyecto FastAPI inicializado con estructura en capas (`routers`, `services`, `schemas`, `models`).
- **Base de Datos**: ORM SQLAlchemy configurado sobre SQLite (como contingencia local) con migraciones de Alembic al día (`webapp_pd.db` generado con todas las tablas).

### Próximos Pasos (Hoja de Ruta para Mañana)
1. **Construir Endpoints Básicos (Routers & Schemas)**:
   - Crear los DTOs en `api/schemas/` usando Pydantic para validar la entrada (lotes, partes, etc).
   - Desarrollar las primeras rutas en `api/routers/lotes.py` y `api/routers/partes.py` para simular la ingesta y guardado de datos.
2. **Integrar Motor Analítico (Services)**:
   - Enlazar la subida de un Excel desde la API (FastAPI) hacia la ejecución de `src/etapa3_core.py` y `src/etapa4_control_obs.py`.
   - Modificar las salidas del motor analítico para que guarden sus resultados en `ParteDiarioProcesado` de SQLite en lugar de generar archivos Parquet directamente.
3. **Frontend Blockers**:
   - Definir estrategia para el Frontend (React/Vite). Dado que Node.js no está instalado en el entorno corporativo, debemos evaluar si se puede solicitar instalación a IT, descargar un binario portable, o si serviremos vistas estáticas generadas desde otro entorno.

## [Actualizaci?n 2026-04-28] - Worker y Refactor In-Memory Finalizado

### Implementaciones
*   **Refactorizaci?n Segura**: Se modificaron `etapa3_core.py` y `etapa4_control_obs.py` para aceptar un `DataFrame` en memoria (`df_pd_input`), aislando el I/O sin romper la interfaz CLI que guarda a Parquet. 
*   **Worker As?ncrono (`api/services/worker.py`)**:
    *   Orquesta el procesamiento de punta a punta: lee Excel de `lote`, aplica limpieza mediante los adapters originales (`etapa2_adapter_conectar`, etc.), e invoca la l?gica de E3 y E4 puramente en memoria.
    *   Mapea los resultados anal?ticos a la tabla `partes_diarios_procesados` (`crear_partes_desde_df`).
    *   Mantiene los `raw_data` originales de cada fila en `partes_diarios_raw` por prop?sitos de trazabilidad.
*   **Integraci?n en API**: `POST /api/v1/lotes` lanza `procesar_lote_en_background` en FastAPI con `BackgroundTasks`.

### Validaciones
*   Los 20 Tests de la suite (`pytest tests/`) ejecutados y pasando. El refactor es determinista y no rompi? la l?gica del motor anal?tico.

### Pr?ximos Pasos Bloqueantes / Desaf?os
*   **Desarrollo del Frontend**: Teniendo el backend de la API y el motor 100% operativos, el siguiente paso seg?n el plan MVP es levantar el Frontend. Estamos limitados por la falta de Node.js nativo (Windows throw `CommandNotFoundException` para `node -v`). Necesitaremos definir un enfoque para React/Vite (e.g. descargar un binario standalone de node, usar vistas servidas por FastAPI usando Jinja, o pedir a sistemas que instale Node).

## Jornada: 2026-04-29 — Frontend scaffolding

### Hechos
- **Vite + React + Tailwind**: proyecto `frontend-app/` inicializado con Vite, React, Tailwind CSS y configuración de deploy. Node.js fue desbloqueado.
- **Páginas iniciales**: scaffolding de dashboards, navegación, mock data y layout components (commits `c0bc36b`, `c96e32e`).

## Jornada: 2026-04-30 — Subida de archivos + worker async

### Hechos
- **Flujo de upload**: `POST /api/v1/lotes` recibe Excel, persiste el `LoteArchivo` y dispara `procesar_lote_en_background` con FastAPI `BackgroundTasks`.
- **Worker async**: refactor del worker para procesar de punta a punta sin tocar Parquet (lee Excel → adapters → E3 → E4 → SQLite) (commit `c6b73b3`).

## Jornada: 2026-05-04 — Migración pyspark → pandas finalizada

### Hechos
- Se consolidó la migración del flujo PySpark a Pandas con la nueva arquitectura API + core services. Pipeline E2E activo vía `python run_pipeline.py` (commit `85bb49b`).

## Jornada: 2026-05-05 — Detalle de partes + auditoría + edición manual

### Hechos
- **DetallePartes (B6)**: pantalla completa con visor de imágenes, formulario de edición, panel de observaciones, integraciones con UsuariosApp y Contratistas.
- **Auditoría append-only**: `AuditoriaCambio` registra cada edición con valor antes/después, usuario y timestamp; `BandejaAuditoria` (B5) consume el feed.
- **Optimistic Locking**: edición de partes valida `version` para evitar conflictos concurrentes.
- **Reclasificación automática**: editar `ord_nro` sobre un parte con `id_traza ∈ {7, 20}` reclasifica al estado/traza correcto. Cubierto por `test_parte_service_reclasificacion`.
- (commits `9553e57`, `5987206`).

## Jornada: 2026-05-07 — Admin de códigos EPEC + Sync Oracle SIGEC + Auto-rescate

### Hechos

- **Admin Reglas + Mapeos (`api/routers/admin.py`, `services/reglas_service.py`)**:
    - CRUD de reglas `cod_epec` (descripcion, obs aplicables, valor USES, soft delete).
    - CRUD de mapeos contratista/cod_contratista → cod_epec (con FASE).
    - Endpoint `POST /seed` idempotente para poblar reglas y mapeos desde literales/parquet inicial.
    - Frontend `MapeoCodigosAdmin.jsx` consume todos los endpoints.

- **Auth básica (`api/core/auth.py`)**: dependencia `require_admin` que protege endpoints sensibles (sync Oracle). Sin middleware todavía — control por convenio.

- **Sync Oracle SIGEC → SQLite local (CE + PROTELEM)**:
    - `oracle_sync_service.sincronizar_ordenativos_protelem` trae ordenativos + fotos + equipos en una sola conexión Oracle, usa `INSERT ... ON CONFLICT DO UPDATE` chunked (CHUNK=500), y commit transaccional con rollback total ante fallo intermedio.
    - 3 modelos ORM nuevos: `OrdenativoOracleLocal`, `OrdenativoOracleFoto`, `OrdenativoOracleEquipo`.
    - Endpoint admin `POST /sync-ordenativos-oracle` (BackgroundTasks) + `GET /status` con counts y resultado del último run.
    - Panel de sync en `MapeoCodigosAdmin` (botón "Sincronizar ahora", polling 3s, contadores de ordenativos/fotos/equipos, manejo de 401/403 ocultando el panel).

- **Rescate de huérfanos contra DB local (`rescate_ordenativos_service`)**:
    - `buscar_candidatos_local`: misma firma de retorno que `oracle_service.buscar_candidatos` original — el endpoint UI `/partes/{id}/candidatos-oracle` ya no consulta Oracle live.
    - Política A (suministro) + B (medidor → suministro vía `OrdenativoOracleEquipo`) con dedup por `ord_numero`.
    - `rescatar_huerfanos_lote`: clasifica candidatos por tolerancia: 1→`rescate_unico`, N≥2→`ambiguo_multiple`, 0→`sin_match`.

- **Auto-rescate batch en el worker (`worker._auto_rescatar_local`)**:
    - Tras Etapa 4, los partes con `ID_TRAZA==7` ("Sin Orden Asociada") se reasignan automáticamente:
      - 1 candidato cercano (≤7 días) → `ID_TRAZA=19` ("Rescatado por Oracle"), `ID_ESTADO=2`, `ORD_NRO` asignado.
      - N≥2 candidatos cercanos → `ID_TRAZA=20` ("Múltiples Candidatos Oracle"), `ID_ESTADO=2`, `ORD_NRO=NULL` (auditor desambigua).
      - 0 candidatos / DB sin sync → no toca el parte.

- **Trazas nuevas en `dim_traza`**: 19 ("Rescatado por Oracle"), 20 ("Múltiples Candidatos Oracle").

- **Config (`src/config.py`)**: `RESCATE_DIAS_TOLERANCIA=7`, `RESCATE_FECHA_INICIO_BOOTSTRAP="31/05/2025"`.

- **Etapa 4 parametrizable**: `procesar_etapa4(df_fact_input, df_reglas=None)` permite que el worker pase reglas precargadas desde el ORM en vez de leer Parquet (mantiene fallback CLI).

- **Cleanup oracle_service.py**: removida `buscar_candidatos` (dead code post-migración a DB local). Quedan solo `_limpiar_url_firebase` y `get_fotos_por_ord_numeros` (fallback live para fotos).

- **Visor de fotos prefiere DB local**: `parte_service._fotos_oracle_visor` lee `OrdenativoOracleFoto` primero y solo cae a Oracle live si no hay registros (ORD_NRO previo al bootstrap o sync no corrido).

### Validaciones
- 51/51 tests verdes en el área Oracle/rescate/parte/uses (`test_oracle_sync.py`, `test_rescate_local.py`, `test_parte_service_reclasificacion.py`, `test_uses_enrichment.py`).
- `test_kpis_core.py` sigue con 5 fallos heredados (paridad numérica E4, snapshots stale) — no relacionados con esta jornada; pendiente revisar la generación de snapshots.

### Próximos pasos
- Regenerar snapshots de `test_kpis_core` o investigar la diferencia control_obs (22483) vs fact aprobados (40519).
- Considerar índice en `OrdenativoOracleEquipo.ste_numero` si el volumen lo demanda.
- UI de desambiguación para `ID_TRAZA==20` (auditor elige entre N candidatos).

## [Actualización 2026-05-08] — Sugerencias de cod_epec en Detalle de Parte

### Objetivo
Asistir al auditor para asociar el `cod_epec` correcto en partes Aprobados, comparando las observaciones cargadas por el operario contra las reglas activas vía distancia de Hamming. Toda asociación pasa por un modal de confirmación que cambia de tono según la divergencia, y queda registrada en bitácora con un motivo predefinido.

### Implementaciones

#### Backend
- **Helper Hamming compartido** (`src/hamming.py`): `hamming_matrix(N×K vs M×K → int16)` y `campos_diferentes(app_row, regla_row)`. Importado desde Etapa 4 (`_calcular_hamming_global` ahora delega) y desde el nuevo servicio de UI — única fuente de verdad para evitar drift numérico.
- **`SugerenciasService`** (`api/services/sugerencias_service.py`): para un `parte_id` Aprobado, calcula la distancia Hamming contra todas las reglas activas y arma `match_exacto` (Hamming=0), `cercanos` (top 3 con Hamming>0, ordenados por hamming asc → valor_uses desc → cod_epec asc) y `todas` (lista plana usada por el dropdown del UI para preview Hamming sin segundo round-trip). Para partes sin observaciones replica la convención de Etapa 4 (cod 11).
- **DTOs** (`api/schemas/sugerencias_schemas.py`): `CandidatoEpecDTO`, `CandidatosEpecResponse`, `OpcionEpecDTO`.
- **Endpoints**:
  - `GET /api/v1/partes/{id}/codigos-epec-candidatos` → 404 si no existe, 400 si no está Aprobado.
  - `GET /api/v1/admin/reglas/cod-epec-opciones` → lista plana `(cod_epec, descripcion, valor_uses)` para selectores. Declarado *antes* de `/reglas/{regla_id}` para evitar el match con el conversor `int`.

#### Frontend (`DetallePartes.jsx`)
- Subsección **"Códigos EPEC Candidatos"** entre las observaciones del operario y los cruces. Renderiza tarjetas separadas para match exacto (verde) y top 3 cercanos (ámbar/rojo según Hamming ≥ 2). Cada tarjeta muestra `cod_epec`, descripción, score N/8, Hamming y `campos_diferentes`. Si el cod actual coincide, badge "Asignado actualmente"; si no, botón "Asociar este código".
- **Dropdown** `cod_epec` reemplaza el input texto: lista todas las opciones del catálogo con `(cod, desc, USES)`, y debajo muestra "Hamming: N · Difiere en: …" en color rojo cuando Hamming ≥ 2.
- **Modal único de dos modos**:
  - Simple (Hamming < 2 o sin candidato): header verde, mensaje neutro, motivo automático `"Asociación de cod_epec acorde a observaciones cargadas (Hamming=N)"`.
  - Warning (Hamming ≥ 2): header rojo, lista de `campos_diferentes`, motivo `"Asociación de cod_epec con discrepancia significativa vs observaciones (Hamming=N)"`.
  - Ambos modos exponen un textarea opcional ("Observación adicional") que se concatena al motivo final.
- Política: cualquier cambio de `cod_epec` (sea por click en tarjeta o por dropdown) dispara el modal — imposible saltearse la confirmación.

### Validaciones
- **Tests nuevos**:
  - `tests/test_hamming_helper.py` (6 tests): paridad bit-exacta vs cálculo inline original, casos extremos, `campos_diferentes` en orden canónico.
  - `tests/test_sugerencias_service.py` (7 tests): match exacto único, fallback cod 11 sin obs, ordenamiento de cercanos, errores 400/404, múltiples descripciones para el mismo cod, `campos_diferentes` correcto.
- **Suite total**: 79/84 verdes. Los 5 fallos restantes son los heredados de `test_kpis_core` (snapshots stale, no relacionados con esta jornada).
- **Lint frontend**: 8 warnings preexistentes en `DetallePartes.jsx` (prop-types, unescaped-entities) — esta jornada no introdujo nuevos.

### Decisiones técnicas
- **Umbral warning fuerte = Hamming ≥ 2**: criterio acordado con el usuario para distinguir asociaciones coherentes de las que ameritan registro explícito de la decisión.
- **Helper Hamming compartido** en lugar de duplicar la fórmula: garantiza paridad bit-exacta entre el motor batch y la API single-parte, evitando drift cuando se evolucione el algoritmo.
- **`todas` en el response**: el frontend no necesita un segundo round-trip para calcular el Hamming preview de una opción cualquiera del dropdown (~21 reglas activas hoy → payload trivial).
- **Mapeo ORM ↔ OBS_COLS** vía `_OBS_FIELDS` de `reglas_service.py`: el lower-case del nombre canónico no coincide con el ORM en `EQUIPO_DE_MEDICION_INSTALADO`, por lo que se reusa la lookup table existente.

### Próximos pasos
- (Opcional) Cuando el cod_epec se cambia manualmente, el motor recalcula `valor_uses_obs` solo en el próximo run de Etapa 4. Evaluar recalcular en el PATCH si se vuelve crítico para la UX.

