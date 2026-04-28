#!/usr/bin/env python
# coding: utf-8

# ## control_obs_pd_ce
# 
# null

# ## Carga de Reglas por Códigos de Cierre

# In[2]:


#!/usr/bin/env python
# coding: utf-8

# =============================================================================
# CELDA 1 — TABLA DE REGLAS DE OBSERVACIONES POR CÓDIGO DE CIERRE
# =============================================================================
#
# Crea/actualiza datos_generales.reglas_cod_obs_app con las combinaciones
# válidas de observaciones esperadas para cada código de cierre EPEC.
#
# ESTRUCTURA DE COLUMNAS:
#   COD_EPEC    : código de cierre (clave de join con fact_partes_diarios_full)
#   DESCRIPCION : nombre de la variante (un mismo COD puede tener varias)
#   GABINETE, SUBTERRANEO, ALTURA, AEREO → dónde se realizó el trabajo (sitio)
#   EQUIPO_MEDICION_REEMPLAZADO, ACOMETIDA_REALIZADA,
#   TAPA_REEMPLAZADA, EQUIPO_DE_MEDICION_INSTALADO → qué se hizo (trabajo)
#   VALOR_USES  : valor USES asociado al código
#
# VALORES: 1 = observación REQUERIDA para ese código/variante
#          0 = observación NO requerida (no debe aparecer)
# =============================================================================

from pyspark.sql.types import (
    StructType, StructField, LongType, StringType, IntegerType, DoubleType
)

TABLA_REGLAS = "datos_generales.reglas_cod_obs_app"

# -----------------------------------------------------------------------------
# Datos de la tabla de reglas
# Columnas: COD_EPEC, DESCRIPCION,
#           GABINETE, SUBTERRANEO, ALTURA, AEREO,
#           EQUIPO_MEDICION_REEMPLAZADO, ACOMETIDA_REALIZADA,
#           TAPA_REEMPLAZADA, EQUIPO_DE_MEDICION_INSTALADO,
#           VALOR_USES
# -----------------------------------------------------------------------------
datos_reglas = [
    #  COD   DESCRIPCION                                                               GAB  SUB  ALT  AER  MED  ACO  TAP  INS   USES
    (   22,  "Normalización Monofasica Aérea SIN tapa",                                  0,   0,   0,   1,   1,   1,   0,   1,  0.1860),
    (   44,  "Cambio de equipo Trifasico con tapa (subterraneo)",                        0,   1,   0,   0,   1,   0,   1,   1,  0.1000),
    (   44,  "Cambio de equipo Trifasico con tapa (aereo)",                              0,   0,   0,   1,   1,   0,   1,   1,  0.1000),
    (   44,  "Cambio de equipo Trifasico con tapa (altura)",                             0,   0,   1,   0,   1,   0,   1,   1,  0.1000),
    (   43,  "Cambio de equipo Monofasico con tapa (subterraneo)",                       0,   1,   0,   0,   1,   0,   1,   1,  0.1000),
    (   43,  "Cambio de equipo Monofasico con tapa (aereo)",                             0,   0,   0,   1,   1,   0,   1,   1,  0.1000),
    (   43,  "Cambio de equipo Monofasico con tapa (altura)",                            0,   0,   1,   0,   1,   0,   1,   1,  0.1000),
    (   11,  "Informado",                                                                0,   0,   0,   0,   0,   0,   1,   0,  0.0100),
    (   12,  "Normalización Trifasica Aérea SIN tapa",                                   0,   0,   0,   1,   1,   1,   0,   1,  0.4560),
    (    1,  "Normalización Trifasica Aérea",                                            0,   0,   0,   1,   1,   1,   0,   1,  0.7600),
    (   15,  "Normalización Trifasica en Altura con cambio de tapa",                     0,   0,   1,   0,   1,   1,   1,   1,  1.0000),
    (   15,  "Normalización Trifasica en Altura sin cambio de tapa",                     0,   0,   1,   0,   1,   1,   0,   1,  1.0000),
    (   15,  "Normalización Trifasica en linea Aerea con Cruce de calle",                0,   0,   1,   0,   1,   1,   1,   1,  1.0000),
    (    7,  "Cambio de equipo (en gabinete)",                                           1,   0,   0,   0,   1,   0,   0,   1,  0.0600),
    (    7,  "Cambio de equipo (subterraneo)",                                           0,   1,   0,   0,   1,   0,   0,   1,  0.0600),
    (    7,  "Cambio de equipo (aereo)",                                                 0,   0,   0,   1,   1,   0,   0,   1,  0.0600),
    (    7,  "Cambio de equipo (altura)",                                                0,   0,   1,   0,   1,   0,   0,   1,  0.0600),
    (   25,  "Normalización Monofasica Altura con cambio de tapa",                       0,   0,   1,   0,   1,   1,   1,   1,  0.3600),
    (   25,  "Normalización Monofasica Altura sin cambio de tapa",                       0,   0,   1,   0,   1,   1,   0,   1,  0.3600),
    (   25,  "Normalización Monofasica en linea Aerea con Cruce de calle",               0,   0,   1,   0,   1,   1,   0,   1,  0.3600),
    (    2,  "Normalización Monofasica Aérea",                                           0,   0,   0,   1,   1,   1,   1,   1,  0.3100),
]

schema_reglas = StructType([
    StructField("COD_EPEC",                        LongType(),    False),
    StructField("DESCRIPCION",                     StringType(),  False),
    StructField("GABINETE",                        IntegerType(), False),
    StructField("SUBTERRANEO",                     IntegerType(), False),
    StructField("ALTURA",                          IntegerType(), False),
    StructField("AEREO",                           IntegerType(), False),
    StructField("EQUIPO_MEDICION_REEMPLAZADO",     IntegerType(), False),
    StructField("ACOMETIDA_REALIZADA",             IntegerType(), False),
    StructField("TAPA_REEMPLAZADA",                IntegerType(), False),
    StructField("EQUIPO_DE_MEDICION_INSTALADO",    IntegerType(), False),
    StructField("VALOR_USES",                      DoubleType(),  False),
])

df_reglas = spark.createDataFrame(datos_reglas, schema=schema_reglas)

df_reglas.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TABLA_REGLAS)

print(f"✅ Tabla '{TABLA_REGLAS}' creada con {df_reglas.count()} reglas.")
print()
display(df_reglas)


# ## Control de observaciones contra reglas por codigo

# In[1]:


#!/usr/bin/env python
# coding: utf-8

# =============================================================================
# CELDA 2 — CONTROL DE OBSERVACIONES Y VALORACIÓN ECONÓMICA (USES) — v5 FIXED
# =============================================================================
#
# CAMBIOS v5 (FIXES):
#   [FIX-1] Detección de match fallido: cuando el JOIN con reglas del código
#           declarado no encuentra variantes, ahora se detecta y se marcan
#           TODAS las observaciones requeridas como faltantes.
#
#   [FIX-2] Validación de integridad de reglas: se agrega flag _REGLA_MATCH
#           para identificar registros sin regla definida vs registros donde
#           el operario no cargó observaciones.
#
#   [FIX-3] Cálculo de faltantes robusto: ya no depende de coalesce(NULL, 0)
#           que enmascaraba los casos sin match.
#
# CAMBIOS v4 (heredados):
#   [REFACTOR] Orden de análisis: primero vs código declarado, luego global.
#
# CAMBIOS v2 (heredados):
#   [FIX] Anti fan-out: dropDuplicates(["ID_PARTE_HASH"])
#   [FIX] Window por ID_PARTE_HASH
#   [FIX] Validación de integridad
# =============================================================================

from pyspark.sql import Window
from pyspark.sql.functions import (
    col, when, lit, abs as spark_abs, coalesce,
    row_number, concat_ws, current_timestamp, broadcast, round as spark_round,
    sum as spark_sum, count as spark_count,
)

# -----------------------------------------------------------------------------
# Tablas
# -----------------------------------------------------------------------------
TABLA_FACT      = "datos_generales.fact_partes_diarios_full"
TABLA_REGLAS    = "datos_generales.reglas_cod_obs_app"
TABLA_OUTPUT    = "datos_generales.control_obs_app"

TABLA_USUARIOS  = "datos_generales.dim_usuarios_bi"
TABLA_ESTADO    = "datos_generales.dim_estado_bi"
TABLA_TRAZA     = "datos_generales.dim_traza_calidad_bi"
TABLA_EMPRESA   = "datos_generales.dim_empresa_bi"
TABLA_ARCHIVO   = "datos_generales.dim_archivo_bi"
TABLA_PIVOT_APP = "datos_generales.pivot_resul_app_movil"

# Las 8 columnas de observación — nombre en app y nombre en reglas (mismo orden)
OBS_COLS = [
    ("'APP4SITIO_3'", "GABINETE"),
    ("'APP4SITIO_4'", "SUBTERRANEO"),
    ("'APP4SITIO_2'", "ALTURA"),
    ("'APP4SITIO_1'", "AEREO"),
    ("'APP4TRAB_1'",  "EQUIPO_MEDICION_REEMPLAZADO"),
    ("'APP4TRAB_2'",  "ACOMETIDA_REALIZADA"),
    ("'APP4TRAB_3'",  "TAPA_REEMPLAZADA"),
    ("'APP4TRAB_4'",  "EQUIPO_DE_MEDICION_INSTALADO"),
]

VALOR_USES_COD_11 = 0.0100  # USES del código 11 (Informado / Sin observaciones)

print(f"\n{'='*80}")
print("🔍 INICIANDO CONTROL DE OBSERVACIONES Y VALORACIÓN ECONÓMICA (v5 FIXED)")
print(f"{'='*80}")

# =============================================================================
# PASO 1 — Cargar partes aprobados con observaciones de la app
# =============================================================================
print("\n[1/7] Cargando partes aprobados con observaciones...")

df_fact = spark.table(TABLA_FACT)
df_usr  = spark.table(TABLA_USUARIOS)
df_est  = spark.table(TABLA_ESTADO)
df_trz  = spark.table(TABLA_TRAZA)
df_emp  = spark.table(TABLA_EMPRESA)
df_arch = spark.table(TABLA_ARCHIVO)
df_app  = spark.table(TABLA_PIVOT_APP)

# Join con dimensiones
df_base = df_fact \
    .join(df_est,  "ID_ESTADO",  "left") \
    .join(df_trz,  "ID_TRAZA",   "left") \
    .join(df_emp,  "ID_EMPRESA", "left") \
    .join(df_usr,  df_fact.USR_ID == df_usr.USR_NUMERO, "left") \
    .join(df_arch, "ID_ARCHIVO", "left") \
    .filter(col("DESC_ESTADO") == "Aprobado")

# [FIX] Guardia anti fan-out
_count_pre = df_base.count()
df_base = df_base.dropDuplicates(["ID_PARTE_HASH"])
_count_post = df_base.count()
if _count_pre != _count_post:
    print(f"   ⚠️  Fan-out detectado y corregido: {_count_pre} → {_count_post}")
else:
    print(f"   ✅ Sin fan-out: {_count_post} registros")

COLS_BASE = df_base.columns

# Join con pivot de la app por número de ordenativo
df_con_app = df_base.join(
    df_app,
    df_base.ORD_NRO == df_app["ORD_NUMERO"],
    "left",
)

# =============================================================================
# PASO 2 — Normalizar observaciones de la app a 0/1
# =============================================================================
print("\n[2/7] Normalizando observaciones de la app...")

df_norm = df_con_app
for col_app, col_regla in OBS_COLS:
    df_norm = df_norm.withColumn(
        f"_APP_{col_regla}",
        when(col(f"`{col_app}`").isNotNull(), lit(1)).otherwise(lit(0))
    )

# Flag: el operario no cargó ninguna observación
expr_sin_obs = sum(col(f"_APP_{cr}") for _, cr in OBS_COLS)
df_norm = df_norm.withColumn("_SIN_OBS", when(expr_sin_obs == 0, lit(True)).otherwise(lit(False)))

total_partes = df_norm.count()
print(f"   Partes aprobados: {total_partes:,}".replace(",", "."))

# =============================================================================
# PASO 3 — Obtener VALOR_USES_ORIGEN del código declarado
# =============================================================================
print("\n[3/7] Asignando VALOR_USES_ORIGEN por código declarado...")

df_reglas = spark.table(TABLA_REGLAS)

# [FIX v5] Asegurar que el tipo de COD_EPEC coincida
df_reglas = df_reglas.withColumn("COD_EPEC", col("COD_EPEC").cast("long"))

df_uses_lookup = df_reglas.select(
    col("COD_EPEC").alias("_LOOKUP_COD"),
    col("VALOR_USES").alias("VALOR_USES_ORIGEN"),
).distinct()

df_con_origen = df_norm.join(
    broadcast(df_uses_lookup),
    df_norm.CODIGO_EPEC == df_uses_lookup["_LOOKUP_COD"],
    "left",
).drop("_LOOKUP_COD")

# =============================================================================
# PASO 4a — Join vs reglas del CÓDIGO DECLARADO → faltantes/excedentes
# =============================================================================
print("\n[4a/7] Calculando faltantes/excedentes vs código declarado...")

# Preparar reglas del código declarado
df_reglas_decl = df_reglas.select(
    col("COD_EPEC").alias("_DECL_COD"),
    col("DESCRIPCION").alias("_DECL_DESC"),
    *[col(cr).alias(f"_DECL_{cr}") for _, cr in OBS_COLS],
)

# Join restringido: cada parte solo ve las variantes de SU código declarado
df_cross_decl = df_con_origen.join(
    broadcast(df_reglas_decl),
    df_con_origen.CODIGO_EPEC == df_reglas_decl["_DECL_COD"],
    "left",
)

# [FIX v5] Detectar si el JOIN encontró match con las reglas
df_cross_decl = df_cross_decl.withColumn(
    "_REGLA_MATCH",
    when(col("_DECL_COD").isNotNull(), lit(True)).otherwise(lit(False))
)

# Hamming contra las variantes del código declarado
# [FIX v5] Solo calcular si hay match, sino dejar como NULL para detectar después
expr_hamming_decl = when(
    col("_REGLA_MATCH"),
    sum(
        spark_abs(
            coalesce(col(f"_APP_{cr}"), lit(0)) -
            coalesce(col(f"_DECL_{cr}"), lit(0))
        )
        for _, cr in OBS_COLS
    )
).otherwise(lit(None))

df_cross_decl = df_cross_decl.withColumn("_HAMMING_DECL", expr_hamming_decl)

# Mejor variante del código declarado (menor Hamming)
w_decl = Window.partitionBy("ID_PARTE_HASH").orderBy(
    col("_HAMMING_DECL").asc_nulls_last(),  # [FIX v5] NULLs al final
    col("_DECL_DESC").asc_nulls_last(),
)
df_best_decl = df_cross_decl \
    .withColumn("_rank_decl", row_number().over(w_decl)) \
    .filter(col("_rank_decl") == 1) \
    .drop("_rank_decl")

# =============================================================================
# [FIX v5] Calcular faltantes/excedentes con manejo robusto de NULLs
# =============================================================================
campos_faltantes  = []
campos_excedentes = []

for _, cr in OBS_COLS:
    app_col  = coalesce(col(f"_APP_{cr}"),  lit(0))
    # [FIX v5] Si no hay match, la regla se considera como "todo requerido" (1)
    # Esto asegura que si no encontramos la regla, marquemos faltantes
    decl_col = when(
        col("_REGLA_MATCH"),
        coalesce(col(f"_DECL_{cr}"), lit(0))
    ).otherwise(lit(1))  # [FIX v5] Sin match → asumir que todo es requerido

    df_best_decl = df_best_decl.withColumn(
        f"_FALTA_{cr}",
        when((decl_col == 1) & (app_col == 0), lit(1)).otherwise(lit(0))
    )
    df_best_decl = df_best_decl.withColumn(
        f"_EXCEDE_{cr}",
        when((decl_col == 0) & (app_col == 1), lit(1)).otherwise(lit(0))
    )
    campos_faltantes.append(f"_FALTA_{cr}")
    campos_excedentes.append(f"_EXCEDE_{cr}")

def concat_campos_flag(prefix, cols_list):
    return concat_ws(", ", *[
        when(col(c) == 1, lit(c.replace(prefix, ""))).otherwise(lit(None))
        for c in cols_list
    ])

df_con_diffs_decl = df_best_decl \
    .withColumn("TOTAL_FALTANTES",
        sum(col(c) for c in campos_faltantes)) \
    .withColumn("TOTAL_EXCEDENTES",
        sum(col(c) for c in campos_excedentes)) \
    .withColumn("DETALLE_FALTANTES",
        concat_campos_flag("_FALTA_", campos_faltantes)) \
    .withColumn("DETALLE_EXCEDENTES",
        concat_campos_flag("_EXCEDE_", campos_excedentes)) \
    .withColumn("VARIANTE_DECLARADA", 
        when(col("_REGLA_MATCH"), col("_DECL_DESC"))
        .otherwise(lit("SIN REGLA PARA CÓDIGO DECLARADO"))  # [FIX v5]
    ) \
    .drop(
        "_DECL_DESC", "_HAMMING_DECL", "_DECL_COD",
        *[f"_DECL_{cr}" for _, cr in OBS_COLS],
        *campos_faltantes, *campos_excedentes,
    )

# [FIX v5] Log de diagnóstico
_sin_match = df_con_diffs_decl.filter(~col("_REGLA_MATCH")).count()
if _sin_match > 0:
    print(f"   ⚠️  {_sin_match} registros SIN match con reglas del código declarado")

# =============================================================================
# PASO 4b — Cross join vs TODAS las reglas → COD_EPEC_SUGERIDO
# =============================================================================
print("\n[4b/7] Buscando código sugerido por distancia Hamming global...")

df_reglas_cross = df_reglas.select(
    col("COD_EPEC").alias("_REGLA_COD_EPEC"),
    col("DESCRIPCION").alias("_REGLA_DESCRIPCION"),
    col("VALOR_USES").alias("_REGLA_VALOR_USES"),
    *[col(cr).alias(f"_REGLA_{cr}") for _, cr in OBS_COLS],
)

df_cross = df_con_diffs_decl.crossJoin(broadcast(df_reglas_cross))

# Hamming global
expr_hamming = sum(
    spark_abs(
        coalesce(col(f"_APP_{cr}"), lit(0)) -
        coalesce(col(f"_REGLA_{cr}"), lit(0))
    )
    for _, cr in OBS_COLS
)
df_cross = df_cross.withColumn("HAMMING_DIST", expr_hamming)

# Mejor match global
w_best = Window.partitionBy("ID_PARTE_HASH").orderBy(
    col("HAMMING_DIST").asc(),
    col("_REGLA_DESCRIPCION").asc(),
)
df_best = df_cross \
    .withColumn("_rank", row_number().over(w_best)) \
    .filter(col("_rank") == 1) \
    .drop("_rank")

# =============================================================================
# PASO 5 — Asignar COD_EPEC_SUGERIDO
# =============================================================================
print("\n[5/7] Asignando código sugerido y VALOR_USES_OBS...")

df_sugerido = df_best \
    .withColumn("COD_EPEC_SUGERIDO",
        when(col("_SIN_OBS"), lit(11))
        .otherwise(col("_REGLA_COD_EPEC"))
    ) \
    .withColumn("DESCRIPCION_SUGERIDA",
        when(col("_SIN_OBS"), lit("Sin Observaciones Cargadas"))
        .otherwise(col("_REGLA_DESCRIPCION"))
    ) \
    .withColumn("VALOR_USES_OBS",
        when(col("_SIN_OBS"), lit(VALOR_USES_COD_11))
        .otherwise(col("_REGLA_VALOR_USES"))
    )

# =============================================================================
# PASO 6 — Calcular diferencias económicas y clasificar
# =============================================================================
print("\n[6/7] Calculando diferencias económicas y clasificando...")

df_econ = df_sugerido \
    .withColumn("DIFERENCIA_USES",
        spark_round(col("VALOR_USES_ORIGEN") - col("VALOR_USES_OBS"), 4)
    ) \
    .withColumn("DIFERENCIA_USES_ABS",
        spark_round(spark_abs(col("VALOR_USES_ORIGEN") - col("VALOR_USES_OBS")), 4)
    )

# [FIX v5] Clasificación mejorada incluyendo caso "Sin Regla para Código"
df_resultado = df_econ.withColumn(
    "DISCREPANCIA_CODIGO",
    when(col("VALOR_USES_ORIGEN").isNull(),
         lit("Sin Regla Definida"))
    .when(~col("_REGLA_MATCH"),
         lit("Sin Regla para Código Declarado"))  # [FIX v5] Nuevo estado
    .when(col("_SIN_OBS"),
         lit("Sin Observaciones"))
    .when(col("CODIGO_EPEC") == col("COD_EPEC_SUGERIDO"),
         lit("Sin Discrepancia"))
    .when(col("DIFERENCIA_USES") == 0,
         lit("Error Operativo"))
    .when(col("DIFERENCIA_USES") > 0,
         lit("Sobrevaloración"))
    .otherwise(
         lit("Subvaloración"))
).withColumn(
    "TIMESTAMP_CONTROL", current_timestamp()
)

# =============================================================================
# PASO 7 — Selección final y guardado
# =============================================================================
print("\n[7/7] Guardando resultados...")

COLS_CONTROL = [
    "VARIANTE_DECLARADA",
    "TOTAL_FALTANTES",
    "TOTAL_EXCEDENTES",
    "DETALLE_FALTANTES",
    "DETALLE_EXCEDENTES",
    "COD_EPEC_SUGERIDO",
    "DESCRIPCION_SUGERIDA",
    "HAMMING_DIST",
    "VALOR_USES_ORIGEN",
    "VALOR_USES_OBS",
    "DIFERENCIA_USES",
    "DIFERENCIA_USES_ABS",
    "DISCREPANCIA_CODIGO",
    "TIMESTAMP_CONTROL",
]

# [FIX v5] Limpiar columnas temporales antes del SELECT final
df_final = df_resultado.select(
    *[col(c) for c in COLS_BASE],
    *[col(c) for c in COLS_CONTROL],
)

# Validación de integridad
_count_fact_aprobados = spark.table(TABLA_FACT).filter(col("es_pagable") == 1).count()
_count_final = df_final.count()
if _count_final != _count_fact_aprobados:
    print(f"   ⚠️  ALERTA DE INTEGRIDAD: fact={_count_fact_aprobados}, control={_count_final}")
else:
    print(f"   ✅ Integridad OK: {_count_final} registros")

df_final.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TABLA_OUTPUT)

# =============================================================================
# PANEL DE RESULTADOS (actualizado con nuevo estado)
# =============================================================================
from pyspark.sql.functions import count, desc, sum as spark_sum, avg as spark_avg

df_panel = spark.table(TABLA_OUTPUT)
df_panel.cache()

total    = df_panel.count()
kpi_rows = df_panel.groupBy("DISCREPANCIA_CODIGO").agg(count("*").alias("cantidad")).collect()
kpi      = {r["DISCREPANCIA_CODIGO"]: r["cantidad"] for r in kpi_rows}

print(f"\n{'='*80}")
print("📊 RESULTADOS DEL CONTROL DE OBSERVACIONES Y VALORACIÓN ECONÓMICA (v5)")
print(f"{'='*80}")
print(f"▶ Total partes controlados:           {total:,}".replace(",", "."))
print(f"  ✅ Sin Discrepancia:                {kpi.get('Sin Discrepancia', 0):,}".replace(",", "."))
print(f"  🔴 Sobrevaloración (EPEC pierde):   {kpi.get('Sobrevaloración', 0):,}".replace(",", "."))
print(f"  🟡 Subvaloración (Contrat pierde):  {kpi.get('Subvaloración', 0):,}".replace(",", "."))
print(f"  🔵 Error Operativo (USES iguales):  {kpi.get('Error Operativo', 0):,}".replace(",", "."))
print(f"  ⚪ Sin Observaciones:               {kpi.get('Sin Observaciones', 0):,}".replace(",", "."))
print(f"  ⚪ Sin Regla Definida:              {kpi.get('Sin Regla Definida', 0):,}".replace(",", "."))
print(f"  🟠 Sin Regla para Código Declarado: {kpi.get('Sin Regla para Código Declarado', 0):,}".replace(",", "."))

# Índice de asimetría
sobreval = kpi.get("Sobrevaloración", 0)
subval   = kpi.get("Subvaloración", 0)
if (sobreval + subval) > 0:
    indice = sobreval / (sobreval + subval)
    print(f"\n📈 ÍNDICE DE ASIMETRÍA: {indice:.2%}")

# Impacto económico
print(f"\n--- Impacto económico por tipo de discrepancia ---")
df_panel.filter(col("DISCREPANCIA_CODIGO").isin("Sobrevaloración", "Subvaloración")) \
    .groupBy("DISCREPANCIA_CODIGO") \
    .agg(
        count("*").alias("Cantidad"),
        spark_round(spark_sum("DIFERENCIA_USES_ABS"), 4).alias("Impacto_USES_Total"),
        spark_round(spark_avg("DIFERENCIA_USES_ABS"), 4).alias("Impacto_USES_Promedio"),
    ) \
    .orderBy("DISCREPANCIA_CODIGO") \
    .show(truncate=False)

print(f"\n--- Desglose por Contratista ---")
df_panel.groupBy("EMPRESA", "DISCREPANCIA_CODIGO") \
    .agg(count("*").alias("Cantidad")) \
    .orderBy("EMPRESA", "DISCREPANCIA_CODIGO") \
    .show(truncate=False)

print(f"\n--- Top 10 códigos con mayor sobrevaloración ---")
df_panel.filter(col("DISCREPANCIA_CODIGO") == "Sobrevaloración") \
    .groupBy("CODIGO_EPEC", "COD_EPEC_SUGERIDO") \
    .agg(
        count("*").alias("Cantidad"),
        spark_round(spark_sum("DIFERENCIA_USES"), 4).alias("Impacto_Total"),
    ) \
    .orderBy(desc("Impacto_Total")) \
    .show(10, truncate=False)

# [FIX v5] Nuevo reporte: registros sin regla para código declarado
_sin_regla_cod = kpi.get('Sin Regla para Código Declarado', 0)
if _sin_regla_cod > 0:
    print(f"\n--- ⚠️  Códigos declarados SIN regla definida ---")
    df_panel.filter(col("DISCREPANCIA_CODIGO") == "Sin Regla para Código Declarado") \
        .groupBy("CODIGO_EPEC") \
        .agg(count("*").alias("Cantidad")) \
        .orderBy(desc("Cantidad")) \
        .show(20, truncate=False)

df_panel.unpersist()
print(f"\n✅ Tabla '{TABLA_OUTPUT}' lista (v5 FIXED).")
print(f"{'='*80}")


# ## Generar dimension de imagenes

# In[1]:


from pyspark.sql.functions import col, split, regexp_replace, when

# 1. Leer la tabla pivot (cruda) y la tabla de control (nuestro filtro)
df_pivot = spark.read.table("datos_generales.pivot_resul_app_movil")
# Solo traemos la columna ORD_NRO de control_obs_app para que el join sea ligerísimo
df_control = spark.read.table("datos_generales.control_obs_app").select("ORD_NRO")

# 2. Definir la función de limpieza de Firebase
def limpiar_url_firebase(nombre_columna):
    url_base = split(col(nombre_columna), " - ").getItem(0)
    url_corregida = regexp_replace(url_base, r"\?alt:media", "?alt=media")
    url_corregida = regexp_replace(url_corregida, r"&token:", "&token=")
    return when(col(nombre_columna).isNotNull() & (col(nombre_columna) != ""), url_corregida).otherwise(None)

# 3. Aplicar limpieza a las columnas
df_img_limpias = df_pivot.select(
    col("ORD_NUMERO").alias("ORD_NRO"),
    limpiar_url_firebase("'APP4OBS_80'_TOB_DESCRIPCION").alias("IMAGEN_1"),
    limpiar_url_firebase("'APP4OBS_81'_TOB_DESCRIPCION").alias("IMAGEN_2"),
    limpiar_url_firebase("'APP4OBS_82'_TOB_DESCRIPCION").alias("IMAGEN_3"),
    limpiar_url_firebase("'APP4OBS_83'_TOB_DESCRIPCION").alias("IMAGEN_4"),
    limpiar_url_firebase("'APP4OBS_84'_TOB_DESCRIPCION").alias("IMAGEN_5")
)

# 4. Filtrar las filas que directamente no tengan ninguna foto
df_img_con_datos = df_img_limpias.filter(
    col("IMAGEN_1").isNotNull() | 
    col("IMAGEN_2").isNotNull() | 
    col("IMAGEN_3").isNotNull() | 
    col("IMAGEN_4").isNotNull() | 
    col("IMAGEN_5").isNotNull()
)

# 5. EL FILTRO CLAVE: Dejamos solo los ordenativos que están en control_obs_app
df_img_filtrada = df_img_con_datos.join(df_control, on="ORD_NRO", how="left_semi")

# 5.5 ELIMINAR DUPLICADOS: Garantizamos que sea una tabla de Dimensión pura (Relación 1 a Varios en Power BI)
df_img_final = df_img_filtrada.dropDuplicates(["ORD_NRO"])

# 6. Guardar la dimensión final limpia y filtrada
df_img_final.write \
    .format("delta") \
    .mode("overwrite") \
    .saveAsTable("datos_generales.dim_img_app_pd")

print(f"Tabla dim_img_app_pd creada exitosamente. Total de ordenativos ÚNICOS con fotos: {df_img_final.count()}")

