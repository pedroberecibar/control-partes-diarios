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

