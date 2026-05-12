# Mapa del Proyecto: Sistema de Gestión de Partes Diarios

Este documento define la arquitectura, flujos principales y convenciones del sistema, sirviendo como mapa guía para el desarrollo y contexto.

## 1. Arquitectura y Stack Tecnológico

Aplicación Full-Stack compuesta por un frontend en React, un backend en FastAPI y un motor de procesamiento de datos analítico (Pipeline) basado en Pandas/PyArrow.

- **Frontend:**
  - **Librería Core:** React 18
  - **Herramientas de Build:** Vite
  - **Estilos:** Tailwind CSS, Framer Motion
  - **Routing & Networking:** React Router DOM, Axios
- **Backend (Web API):**
  - **Framework API:** FastAPI, Uvicorn
  - **Base de Datos & ORM:** SQLite / PostgreSQL (Alembic para migraciones), SQLAlchemy 2.0
  - **Validación de Datos:** Pydantic
- **Motor Analítico (Pipeline):**
  - **Procesamiento de Datos:** Pandas, PyArrow, NumPy
  - **Integraciones:** `oracledb` para la ingesta desde SIGEC (Oracle)

## 2. Estructura de Directorios (Árbol Simplificado)

```text
/ (Raíz del Proyecto)
├── frontend-app/                   # Código del cliente web
│   ├── src/
│   │   ├── api/                    # Integración Axios con el backend (ej. API calls)
│   │   ├── components/             # Componentes de UI reutilizables
│   │   ├── pages/                  # Vistas principales (BandejaAuditoria, ListaLotes, etc.)
│   │   └── App.jsx / main.jsx      # Puntos de entrada y enrutador
│   ├── package.json
│   └── tailwind.config.js
│
├── python-version/                 # Backend Web API y Motor de Procesamiento (Pipeline)
│   ├── api/                        # Aplicación FastAPI Web
│   │   ├── core/                   # Configuraciones base y dependencias de BBDD
│   │   ├── db/
│   │   │   └── models/             # Modelos SQLAlchemy (domain_models, base_models)
│   │   ├── routers/                # Controladores de la API (partes, lotes, auditoria, admin)
│   │   ├── schemas/                # Modelos Pydantic para Request/Response
│   │   └── main.py                 # Punto de entrada FastAPI
│   ├── src/                        # Motor de Procesamiento (Pipeline de Datos)
│   │   ├── etapa0_seeds.py         # Extracción desde base de datos Oracle
│   │   ├── etapa1_maestros.py      # Generación de tablas maestras
│   │   ├── etapa2_adapter_*.py     # Parsing y estandarización (Conectar, Cooplyf)
│   │   ├── etapa3_core.py          # Lógica central del negocio (Waterfall)
│   │   ├── etapa4_control_obs.py   # Control de observaciones y asignación por Hamming
│   │   └── config.py               # Configuración de rutas y variables para el pipeline
│   ├── run_pipeline.py             # Script orquestador del Pipeline de Datos CLI
│   ├── alembic/                    # Migraciones de base de datos
│   └── requirements.txt
```

## 3. Flujo de Datos Principal

El sistema procesa y audita lotes (archivos Excel/CSV) cargados por las contratistas:

1. **Ingesta y Recepción (Frontend -> Backend):** 
   - El usuario sube el archivo en `SubidaArchivos.jsx`.
   - La API (`routers/lotes.py`) lo recibe, guarda el registro en `lotes_archivos` y almacena el archivo binario.
2. **Pipeline de Datos (Motor Local):** 
   - Ejecutado mediante `run_pipeline.py`.
   - **Etapa 0:** `etapa0_seeds.py` sincroniza datos de contexto desde Oracle.
   - **Etapa 2 (Adapters):** El archivo crudo es interpretado mediante un Adapter (ej. Conectar o Cooplyf) para estandarizar las columnas y llenar la tabla `partes_diarios_raw`.
   - **Etapa 3 (Core):** `etapa3_core.py` procesa los datos aplicando reglas de negocio (Waterfall) contra dimensiones BI, generando un DataFrame normalizado.
   - **Etapa 4 (Control de Observaciones):** `etapa4_control_obs.py` cruza la información declarada por el operario contra `reglas_cod_epec` utilizando distancia de Hamming para predecir/sugerir el código EPEC y las Unidades de Servicio (USES).
   - Los datos finales persisten en la tabla `partes_diarios_procesados`.
3. **Auditoría Web:** 
   - El auditor visualiza los resultados desde el Frontend (`BandejaAuditoria.jsx`).
   - Se validan las fotos (almacenadas en Firebase, vinculadas vía `parte_imagenes`).
   - Los cambios confirmados son registrados en `auditoria_cambios` de forma inmutable a través de `/api/v1/auditoria`.

## 4. Modelos de Datos / Entidades Clave

- **LoteArchivo:** Archivo Excel subido al sistema. Contiene metadatos de estado, progreso y contratista de origen.
- **ParteDiarioRaw:** Cada fila leída del Excel tal cual viene de origen.
- **ParteDiarioProcesado:** El objeto central tras pasar por el pipeline. Contiene las FKs (id_traza, id_estado, lote_id), la valorización de USES, y las observaciones mapeadas.
- **ReglaCodEpec:** Fuente de verdad para el mapeo de observaciones del operario vs Código EPEC y su valor USES correspondiente.
- **MapeoCodigoContratista:** Relación entre el código interno de la contratista y el `cod_epec`.
- **ParteImagen:** Metadatos de imágenes del parte en Firebase.
- **AuditoriaCambio:** Bitácora inmutable de todas las modificaciones realizadas a un parte en el Frontend.
- **OrdenativoOracleLocal / OrdenativoOracleFoto:** Espejos locales desde la DB Oracle (SIGEC) para consultas en vivo sin dependencia continua del backend on-prem.

## 5. Endpoints / Rutas Principales

### Backend API (`/api/v1`)
- `/lotes`: Subida de archivos, listado de lotes, obtención de estado y progreso.
- `/partes`: Fetch de `partes_diarios_procesados` paginados, detalles e imágenes para visualización en bandeja de entrada y paneles de control.
- `/auditoria`: Registro y validación de cambios generados por los auditores en un parte. Actualiza versiones.
- `/admin`: ABM de tablas maestras (Códigos EPEC, Mapeos, Roles y Usuarios).

### Frontend Routing
- `/`: Dashboard(s) principales (`DashboardCalidad.jsx`, `DashboardEvolucion.jsx`).
- `/subida`: Carga de Excel (`SubidaArchivos.jsx`).
- `/lotes`: Listado y status de cargas (`ListaLotes.jsx`, `DetalleLote.jsx`).
- `/auditoria`: Vista de revisión individual (`BandejaAuditoria.jsx`, `DetallePartes.jsx`).
- `/admin`: Gestión maestra de reglas y usuarios (`MapeoCodigosAdmin.jsx`, `UsuariosRolesAdmin.jsx`).

## 6. Convenciones y Patrones Detectados

- **Clean Architecture & Repository Pattern (Backend API):** Clara separación de responsabilidades. `routers` maneja el request/response de red; Pydantic en `schemas` se encarga de la validación; SQLAlchemy en `models` gestiona la persistencia de datos relacionales; SQLAlchemy Core/Services manejan lógica de negocio delegada.
- **Soft Deletes y Mutabilidad Auditada:** Los Partes no se borran sino que se auditan (`AuditoriaCambio`). Existen mecanismos de *Optimistic Locking* (versioning) en `ParteDiarioProcesado` para evitar condiciones de carrera entre auditores.
- **Aislamiento del Pipeline de Datos (Engine):** La limpieza pesada y cálculos por lote (Pandas) está separada del servicio transaccional (FastAPI). Se comunican principalmente a través del estado en SQLite/PostgreSQL, con scripts auto-contenidos de Etapas (0 al 4).
- **Espejo Local (Caching Pattern):** Los datos clave de la DB heredada de Oracle (SIGEC) se reflejan localmente (`ordenativos_oracle_local`) para garantizar velocidad en el Frontend y desacoplar de disponibilidad del servidor remoto durante el pipeline.
- **Separación de Componentes Frontend:** Fuerte división entre vistas en `src/pages` (inteligentes, con llamadas Axios) y `src/components` (presentacionales, diseño con Tailwind). Uso de `framer-motion` para micro-animaciones (feedback premium al usuario).
