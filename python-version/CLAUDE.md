# Reglas técnicas — proyecto migración PySpark → Pandas

> Este archivo se carga en cada turno. Son reglas que ya costaron sangre o
> están documentadas en `pyspark-version/plan_migracion_local.md`. No
> repetir errores conocidos.

## Invariantes del Core (Fase 3)

1. **NUNCA** `df.apply(axis=1)` en hot loops. Vectorizar con `np.where`,
   `np.select`, `Series.where/mask`, o operaciones de columna.
2. **Sort para reproducir `Window.orderBy` de Spark**: SIEMPRE
   `kind="mergesort"` + tie-breakers explícitos (ej. `_DECL_DESC`,
   `_REGLA_DESCRIPCION`, `_row_id`). Sin tie-breakers el resultado es
   no-determinista.
3. **`_row_id`** se genera con `np.arange(len(df), dtype=np.int64)`. Nunca
   `monotonically_increasing_id` ni equivalente — esto rompe la
   idempotencia entre runs.
4. **`FASE == "AMBAS"`**: pre-expandir `df_mc` a dos filas (`MON` y `TRI`)
   ANTES del merge. NO usar OR en la condición de join.
5. **MERGE de la fact table**: solo vía `io.merge_table(...,
   key="ID_PARTE_HASH")`. Nunca `to_parquet` directo sobre `gold/fact_*`.
6. **TRUNCATE del staging**: solo DESPUÉS de confirmar el write/MERGE
   ([H-07] en el plan). Nunca antes.
7. **Schema de la fact**: orden y tipos exactos según `config.COLS_FACT`.
   Si toco esa lista, propago a todos los call sites en el mismo commit.

## Antes de tocar cualquier sub-bloque

1. Leer la sección equivalente del PySpark original
   (`pyspark-version/procesar_pd_gral_refactor (5).py`).
2. El diff Pandas-vs-PySpark debe ser **justificable línea a línea**.
   Si encuentro una mejora, la propongo aparte — no la mezclo con la
   migración.
3. Para sub-bloques sensibles del waterfall (cruces A/B/C, dedup
   `Repetido X Sumi`, paso 4a/4b de Etapa 4): usar plan mode antes de
   editar.

## Validación (sin Fabric disponible)

- No hay baseline row-level (Fabric sin capacidad). Validamos contra el
  Power BI local del usuario vía el "Panel KPIs" (sub-ticket 3.5).
- Loop: corro pipeline → imprimo panel → usuario compara con Power BI →
  si difiere, uso `scripts/inspect_parte.py` para muestrear partes
  individuales. Detalle en `docs/workflow_fase3.md`.

## Convenciones del repo

- IO con `src/io_lakehouse.py` (`read_table`/`write_table`/`merge_table`/
  `write_table_chunked`). Nunca leer/escribir Parquet directo.
- Conexión Oracle solo vía `src/oracle_io.OracleReadOnly` (sesión
  `SET TRANSACTION READ ONLY`, 4 capas de protección).
- Constantes y rutas en `src/config.py` — única fuente de verdad.
- Hashes deterministas en `src/hashing.py` (`id_parte_hash`,
  `id_externo_cooplyf`).
- Mapeo de términos Oracle ↔ staging ↔ fact en
  `pyspark-version/plan_migracion_local.md` §0.2.1.

## Lo que ya está hecho (no re-implementar)

- Etapa 0 (seeds), 1 (maestros), 2 (adapters CONECTAR + COOPLYF),
  3 (core waterfall + dims BI + dims geo/cal + panel KPIs),
  4 (control de observaciones + dim_img_app_pd).
- Pipeline end-to-end: `python run_pipeline.py` corre todo.
- Ver `pyspark-version/plan_migracion_local.md` §0.1 para snapshot del estado.
