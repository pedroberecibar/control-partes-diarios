# Diseño: Administración de Reglas de Códigos EPEC

> Generado: 2026-05-05  
> Propósito: Document de diseño completo para revisión. Describe el estado actual, la propuesta de arquitectura, la secuencia de implementación y las decisiones abiertas que requieren confirmación antes de codear.

---

## 1. Estado actual — diagnóstico

### 1.1 Las dos tablas maestras que queremos hacer configurables

El pipeline tiene **dos Parquet estáticos** que se generan en `src/etapa1_maestros.py` y se usan en cada procesamiento:

| Archivo Parquet | Generado por | Usado en | Propósito |
|---|---|---|---|
| `master/mapeo_codigos_master.parquet` | Etapa 1 (desde Excel) | Etapa 3 Core | Traducir código de contratista → `CODIGO_EPEC` + `cant_USE_unitario` |
| `master/reglas_cod_obs_app.parquet` | Etapa 1 (literal en código) | Etapa 4 Control de Obs | Definir qué observaciones son requeridas para cada código + `VALOR_USES` |

### 1.2 `mapeo_codigos_master` — estructura

Viene de dos Excel (`conversion_codigos_contratista_a_PD_PBI.xlsx` + `OP_MI.xlsx`), se cruzan y persisten. Columnas relevantes:

```
CONTRATISTA              → "CONECTAR" | "COOPLYF"
COD_CONTRATISTA_INDIVIDUAL  → e.g. "001", "002" (ya explotado por coma del Excel)
FASE                     → "MON" | "TRI" | "AMBAS"
COD_EPEC                 → int, e.g. 7, 11, 22, 44
DESCRIPCION_CODIGO       → string
cant_USE_unitario        → float — USES por unidad de tarea (para billing en Etapa 3)
```

El operario escribe el `COD_CONTRATISTA_INDIVIDUAL` en su Excel. Etapa 3 hace el JOIN para obtener el `COD_EPEC`.

### 1.3 `reglas_cod_obs_app` — estructura

21 filas **hardcodeadas** en `etapa1_maestros.py` como lista de tuplas (`_DATOS_REGLAS`). Columnas:

```
COD_EPEC        → int
DESCRIPCION     → string — identifica la variante dentro del código
GABINETE        → 0 | 1
SUBTERRANEO     → 0 | 1
ALTURA          → 0 | 1
AEREO           → 0 | 1
EQUIPO_MEDICION_REEMPLAZADO → 0 | 1
ACOMETIDA_REALIZADA         → 0 | 1
TAPA_REEMPLAZADA            → 0 | 1
EQUIPO_DE_MEDICION_INSTALADO → 0 | 1
VALOR_USES      → float — valor económico de la tarea
```

Un mismo `COD_EPEC` puede tener **múltiples variantes**. Ejemplo: `COD_EPEC=7` tiene 4 filas (gabinete, subterraneo, aereo, altura). Etapa 4 calcula la distancia Hamming entre las observaciones del operario y **todas** las 21 reglas para encontrar la mejor match.

### 1.4 Cómo usa Etapa 4 las reglas

```
df_reglas = io.read_table("reglas_cod_obs_app", capa="master")  ← Parquet

PASO 3:  VALOR_USES_ORIGEN = lookup por CODIGO_EPEC declarado
PASO 4a: join con reglas del CODIGO_EPEC declarado → calcular faltantes/excedentes
PASO 4b: cross join vs TODAS las reglas → Hamming mínimo → COD_EPEC_SUGERIDO
PASO 5:  asignar VALOR_USES_OBS desde la regla de menor Hamming
PASO 6:  DIFERENCIA_USES = VALOR_USES_ORIGEN - VALOR_USES_OBS → tipo discrepancia
```

> **Invariante crítica**: el orden de las 8 columnas de observaciones importa para el cálculo de Hamming. Está definido en `config.OBS_COLS`. No debe cambiar.

---

## 2. Objetivo de la feature

Crear una **interfaz de administración** que permita:

1. Ver todos los mapeos de códigos en una tabla unificada.
2. Crear, editar y activar/desactivar reglas de observaciones por código.
3. Mantener el seeder (`etapa1_maestros.py`) como carga inicial desde los Excel originales.
4. Que los cambios hechos desde la UI tengan efecto en el próximo procesamiento de partes.

Columnas de la tabla en la UI:
- Código EPEC
- Código Contratista (referencia de mapeo)
- Descripción de la variante
- Valor USE
- 8 flags de observaciones (true/false)
- Estado (activo/inactivo)

---

## 3. Propuesta de arquitectura

### 3.1 Principio guía

Pasar de **Parquet como fuente de verdad** → **ORM (SQLite/Postgres) como fuente de verdad**, manteniendo el Parquet como artefacto generado para compatibilidad con el pipeline CLI.

```
                   ┌─────────────────────┐
                   │  Admin UI           │
                   │  (AdminCodigos.jsx) │
                   └─────────┬───────────┘
                             │ CRUD via API
                   ┌─────────▼───────────┐
                   │  ORM tables         │  ← FUENTE DE VERDAD
                   │  ReglaCodEpec       │
                   │  MapeoCodigoContr.  │
                   └─────────┬───────────┘
                             │
              ┌──────────────┼───────────────────┐
              │                                  │
    ┌─────────▼─────────┐              ┌─────────▼──────────┐
    │  Web Worker        │              │  CLI pipeline       │
    │  parte_import_     │              │  etapa1_maestros   │
    │  service.py        │              │  → exporta Parquet │
    │  (lee de ORM)      │              │  → Etapa 4 lee     │
    └────────────────────┘              └────────────────────┘
```

### 3.2 Nuevas tablas ORM

#### `ReglaCodEpec` (reemplaza `reglas_cod_obs_app.parquet`)

```python
class ReglaCodEpec(Base):
    __tablename__ = "reglas_cod_epec"

    id              = Column(Integer, primary_key=True)
    cod_epec        = Column(Integer, nullable=False, index=True)
    descripcion     = Column(String(200), nullable=False)

    # 8 flags de observaciones (1=requerido, 0=no requerido)
    gabinete                        = Column(Boolean, nullable=False, default=False)
    subterraneo                     = Column(Boolean, nullable=False, default=False)
    altura                          = Column(Boolean, nullable=False, default=False)
    aereo                           = Column(Boolean, nullable=False, default=False)
    equipo_medicion_reemplazado     = Column(Boolean, nullable=False, default=False)
    acometida_realizada             = Column(Boolean, nullable=False, default=False)
    tapa_reemplazada                = Column(Boolean, nullable=False, default=False)
    equipo_medicion_instalado       = Column(Boolean, nullable=False, default=False)

    valor_uses      = Column(Float, nullable=False)
    activo          = Column(Boolean, default=True, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by      = Column(Integer, ForeignKey("usuarios_app.id"), nullable=True)

    # Restricción: (cod_epec, descripcion) debe ser único entre reglas activas
    __table_args__ = (UniqueConstraint("cod_epec", "descripcion", name="uq_regla_cod_desc"),)
```

#### `MapeoCodigoContratista` (reemplaza `mapeo_codigos_master.parquet`)

```python
class MapeoCodigoContratista(Base):
    __tablename__ = "mapeo_codigos_contratista"

    id                      = Column(Integer, primary_key=True)
    contratista_id          = Column(Integer, ForeignKey("contratistas.id"), nullable=False)
    cod_contratista         = Column(String(20), nullable=False)   # e.g. "001"
    fase                    = Column(String(5), nullable=False)     # "MON"|"TRI"|"AMBAS"
    cod_epec                = Column(Integer, nullable=False, index=True)
    descripcion_codigo      = Column(String(200), nullable=True)
    cant_use_unitario       = Column(Float, nullable=True)
    activo                  = Column(Boolean, default=True, nullable=False)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())

    contratista             = relationship("Contratista")
```

> **Nota sobre `MapeoCodigoContratista`**: esta tabla reemplaza el Excel como fuente de verdad del mapeo. El seeder la puebla desde el Excel en la primera corrida; después es administrable desde la UI (o solo desde el seeder, ver Decisión Abierta #1).

### 3.3 Vista unificada para la UI

La tabla que pide el usuario es la combinación de ambas entidades. La query de listado es:

```
Para cada ReglaCodEpec activa:
  - Traer los cod_contratista de MapeoCodigoContratista donde cod_epec coincide
  - Agruparlos como lista ("001, 002, 003") para mostrar en la UI
```

Esto se puede resolver en una sola query con `GROUP_CONCAT` / `array_agg` en Postgres, o cargando ambas tablas y haciendo el join en el service. Dado el volumen pequeño (21 reglas, ~50 mapeos), hacerlo en Python es más portable y simple.

### 3.4 API endpoints nuevos

Router base: `/api/v1/admin/`

```
GET    /admin/reglas                  → lista todas las reglas con cod_contratista agrupado
GET    /admin/reglas/{id}             → detalle de una regla
POST   /admin/reglas                  → crear nueva regla
PATCH  /admin/reglas/{id}             → editar campos de una regla existente
DELETE /admin/reglas/{id}             → desactivar (soft delete — activo=False)

GET    /admin/mapeo-codigos           → lista todos los mapeos contratista → epec
POST   /admin/mapeo-codigos           → crear nuevo mapeo
PATCH  /admin/mapeo-codigos/{id}      → editar un mapeo
DELETE /admin/mapeo-codigos/{id}      → desactivar mapeo

POST   /admin/reglas/exportar-parquet → (opcional) regenera el Parquet desde ORM
```

### 3.5 Modificaciones al pipeline

#### `etapa1_maestros.py` — Seeder

Hoy solo escribe Parquet. Hay que agregar una segunda responsabilidad: **poblar las tablas ORM si están vacías** (idempotente con `INSERT OR IGNORE`).

```python
def _seed_orm_reglas(df: pd.DataFrame, db: Session) -> None:
    """Carga inicial de reglas en ORM si la tabla está vacía."""
    if db.query(ReglaCodEpec).count() > 0:
        return  # ya seedeado — no pisar cambios del admin
    for _, row in df.iterrows():
        db.add(ReglaCodEpec(cod_epec=row.COD_EPEC, ...))
    db.commit()

def _seed_orm_mapeo(df: pd.DataFrame, db: Session) -> None:
    """Carga inicial de mapeos en ORM si la tabla está vacía."""
    if db.query(MapeoCodigoContratista).count() > 0:
        return
    for _, row in df.iterrows():
        db.add(MapeoCodigoContratista(...))
    db.commit()
```

> **Invariante de seguridad**: el seeder NO sobreescribe si la tabla ya tiene datos. Los cambios del admin se preservan entre re-ejecuciones del pipeline.

#### `etapa4_control_obs.py` — Lectura de reglas

Hay dos modos de ejecución:
- **Modo web** (llamado desde `parte_import_service.py`): tiene acceso al ORM.
- **Modo CLI** (llamado directamente): no tiene sesión de DB activa.

La solución más limpia es extender `procesar_etapa4()` para aceptar `df_reglas` opcional:

```python
# etapa4_control_obs.py — cambio mínimo
def procesar_etapa4(
    df_fact_input: pd.DataFrame,
    df_reglas: pd.DataFrame | None = None,   # ← NUEVO parámetro
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ...
    if df_reglas is None:
        df_reglas = io.read_table("reglas_cod_obs_app", capa="master")  # fallback CLI
    df_reglas["COD_EPEC"] = df_reglas["COD_EPEC"].astype("Int64")
    ...
```

En `parte_import_service.py`, cargar las reglas desde ORM y pasarlas:

```python
# parte_import_service.py — ajuste al llamar Etapa 4
df_reglas = reglas_service.cargar_reglas_como_dataframe(db)
df_final, df_img, metricas = procesar_etapa4(df_fact_input=df_fact, df_reglas=df_reglas)
```

Función en `reglas_service.py`:

```python
def cargar_reglas_como_dataframe(db: Session) -> pd.DataFrame:
    """Exporta ReglaCodEpec activas al formato que espera Etapa 4."""
    reglas = db.query(ReglaCodEpec).filter(ReglaCodEpec.activo == True).all()
    return pd.DataFrame([{
        "COD_EPEC":                       r.cod_epec,
        "DESCRIPCION":                    r.descripcion,
        "GABINETE":                       int(r.gabinete),
        "SUBTERRANEO":                    int(r.subterraneo),
        "ALTURA":                         int(r.altura),
        "AEREO":                          int(r.aereo),
        "EQUIPO_MEDICION_REEMPLAZADO":    int(r.equipo_medicion_reemplazado),
        "ACOMETIDA_REALIZADA":            int(r.acometida_realizada),
        "TAPA_REEMPLAZADA":               int(r.tapa_reemplazada),
        "EQUIPO_DE_MEDICION_INSTALADO":   int(r.equipo_medicion_instalado),
        "VALOR_USES":                     r.valor_uses,
    } for r in reglas])
```

> **Invariante**: el orden de columnas del DataFrame retornado DEBE coincidir con `config.OBS_COLS`. La función debe construirse con esa lista como referencia, no hardcodeando el orden.

#### `etapa3_core.py` — Mapeo de códigos

Etapa 3 también lee `mapeo_codigos_master.parquet`. El mismo patrón aplica: aceptar `df_mapeo` opcional; si no, leer Parquet. Esto es un **cambio de fase 2** (ver sección 5).

---

## 4. Frontend — `AdminCodigos.jsx`

### 4.1 Layout

Pantalla nueva accesible desde el menú de navegación (ícono de llave/settings), solo visible para rol admin (a definir si hay autenticación activa).

```
┌──────────────────────────────────────────────────────────────┐
│ Administración de Códigos EPEC                               │
│                                         [+ Nueva regla]      │
├──────────┬─────────────────────────────────────────────────────┤
│ Filtros  │ Tabla con columnas:                                │
│          │  CÓD. EPEC │ CONTRATISTA(S) │ DESCRIPCIÓN │ USES │ │
│ Por cód. │  GAB SUB ALT AER MED ACO TAP INS │ ESTADO │ ACC. │ │
│ Por ctr. ├──────────────────────────────────────────────────── │
│          │  7  │ 001,002 │ Cambio equipo aereo │ 0.06 │ ●●○○○○○● │
│          │  7  │ 001,002 │ Cambio equipo gab.  │ 0.06 │ ●○○○○○○● │
│          │  22 │ 004     │ Norm. Monof. Aérea  │ 0.186│ ○○○●●●○● │
│          │ ...                                                 │
└──────────┴─────────────────────────────────────────────────────┘
```

### 4.2 Columnas de la tabla

- **Cód. EPEC**: número, sorteable
- **Contratista(s)**: badges (CONECTAR / COOPLYF) + lista de `COD_CONTRATISTA_INDIVIDUAL` agrupados. Read-only en esta vista (el mapeo se gestiona por separado o en modal expandido).
- **Descripción**: texto de la variante
- **Valor USE**: número float con 4 decimales
- **8 observaciones**: iconos ✓/— (activa/no requerida). Editable inline o en modal.
- **Estado**: chip Activo/Inactivo
- **Acciones**: editar, desactivar

### 4.3 Modal de edición

Al hacer click en "Editar" se abre un modal con:
- `cod_epec` (int, readonly si es edición)
- `descripcion` (text input)
- `valor_uses` (number input)
- 8 toggles booleanos con etiqueta
- Botón Guardar con optimistic locking (`version` field)

### 4.4 Archivos frontend nuevos

```
src/pages/AdminCodigos.jsx          ← pantalla principal
src/api/adminCodigosApi.js          ← cliente REST
src/components/ObsBoolGrid.jsx      ← grilla reutilizable de 8 flags (usada también en DetallePartes)
```

---

## 5. Plan de implementación secuencial

### Fase 1 — Backend models + seeder (sin tocar Etapa 3/4)

1. Agregar `ReglaCodEpec` y `MapeoCodigoContratista` a `domain_models.py`.
2. Crear `api/db/migrations/` si no existe (o actualizar `create_all`).
3. Agregar `_seed_orm_reglas()` y `_seed_orm_mapeo()` a `etapa1_maestros.py`.
4. Ejecutar el seeder una vez para poblar las tablas ORM.
5. Verificar integridad: `SELECT COUNT(*) FROM reglas_cod_epec` debe dar 21; `mapeo_codigos_contratista` el número de filas del mapeo.

### Fase 2 — API CRUD + schemas

1. `api/schemas/admin_schemas.py`: DTOs de request/response para reglas y mapeo.
2. `api/services/reglas_service.py`: lógica CRUD + `cargar_reglas_como_dataframe()`.
3. `api/routers/admin.py`: endpoints REST.
4. Registrar el router en `main.py`.
5. Testear con curl / Swagger que POST/PATCH/DELETE funcionen.

### Fase 3 — Integración con Etapa 4

1. Agregar parámetro `df_reglas: pd.DataFrame | None = None` a `procesar_etapa4()`.
2. En `parte_import_service.py`: llamar a `reglas_service.cargar_reglas_como_dataframe(db)` antes de llamar a `procesar_etapa4()`.
3. Mantener el fallback Parquet para el modo CLI (`run()`).
4. Verificar que un cambio de regla en la UI se refleje en el próximo lote procesado.

### Fase 4 — Frontend `AdminCodigos.jsx`

1. `adminCodigosApi.js`.
2. `AdminCodigos.jsx` con la tabla y el modal de edición.
3. `ObsBoolGrid.jsx` como componente reutilizable.
4. Agregar navegación en `App.jsx` y en el sidebar.

### Fase 5 — (Opcional) Integración con Etapa 3

1. Agregar `df_mapeo: pd.DataFrame | None = None` a la función principal de Etapa 3.
2. En `parte_import_service.py`: cargar mapeo desde ORM antes de Etapa 3.
3. Agregar UI para gestionar `MapeoCodigoContratista` (crear/editar mapeos).

> Las fases 1-4 son el MVP. Fase 5 es opcional si el mapeo se sigue manteniendo solo desde los Excel.

---

## 6. Decisiones abiertas — confirmar antes de codear

### D1: ¿`MapeoCodigoContratista` es administrable desde la UI o solo via seeder?

**Opción A**: Solo seeder/Excel. La UI solo muestra los mapeos como referencia (read-only). El admin edita las *reglas* de observaciones y *valor USE*, pero si necesita cambiar a qué `COD_EPEC` va un código de contratista, actualiza el Excel y re-seedea.

**Opción B**: Totalmente administrable. La UI permite CRUD completo sobre mapeos también.

**Recomendación**: Opción A para MVP. Los mapeos cambian raramente (son la "definición del catálogo"), mientras que las reglas de observaciones pueden cambiar con mayor frecuencia.

### D2: ¿Qué pasa cuando se cambia una regla y hay partes ya procesados con la regla anterior?

Los partes ya procesados tienen `cod_epec_sugerido`, `valor_uses_obs`, `diferencia_uses` y `tipo_discrepancia` guardados en la DB (como resultado de Etapa 4). Un cambio de regla **no recalcula** esos valores históricos — solo afecta los lotes nuevos.

**Acción necesaria**: Agregar un aviso en la UI: *"Los cambios aplican al próximo lote procesado. Los partes ya procesados no se recalculan."*

### D3: ¿Los cambios de reglas se auditan?

Actualmente `AuditoriaCambio` solo cubre partes procesados. ¿Queremos un log de quién cambió qué regla y cuándo?

**Recomendación**: Sí, agregar `AuditoriaRegla` (append-only) con: `regla_id`, `usuario_id`, `accion` (CREATE/UPDATE/DEACTIVATE), `valor_anterior` (JSON), `valor_nuevo` (JSON), `fecha_cambio`. El esfuerzo es bajo y el valor es alto para auditoría.

### D4: ¿El Parquet de reglas queda obsoleto después del MVP?

En modo web (worker), Etapa 4 leerá las reglas desde ORM. En modo CLI, seguirá leyendo el Parquet. El Parquet quedará **potencialmente desincronizado** si alguien hace cambios via UI y luego corre el pipeline en modo CLI.

**Opciones:**
- A: Agregar botón "Exportar a Parquet" en la UI admin (regenera el Parquet desde ORM).
- B: Hacer que `run()` en Etapa 4 lea de ORM si hay conexión a DB disponible.
- C: Documentar que el modo CLI es solo para debugging; producción siempre usa el worker web.

**Recomendación**: Opción C a corto plazo; Opción A (botón de exportación) como mejora posterior.

### D5: ¿Cómo manejar `VALOR_USES` cuando un mismo `COD_EPEC` tiene múltiples variantes?

En las reglas actuales, todas las variantes del mismo `COD_EPEC` tienen el **mismo** `VALOR_USES` (e.g., las 4 variantes del código 7 todas tienen 0.0600; las 3 del código 44 tienen 0.1000).

El Paso 3 de Etapa 4 hace `drop_duplicates()` sobre `COD_EPEC` al calcular `VALOR_USES_ORIGEN`, por lo que solo toma un `VALOR_USES` por código. Si en la UI se permite que distintas variantes del mismo código tengan distinto `VALOR_USES`, este comportamiento sería inconsistente.

**Recomendación**: Agregar validación en el service: si se intenta guardar una variante con `VALOR_USES` diferente a las otras variantes del mismo `COD_EPEC`, mostrar un warning al usuario. No bloquear, pero alertar.

---

## 7. Archivos afectados — resumen

| Archivo | Tipo de cambio |
|---|---|
| `api/db/models/domain_models.py` | Agregar `ReglaCodEpec`, `MapeoCodigoContratista` |
| `api/schemas/admin_schemas.py` | Nuevo — DTOs request/response |
| `api/services/reglas_service.py` | Nuevo — CRUD + exportar a DataFrame |
| `api/routers/admin.py` | Nuevo — endpoints REST |
| `api/main.py` | Registrar router admin |
| `src/etapa1_maestros.py` | Agregar `_seed_orm_*()` functions |
| `src/etapa4_control_obs.py` | Agregar parámetro `df_reglas` opcional |
| `api/services/parte_import_service.py` | Cargar reglas desde ORM antes de Etapa 4 |
| `frontend-app/src/pages/AdminCodigos.jsx` | Nuevo — pantalla de admin |
| `frontend-app/src/api/adminCodigosApi.js` | Nuevo — cliente REST |
| `frontend-app/src/components/ObsBoolGrid.jsx` | Nuevo — grilla de 8 flags reutilizable |
| `frontend-app/src/App.jsx` | Agregar ruta `/admin/codigos` y navegación |

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El seeder re-seedea y pisa cambios del admin | Alto | La condición `if count > 0: return` en el seeder lo previene |
| CLI usa reglas Parquet desactualizadas | Medio | Solo el worker web es producción; CLI es debugging |
| Hamming inestable si hay variantes con mismo Hamming | Bajo | El sort por `DESCRIPCION` asc como tie-breaker ya está implementado |
| El `VALOR_USES` de variantes del mismo código diverge | Medio | Validación en service + warning en UI (D5) |
| Sin auditoría de cambios de reglas | Medio | Agregar `AuditoriaRegla` (D3) |
