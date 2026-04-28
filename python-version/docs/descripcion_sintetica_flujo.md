# Descripción Sintética del Flujo — Pipeline Partes Diarios (Python Local)

> Versión migrada desde PySpark/Fabric a Python + Pandas.
> Todas las tablas se almacenan como Parquet en `data/`.

---

## Etapa 1 — Maestros

Lee 2 archivos Excel de configuración y genera tablas Parquet en `data/master/`:

- **mapeo_codigos_master** (116 filas): traduce código de contratista → `COD_EPEC` + `cant_USE_unitario` + `FASE`.
- **reglas_cod_obs_app** (21 filas): combinaciones de observaciones esperadas por código (8 columnas binarias que definen qué debe observarse en cada tipo de trabajo).

---

## Etapa 2 — Adapters (CONECTAR + COOPLYF)

Lee los archivos Excel de partes diarios de cada contratista, normaliza columnas (nombres, tipos, fechas) y los apila en `data/stage/` como Parquet.

- Lleva una **bitácora** para no reprocesar archivos ya cargados.
- Flag `--reproceso` fuerza la recarga de todo.
- Salida: `staging_conectar` y `staging_cooplyf`.

---

## Etapa 0 — Seeds (opcional, requiere conexión Oracle)

Extrae 6 tablas desde las bases SIGEC y GEOREF de EPEC, guardándolas en `data/seed/`:

| Seed                     | Filas aprox. | Contenido                                   |
|--------------------------|--------------|---------------------------------------------|
| `dim_ord`                | 5.7M         | Ordenativos de trabajo (CE, IC, CX, etc.)       |
| `sigec_general`          | 1.2M         | Suministros con datos geográficos            |
| `dim_stk_stock_equipos`  | 2.2M         | Stock de medidores (fases, marca, etc.)      |
| `pivot_resul_app_movil`  | 284K         | Observaciones de la app móvil (pivoteadas)   |
| `eqp_equipos_ultimos_10` | 77K          | Últimos 10 equipos por suministro            |
| `usuarios_gral`          | 952          | Usuarios/operarios                           |

---

## Etapa 3 — Core Waterfall

El corazón del pipeline. Toma cada parte del staging y lo cruza contra los ordenativos de trabajo para determinar su validez y clasificación.

### Waterfall de cruces (sub-bloque 3.3)

1. **Cruce A** — Parte ↔ ordenativo CE de la **misma contratista** (por suministro + fecha ±15 días). Asigna traza de calidad comparando medidores declarados vs. SIGEC:
   - `Original OK`: medidores coinciden exactamente.
   - `Corregido Nro EQP Invertidos`: colocado/retirado están al revés.
   - `Corregido Nro Medidor`: medidores no coinciden (se corrigen desde SIGEC).
   - `Corregido Medidor Vacio`: parte sin medidor declarado.

2. **Cruce B** — Los pendientes del Cruce A se buscan contra ordenativos **no-CE** (IC, CX, MP, RX, etc.). Si matchea → `No Corresponde TOR CE` (fuera de alcance).

3. **Cruce C** — Rescate técnico por número de medidor: el operario escribió mal el suministro pero el medidor está bien. Se identifica el suministro real desde SIGEC y se busca el ordenativo CE de ese suministro. Traza: `Corregido Sumi` o `Corregido Sumi Nro EQP`.

4. **Huérfanos** — Los que no matchearon en ningún cruce:
   - Con suministro válido → `Sin Orden Asociada`
   - Sin medidor → `Error Sumi Sin Nro Medidor`
   - Con medidor → `Error Sumi Y Nro Medidor`

5. **Regla "Otro Origen"** — Si el ordenativo tiene `SEC_CODIGO_ORIGEN ≠ PROTELEM`, se pisa la traza a `Otro Origen` (fuera de alcance).

6. **Regla "Informado - No Ejecutado"** — Si el ordenativo cruzado tiene `ORD_RESULTADO = IN`, se aprueba el cruce pero se asigna la traza `Informado - No Ejecutado` (rechazado), ya que este ordenativo no fue ejecutado en campo.

### Enriquecimiento y dedup (sub-bloque 3.3 cont.)

6. **Enriquecimiento**: join con usuarios (nombre del operario), stock de equipos (fase MON/TRI) y maestro de códigos (COD_EPEC + USES).

8. **Dedup "Informados con ORD-SUMI aprobado"**: si un suministro tiene múltiples partes, el mejor queda aprobado (prioridad: COD_EPEC ≠ 11, fecha más reciente, row_id más alto) y los demás se marcan `Informados con ORD-SUMI aprobado` (rechazados).

9. **Merge a fact**: normaliza al schema `COLS_FACT` (22 columnas) y escribe a `data/gold/fact_partes_diarios_full` vía upsert por `ID_PARTE_HASH`.

### Dimensiones (sub-bloques 3.1, 3.2, 3.4)

| Dimensión                | Filas  | Descripción                                       |
|--------------------------|--------|---------------------------------------------------|
| `dim_estado_bi`          | 4      | Aprobado, Revisión, Rechazado, Fuera de Alcance   |
| `dim_traza_calidad_bi`   | 12     | Todas las trazas posibles                         |
| `dim_empresa_bi`         | 2      | CONECTAR, COOPLYF                                 |
| `dim_usuarios_bi`        | 952    | ID ↔ nombre de operario                           |
| `dim_archivo_bi`         | 9      | Archivos de input procesados                      |
| `dim_suministros_geo`    | 72,920 | Coordenadas, calle, barrio, departamento          |
| `dim_calendario`         | 273    | Rango de fechas con atributos (mes, trimestre, año) |

### Panel de KPIs (sub-bloque 3.5)

Imprime el mismo panel que la Celda 7 del PySpark original: totales por estado, efectividad, desglose por traza, USES por contratista, detalle mensual. Diseñado para comparar visualmente contra Power BI.

---

## Etapa 4 — Control de Observaciones y Valoración Económica (USES)

Toma solo los **aprobados** (40,527) de la fact y los cruza contra las observaciones de la app móvil para detectar discrepancias entre lo declarado y lo observado en campo.

### Los 7 pasos

1. **Carga**: fact aprobados + dimensiones + pivot de la app (join por `ORD_NRO`).
2. **Normalización**: 8 campos de observación de la app → 0/1 (`_APP_GABINETE`, `_APP_SUBTERRANEO`, etc.). Flag `_SIN_OBS` si todas son 0.
3. **VALOR_USES_ORIGEN**: lookup del valor USES esperado según el código declarado por el contratista.
4. **Faltantes/excedentes**: compara observaciones declaradas vs. reglas del código. Identifica qué observaciones faltan y cuáles sobran.
5. **Código sugerido por Hamming**: cross join contra TODAS las reglas, calcula distancia Hamming (cuántas observaciones difieren) y sugiere el código que mejor matchea las observaciones reales.
6. **Diferencia económica**: `DIFERENCIA_USES = VALOR_USES_ORIGEN - VALOR_USES_OBS`. Clasifica:
   - **Sin Discrepancia**: código declarado = código sugerido.
   - **Sobrevaloración**: el contratista declaró un código que vale más USES.
   - **Subvaloración**: el contratista declaró un código que vale menos USES.
   - **Error Operativo**: códigos distintos pero mismo valor USES.
   - **Sin Observaciones**: el operario no cargó observaciones en la app.
7. **Guardado**: `control_obs_app` en gold (40,527 filas, 42 columnas).

### Tabla adicional

- **dim_img_app_pd** (40,524 filas): URLs de fotos Firebase limpias, una fila por ordenativo.

---

## Resumen de tablas finales

| Capa       | Tabla                      | Filas   | Cols | Descripción                                |
|------------|----------------------------|---------|------|--------------------------------------------|  
| **gold**   | `fact_partes_diarios_full`  | 121,967 | 22   | Tabla de hechos principal                  |
| **gold**   | `control_obs_app`           | 40,527  | 42   | Análisis de discrepancias (solo aprobados) |
| **dim**    | `dim_estado_bi`             | 4       | 2    | Estados posibles                           |
| **dim**    | `dim_traza_calidad_bi`      | 12      | 2    | Trazas de calidad                          |
| **dim**    | `dim_empresa_bi`            | 2       | 2    | Contratistas                               |
| **dim**    | `dim_usuarios_bi`           | 952     | 2    | Operarios                                  |
| **dim**    | `dim_archivo_bi`            | 9       | 2    | Archivos procesados                        |
| **dim**    | `dim_suministros_geo`       | 72,920  | 9    | Georreferenciación                         |
| **dim**    | `dim_calendario`            | 273     | 6    | Calendario                                 |
| **dim**    | `dim_img_app_pd`            | 40,524  | 6    | Fotos de la app                            |
| **master** | `mapeo_codigos_master`      | 116     | 6    | Mapeo de códigos                           |
| **master** | `reglas_cod_obs_app`        | 21      | 11   | Reglas de observaciones                    |

---

## Ejecución

```bash
# Desde python-version/, usando el venv:
..\venv\Scripts\python.exe run_pipeline.py                    # Todo end-to-end (etapas 1-4)
..\venv\Scripts\python.exe run_pipeline.py --solo-etapa 3     # Solo Core + dims + KPIs
..\venv\Scripts\python.exe run_pipeline.py --solo-etapa 4     # Solo Control de Observaciones
..\venv\Scripts\python.exe -m src.etapa3_panel_kpis           # Solo el panel KPIs
..\venv\Scripts\python.exe -m pytest tests/ -v                # Tests de no-regresión (20 tests)
..\venv\Scripts\python.exe scripts/inspect_parte.py --suministro 419389  # Debugging
```
