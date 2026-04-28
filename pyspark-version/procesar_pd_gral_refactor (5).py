#!/usr/bin/env python
# coding: utf-8

# ## procesar_pd_gral_refactor
# 
# null

# In[6]:


#!/usr/bin/env python
# coding: utf-8

# ## procesar_pd_gral_refactor
# 
# null

# In[2]:


#!/usr/bin/env python
# coding: utf-8

# ## procesar_pd_gral_refactor
# 
# null

# In[2]:


#!/usr/bin/env python
# coding: utf-8

# =============================================================================
# procesar_pd_gral.py — v27.3
# =============================================================================
# CAMBIOS RESPECTO A v27.2:
#
#   [FIX-F] dim_usuarios_bi: dropDuplicates(["USR_NUMERO"]) en lugar de distinct()
#           Evita fan-out en joins downstream cuando un mismo USR_NUMERO tiene
#           variaciones en USR_NOMBRE (espacios, tildes, mayúsculas distintas).
#           Impacto: el control de observaciones contaba 41.061 partes en vez
#           de los 38.976 reales, distorsionando todos los KPIs.
#
#   [FIX-G] Cruce B: coalesce(ORD_FECHA_FIN, ORD_PRIMER_ASIGNACION) para no-CE.
#           Órdenes con resultado EM/N/P frecuentemente tienen ORD_FECHA_FIN=NULL
#           → datediff NULL → filtro <=15 falla → caen en "Sin Orden Asociada"
#           cuando deberían ser "No Corresponde TOR CE". Bug documentado desde v27.0.
#
#   [FIX-H] MERGE key: ID_PARTE_HASH en lugar de ID_ARCHIVO + ID_EXTERNO.
#           ID_EXTERNO de COOPLYF se genera con monotonically_increasing_id (volátil
#           entre ejecuciones). Con el MERGE viejo, reprocesar COOPLYF generaba
#           duplicados en lugar de actualizar. ID_PARTE_HASH es SHA256 determinista.
#
# CAMBIOS HEREDADOS DE v27.2:
#
#   [FIX-A] Cruce A filtrado por contratista (BUG CRÍTICO)
#           El Cruce A ya no captura órdenes CE de la contratista equivocada.
#           Se construye df_ord_ce_contratista filtrando dim_ord para que solo
#           contenga CE cuyo USR_NUMERO_EJEC_ORD pertenezca al pool de usuarios
#           de la contratista que se está procesando.
#           Casos corregidos: registros de COOPLYF apareciendo bajo CONECTAR
#           (imgs 1, 3, 5 del análisis de SIGEC).
#
#   [FIX-B] Cruce C filtrado por contratista
#           El rescate por número de medidor también usa df_ord_ce_contratista,
#           evitando que Cruce C herede el usuario de la última CE ejecutada
#           por una contratista distinta (casos 2 y 4 del análisis).
#
#   [FIX-C] TOR_DETECTADO — trazabilidad del tipo de ordenativo
#           Cuando un parte cae en "No Corresponde TOR CE" (Fuera de Alcance),
#           se guarda el tipo de ordenativo real detectado en SIGEC (IC, CX, MP,
#           RX, etc.) en la nueva columna TOR_DETECTADO de la fact table.
#           Esto permite en Power BI filtrar/agrupar los fuera de alcance por
#           tipo de ordenativo y justificar su exclusión ante la auditoría.
#           Para todos los demás estados TOR_DETECTADO = null.
#
#   [NEW]   dim_archivo: normalización de ORIGEN_ARCHIVO (heredado de v26.0).
#
# REGLAS DE NEGOCIO v27.0:
#   - Solo órdenes CE de origen PROTELEM con resultado E/IN/D/EH/EI son válidas.
#   - La CE válida debe pertenecer a la MISMA contratista que el archivo.
#   - Partes con TO != CE dentro de la ventana → Fuera de Alcance con TOR_DETECTADO.
#   - Ventana temporal: ABS(fecha_parte - ORD_FECHA_FIN) <= 15 días.
# =============================================================================


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 1 — IMPORTS Y CONFIGURACIÓN GLOBAL
# ═════════════════════════════════════════════════════════════════════════════

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.functions import (
    col, when, lit, abs, datediff, row_number, coalesce,
    monotonically_increasing_id, to_date, desc, current_timestamp,
    broadcast, sha2, concat_ws, trim,
)
from pyspark.sql.types import StructType, StructField, IntegerType, StringType
from delta.tables import DeltaTable

# -----------------------------------------------------------------------------
# Parámetros del pipeline
# -----------------------------------------------------------------------------
LISTA_CONTRATISTAS = ["CONECTAR", "COOPLYF"]
DIAS_TOLERANCIA    = 15

# Tablas de entrada (maestros y staging)
TABLA_MAESTRA_COD = "datos_generales.mapeo_codigos_master"
TABLA_EQP_SRV     = "datos_generales.eqp_equipos_ultimos_10"
TABLA_DIM_ORD     = "datos_generales.dim_ord"
TABLA_USUARIOS    = "datos_generales.usuarios_gral"
TABLA_STOCK_SIGEC = "datos_generales.dim_stk_stock_equipos"

# Tablas de salida
TABLA_FACT        = "datos_generales.fact_partes_diarios_full"
TABLA_DIM_ARCHIVO = "datos_generales.dim_archivo_bi"

# -----------------------------------------------------------------------------
# [H-08] Trazas centralizadas — única fuente de verdad
# Agregar una traza nueva aquí la propaga a todo el pipeline automáticamente.
# -----------------------------------------------------------------------------
TRAZAS_OK = [
    "Original OK",
    "Corregido Nro EQP Invertidos",
    "Corregido Nro Medidor",
    "Corregido Sumi",
    "Corregido Medidor Vacio",
]
TRAZAS_OCR = [
    "Corregido Sumi Nro EQP",
]
TRAZAS_RECHAZO = [
    "No Corresponde TOR CE",
    "Sin Orden Asociada",
    "Error Sumi Sin Nro Medidor",
    "Error Sumi Y Nro Medidor",
    "Repetido X Sumi",
    "Otro Origen",
]
TRAZAS_DESCARTE_TECNICO = [
    "No Corresponde TOR CE",
    "Sin Orden Asociada",
    "Error Sumi Sin Nro Medidor",
    "Error Sumi Y Nro Medidor",
    "Otro Origen",
]
TRAZAS_CORRECCION_MEDIDOR = [
    "Corregido Nro EQP Invertidos",
    "Corregido Nro Medidor",
    "Corregido Sumi Nro EQP",
    "Corregido Medidor Vacio",
]

# Schema final de la fact table — columnas en orden canónico
COLS_FACT = [
    "ID_EXTERNO", "FECHA", "ESTADO_PROCESO", "ID_ARCHIVO",
    "SRV_CODIGO", "SUMINISTRO_RAW", "NRO_EQP_COLOCADO", "NRO_EQP_RETIRADO",
    "CODIGO_CONTRATISTA", "CODIGO_EPEC", "ORD_NRO", "ORD_FECHA_FIN", "es_pagable",
    "ID_EMPRESA", "ID_ESTADO", "TIMESTAMP_ETL", "SEC_CODIGO_ORIGEN",
    "USR_ID", "ID_TRAZA",
    "ID_PARTE_HASH",       # Clave estable para el módulo de correcciones
    "FUE_CORREGIDO",       # Flag de override de auditoría para Power BI
    "ORD_TIPO_DETECTADO",  # [v27] Tipo de ordenativo del parte (IC/CX/MP/…).
                           # Poblado solo en "No Corresponde TOR CE"; NULL en el resto.
                           # Permite desglosar en Power BI por qué tipo de orden
                           # fue el motivo de exclusión de cada parte fuera de alcance.
]


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 2 — DIMENSIONES ESTÁTICAS Y dim_archivo
# ═════════════════════════════════════════════════════════════════════════════

print(f"\n{'='*80}")
print("⚙️  GENERANDO DIMENSIONES BI...")
print(f"{'='*80}")

# Dimensión Empresas
spark.createDataFrame(
    [(1, "CONECTAR"), (2, "COOPLYF")],
    ["ID_EMPRESA", "EMPRESA"],
).write.format("delta").mode("overwrite").saveAsTable("datos_generales.dim_empresa_bi")

# Dimensión Estados
spark.createDataFrame(
    [(1, "Aprobado"), (2, "Revisión"), (3, "Rechazado"), (4, "Fuera de Alcance")],
    ["ID_ESTADO", "DESC_ESTADO"],
).write.format("delta").mode("overwrite").saveAsTable("datos_generales.dim_estado_bi")

# Dimensión Traza de Calidad
spark.createDataFrame(
    [
        (1,  "Original OK"),
        (2,  "Corregido Nro EQP Invertidos"),
        (3,  "Corregido Nro Medidor"),
        (4,  "Corregido Sumi"),
        (5,  "Corregido Sumi Nro EQP"),
        (6,  "No Corresponde TOR CE"),
        (7,  "Sin Orden Asociada"),
        (8,  "Error Sumi Sin Nro Medidor"),
        (9,  "Error Sumi Y Nro Medidor"),
        (10, "Repetido X Sumi"),
        (11, "Otro Origen"),
        (12, "Corregido Medidor Vacio"),
    ],
    ["ID_TRAZA", "DESC_TRAZA"],
).write.format("delta").mode("overwrite").saveAsTable("datos_generales.dim_traza_calidad_bi")

# Dimensión Usuarios (dinámica desde la fuente)
# [FIX] dropDuplicates por USR_NUMERO en lugar de distinct() sobre ambas columnas.
# Si un mismo USR_NUMERO tiene variaciones en USR_NOMBRE (espacios, tildes),
# distinct() genera filas duplicadas y provoca fan-out en joins downstream.
spark.table("datos_generales.usuarios_gral") \
    .select("USR_NUMERO", "USR_NOMBRE") \
    .dropDuplicates(["USR_NUMERO"]) \
    .write.format("delta").mode("overwrite").saveAsTable("datos_generales.dim_usuarios_bi")

# -----------------------------------------------------------------------------
# [NEW] dim_archivo_bi — Normalización de ORIGEN_ARCHIVO
# -----------------------------------------------------------------------------
# PROBLEMA RESUELTO: ORIGEN_ARCHIVO es un string largo (ej. path ABFS o nombre
# de Excel) que se repetía en CADA fila de la fact table. Con miles de partes
# diarios por archivo, eso implica almacenar el mismo string miles de veces.
#
# SOLUCIÓN: Generamos un ID_ARCHIVO (entero) por cada nombre de archivo único
# y lo almacenamos como clave foránea en la fact table. Power BI hace el join
# con esta dimensión para mostrar el nombre en los reportes.
#
# IDEMPOTENCIA: La dimensión se construye de forma acumulativa — cada ejecución
# agrega los archivos nuevos del lote y respeta los IDs ya asignados a los
# archivos históricos. Los IDs nunca se reasignan.
# -----------------------------------------------------------------------------

def actualizar_dim_archivo(nombres_nuevos: list) -> dict:
    """
    Recibe una lista de nombres de archivo del lote actual.
    Devuelve un dict {nombre_archivo: ID_ARCHIVO} con los IDs a usar
    (existentes para los ya conocidos, nuevos para los recién llegados).
    Persiste la dimensión actualizada en TABLA_DIM_ARCHIVO.
    """
    if not nombres_nuevos:
        return {}

    # Cargar dimensión existente (si ya existe la tabla)
    if spark.catalog.tableExists(TABLA_DIM_ARCHIVO):
        df_existente = spark.table(TABLA_DIM_ARCHIVO)
        max_id = df_existente.agg(F.max("ID_ARCHIVO")).collect()[0][0] or 0
        existentes = {
            r["NOMBRE_ARCHIVO"]: r["ID_ARCHIVO"]
            for r in df_existente.collect()
        }
    else:
        max_id     = 0
        existentes = {}

    # Asignar IDs solo a los archivos realmente nuevos
    nuevos = [n for n in nombres_nuevos if n not in existentes]
    nuevos_con_id = {
        nombre: max_id + idx + 1
        for idx, nombre in enumerate(sorted(nuevos))
    }

    # Mapa combinado (histórico + nuevos)
    mapa_completo = {**existentes, **nuevos_con_id}

    # Persistir solo si hay archivos nuevos
    if nuevos_con_id:
        df_dim_nueva = spark.createDataFrame(
            [(v, k) for k, v in mapa_completo.items()],
            ["ID_ARCHIVO", "NOMBRE_ARCHIVO"],
        )
        df_dim_nueva.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .saveAsTable(TABLA_DIM_ARCHIVO)
        print(f"   dim_archivo_bi actualizada: {len(nuevos_con_id)} archivo(s) nuevo(s) registrado(s).")
    else:
        print("   dim_archivo_bi sin cambios (todos los archivos del lote ya estaban registrados).")

    return mapa_completo

print("✅ Dimensiones listas para Power BI.")


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 3 — MOTOR CORE (WATERFALL v26.0)
# ═════════════════════════════════════════════════════════════════════════════

def ejecutar_core_para_contratista(contratista: str, mapa_archivos: dict, df_dim_traza) -> "DataFrame | None":
    """
    Ejecuta el waterfall completo para una contratista y devuelve un DataFrame
    ya normalizado al schema de COLS_FACT, listo para el MERGE sobre la fact table.

    Parámetros:
        contratista  : "CONECTAR" o "COOPLYF"
        mapa_archivos: dict {nombre_archivo: ID_ARCHIVO} para normalizar ORIGEN_ARCHIVO
        df_dim_traza : DataFrame de la dimensión de trazas (se pasa para no releerla)

    Retorna:
        DataFrame con el schema de COLS_FACT, o None si no hay datos.

    [H-07] Ya no escribe tablas intermedias de staging. La consolidación ocurre
           en memoria — el caller acumula los DataFrames y hace un único MERGE.
    """
    sufijo        = contratista.lower()
    id_empresa    = 1 if contratista == "CONECTAR" else 2
    TABLA_INPUT_PD = f"datos_generales.pd_{sufijo}_aux"

    print(f"\n{'='*80}\nINICIANDO PROCESO PARA: {contratista}\n{'='*80}")

    if not spark.catalog.tableExists(TABLA_INPUT_PD):
        print(f"⚠️  Tabla {TABLA_INPUT_PD} no existe. Saltando.")
        return None

    df_pd = spark.table(TABLA_INPUT_PD)

    # [H-02] limit(1) en lugar de count() — no materializa todo el DF
    if df_pd.limit(1).count() == 0:
        print(f"⚠️  Tabla {TABLA_INPUT_PD} vacía. Saltando.")
        return None

    if "ID_Externo" not in df_pd.columns:
        df_pd = df_pd.withColumn("ID_Externo", monotonically_increasing_id().cast("string"))

    # ── CARGA DE MAESTROS ────────────────────────────────────────────────────
    # [H-04] Las tablas pequeñas se envuelven con broadcast() para evitar shuffle.
    #        df_tecnica no se broadcast — puede ser grande según el parque de medidores.
    #        df_fases: evaluar tamaño. Si dim_stk_stock_equipos < ~100MB → agregar broadcast().
    df_maestro_cod = broadcast(
        spark.table(TABLA_MAESTRA_COD).filter(col("CONTRATISTA") == contratista)
    )
    df_tecnica = spark.table(TABLA_EQP_SRV).select(
        col("SRV_CODIGO").cast("long").alias("srv_tecnico"),
        col("STE_NUMERO_ULTIMO").cast("double").alias("db_colocado"),
        col("STE_NUMERO_ANTERIOR_1").cast("double").alias("db_retirado"),
    )

    # [FIX-A/B/C] df_usr se amplía para incluir CONTRATISTA.
    # df_usr_pool: pool de USR_NUMERO que pertenecen a la contratista que se procesa.
    # Se usa como filtro en Cruce A, B y C para que ningún cruce capture una orden
    # cuyo ejecutante pertenece a otra contratista.
    df_usr = broadcast(
        spark.table(TABLA_USUARIOS).select("USR_NUMERO", "USR_NOMBRE", "SEC_CODIGO")
    )
    df_usr_pool = broadcast(
        df_usr.filter(col("SEC_CODIGO") == contratista).select("USR_NUMERO")
    )

    df_fases = spark.table(TABLA_STOCK_SIGEC).select(
        col("ste_numero").cast("double").alias("MEDIDOR_STOCK"),
        col("ste_fases").alias("FASE_SIGEC"),
    ).distinct()

    cols_dim_ord    = spark.table(TABLA_DIM_ORD).columns
    col_origen_expr = col("SEC_CODIGO_ORIGEN") if "SEC_CODIGO_ORIGEN" in cols_dim_ord \
                      else lit(None).cast("string").alias("SEC_CODIGO_ORIGEN")
    col_usr_expr    = col("USR_NUMERO_EJEC_ORD") if "USR_NUMERO_EJEC_ORD" in cols_dim_ord \
                      else lit(None).cast("long").alias("USR_NUMERO_EJEC_ORD")

    # Universo completo de órdenes CE con resultado válido.
    # NO filtrado por contratista aún — el filtro se aplica después via df_usr_pool
    # para poder reutilizar este DF si se necesita auditoría cruzada en el futuro.
    df_ord_ce = spark.table(TABLA_DIM_ORD) \
        .filter((col("TOR_CODIGO") == "CE") & col("ORD_RESULTADO").isin(["E", "IN", "D", "EH", "EI"])) \
        .select(
            col("ORD_NUMERO").alias("NUMERO_ORDEN"),
            col("SRV_CODIGO").cast("long").alias("ord_suministro"),
            col("ORD_FECHA_FIN"),
            to_date(col("ORD_FECHA_FIN")).alias("ord_fecha_ref"),
            col_origen_expr,
            col_usr_expr.alias("ID_OPERARIO_RAW"),
        )

    # [FIX-A] df_ord_ce_propia: solo CE cuyo ejecutante pertenece a ESTA contratista.
    # Elimina el falso match donde CONECTAR capturaba una CE de COOPLYF (o viceversa).
    df_ord_ce_propia = df_ord_ce.join(
        df_usr_pool,
        df_ord_ce.ID_OPERARIO_RAW == df_usr_pool.USR_NUMERO,
        "inner",
    ).drop("USR_NUMERO")

    # Universo completo de órdenes no-CE con resultado válido.
    # [v27.2] Sin filtro de contratista: Cruce B solo clasifica, no asigna usuario.
    # ORD_NUMERO agregado para trazabilidad en ORD_NRO. df_ord_rechazo_propia eliminado.
    # [FIX] coalesce(ORD_FECHA_FIN, ORD_PRIMER_ASIGNACION): órdenes con resultado
    # EM/N/P frecuentemente tienen ORD_FECHA_FIN=NULL → datediff devuelve NULL →
    # filtro <= 15 falla silenciosamente → caen en "Sin Orden Asociada" cuando
    # deberían ser "No Corresponde TOR CE". Usando PRIMER_ASIGNACION como fallback
    # se capturan correctamente.
    df_ord_rechazo_tor = spark.table(TABLA_DIM_ORD) \
        .filter((col("TOR_CODIGO") != "CE")) \
        .select(
            col("ORD_NUMERO").alias("NUMERO_ORDEN"),
            col("SRV_CODIGO").cast("long").alias("ord_suministro"),
            col("TOR_CODIGO").alias("TIPO_ORDEN_DETECTADO"),
            coalesce(to_date(col("ORD_FECHA_FIN")), to_date(col("ORD_FECHA_INICIO"))).alias("ord_fecha_ref"),            col_origen_expr,
        )

    # ── WATERFALL ────────────────────────────────────────────────────────────
    print("   Ejecutando lógica de cruce y rescate...")

    # [H-09] _row_id: generado por monotonically_increasing_id(). Estable dentro
    #         de este job pero volátil entre ejecuciones. Válido solo como clave
    #         de join interno. Para identificación externa persistente → ID_PARTE_HASH.
    df_base = df_pd \
        .withColumn("_row_id", monotonically_increasing_id()) \
        .withColumn("Suministro_Norm", col("Suministro").cast("long")) \
        .withColumn("medidorColocado",  col("medidorColocado").cast("double")) \
        .withColumn("medidorRetirado",  col("medidorRetirado").cast("double")) \
        .withColumn("Fecha_Norm",       to_date(col("Fecha")))

    # [H-01] Cache de df_base: se referencia en 5 joins del waterfall.
    #         Sin cache → Spark re-escanea el input completo en cada uno.
    df_base.cache()

    CLAVE_JOIN = ["_row_id"]
    w_match    = Window.partitionBy("_row_id").orderBy(col("dias_diff").asc())

    # ── Cruce A: Suministro + Orden CE ────────────────────────────────────
    # [FIX-A] Usa df_ord_ce_propia: solo CE cuyo ejecutante es de ESTA contratista.
    df_candidatos_A = df_base \
        .join(df_ord_ce_propia, col("Suministro_Norm") == col("ord_suministro"), "inner") \
        .withColumn("dias_diff", abs(datediff(col("Fecha_Norm"), col("ord_fecha_ref")))) \
        .filter(col("dias_diff") <= DIAS_TOLERANCIA) \
        .withColumn("rank", row_number().over(w_match)).filter(col("rank") == 1) \
        .select(
            col("_row_id"), col("NUMERO_ORDEN"),
            col("ord_suministro").alias("Suministro_Final"),
            col("ORD_FECHA_FIN"), col("SEC_CODIGO_ORIGEN"), col("ID_OPERARIO_RAW"),
        )

    df_analisis_A = df_candidatos_A \
        .join(df_tecnica, col("Suministro_Final") == col("srv_tecnico"), "left") \
        .join(df_base.select("_row_id", "medidorColocado", "medidorRetirado"), "_row_id", "inner")

    df_resultados_A = df_analisis_A.withColumn("TRAZA_CALIDAD",
        when(col("medidorColocado").isNull(),
             lit("Corregido Medidor Vacio"))
        .when(
            (col("medidorColocado") == col("db_colocado")) &
            (col("medidorRetirado") == col("db_retirado")),
            lit("Original OK"))
        .when(
            (col("medidorColocado") == col("db_retirado")) &
            (col("medidorRetirado") == col("db_colocado")),
            lit("Corregido Nro EQP Invertidos"))
        .otherwise(lit("Corregido Nro Medidor"))
    ).withColumn(
        # [NEW] ORD_TIPO_DETECTADO: NULL en aprobados/OCR — el ordenativo es CE por definición
        "ORD_TIPO_DETECTADO", lit(None).cast("string")
    ).select(
        "_row_id", "NUMERO_ORDEN", "Suministro_Final", "ORD_FECHA_FIN",
        "TRAZA_CALIDAD", "db_colocado", "db_retirado",
        "SEC_CODIGO_ORIGEN", "ID_OPERARIO_RAW", "ORD_TIPO_DETECTADO",
    )

    df_pendientes_A = df_base.join(df_resultados_A, CLAVE_JOIN, "left_anti")

    # ── Cruce B: Descarte por tipo de orden distinta de CE ────────────────
    # [v27.2] Usa df_ord_rechazo_tor (global): captura no-CE de cualquier ejecutante.
    # Antes usaba df_ord_rechazo_propia (filtrada por contratista), lo que dejaba
    # caer en "Sin Orden Asociada" a partes cuya orden no-CE era de la otra contratista.
    df_match_otros = df_pendientes_A \
        .join(df_ord_rechazo_tor, col("Suministro_Norm") == col("ord_suministro"), "inner") \
        .withColumn("dias_diff", abs(datediff(col("Fecha_Norm"), col("ord_fecha_ref")))) \
        .filter(col("dias_diff") <= DIAS_TOLERANCIA) \
        .withColumn("rank", row_number().over(w_match)).filter(col("rank") == 1) \
        .select(
            col("_row_id"),
            lit("No Corresponde TOR CE").alias("TRAZA_CALIDAD"),
            col("SEC_CODIGO_ORIGEN"),
            col("NUMERO_ORDEN"),          # [v27.2] nro de ordenativo → ORD_NRO
            col("TIPO_ORDEN_DETECTADO"),  # IC / CX / MP / RX / etc.
        )

    df_pendientes_Reales = df_pendientes_A.join(df_match_otros, CLAVE_JOIN, "left_anti")

    # ── Cruce C: Rescate por número de medidor (suministro mal anotado) ───
    df_rescate_colocado = df_pendientes_Reales \
        .filter(col("medidorColocado").isNotNull()) \
        .join(
            df_tecnica.select(
                col("db_colocado").alias("eqp_medidor"),
                col("srv_tecnico").alias("eqp_suministro_real"),
                col("db_retirado").alias("eqp_retirado_esperado"),
            ),
            col("medidorColocado") == col("eqp_medidor"), "inner",
        ) \
        .select(
            col("_row_id"), col("eqp_suministro_real"),
            col("eqp_retirado_esperado"), col("eqp_medidor").alias("db_colocado"),
        )

    df_rescate_retirado = df_pendientes_Reales \
        .filter(col("medidorColocado").isNull() & col("medidorRetirado").isNotNull()) \
        .join(
            df_tecnica.select(
                col("db_retirado").alias("eqp_retirado_match"),
                col("srv_tecnico").alias("eqp_suministro_real"),
                col("db_colocado").alias("eqp_colocado_inferido"),
            ),
            col("medidorRetirado") == col("eqp_retirado_match"), "inner",
        ) \
        .select(
            col("_row_id"), col("eqp_suministro_real"),
            col("eqp_retirado_match").alias("eqp_retirado_esperado"),
            col("eqp_colocado_inferido").alias("db_colocado"),
        )

    df_rescate_con_orden = df_rescate_colocado.unionByName(df_rescate_retirado) \
        .join(df_ord_ce_propia, col("eqp_suministro_real") == col("ord_suministro"), "inner") \
        .join(
            df_base.select("_row_id", "Fecha_Norm", "medidorColocado", "medidorRetirado"),
            "_row_id", "inner",
        ) \
        .withColumn("dias_diff", abs(datediff(col("Fecha_Norm"), col("ord_fecha_ref")))) \
        .filter(col("dias_diff") <= DIAS_TOLERANCIA) \
        .withColumn("rank", row_number().over(w_match)).filter(col("rank") == 1) \
        .select(
            col("_row_id"), col("NUMERO_ORDEN"),
            col("eqp_suministro_real").alias("Suministro_Final"),
            col("ORD_FECHA_FIN"), col("eqp_retirado_esperado"),
            col("medidorRetirado").alias("excel_retirado"),
            col("db_colocado"), col("SEC_CODIGO_ORIGEN"), col("ID_OPERARIO_RAW"),
        )

    df_resultados_B = df_rescate_con_orden.withColumn("TRAZA_CALIDAD",
        when(col("excel_retirado") == col("eqp_retirado_esperado"), lit("Corregido Sumi"))
        .otherwise(lit("Corregido Sumi Nro EQP"))
    ).withColumn(
        # [NEW] ORD_TIPO_DETECTADO: NULL en rescates — el ordenativo es CE por definición
        "ORD_TIPO_DETECTADO", lit(None).cast("string")
    ).select(
        "_row_id", "NUMERO_ORDEN", "Suministro_Final", "ORD_FECHA_FIN",
        "TRAZA_CALIDAD", "db_colocado",
        col("eqp_retirado_esperado").alias("db_retirado"),
        "SEC_CODIGO_ORIGEN", "ID_OPERARIO_RAW", "ORD_TIPO_DETECTADO",
    )

    # Estandarizar el schema de df_match_otros para el union final.
    # TIPO_ORDEN_DETECTADO ya viene poblado desde Cruce B — se renombra a
    # ORD_TIPO_DETECTADO para que unionByName sea consistente con df_resultados_A/B.
    # [v27.2] NUMERO_ORDEN ya viene poblado desde df_match_otros — NO se pisa con NULL.
    df_otros_std = df_match_otros \
        .withColumnRenamed("TIPO_ORDEN_DETECTADO", "ORD_TIPO_DETECTADO") \
        .withColumn("Suministro_Final", lit(None).cast("long")) \
        .withColumn("ORD_FECHA_FIN",    lit(None).cast("string")) \
        .withColumn("db_colocado",      lit(None).cast("double")) \
        .withColumn("db_retirado",      lit(None).cast("double")) \
        .withColumn("ID_OPERARIO_RAW",  lit(None).cast("long"))

    # ── Ensamblado final del waterfall ────────────────────────────────────
    df_full = df_base.join(
        df_resultados_A.unionByName(df_resultados_B).unionByName(df_otros_std),
        CLAVE_JOIN, "left",
    )

    df_full = df_full \
        .withColumn("TRAZA_CALIDAD", coalesce(
            col("TRAZA_CALIDAD"),
            when(col("Suministro_Norm").isNotNull(),  lit("Sin Orden Asociada"))
            .when(col("medidorColocado").isNull(),     lit("Error Sumi Sin Nro Medidor"))
            .otherwise(                                lit("Error Sumi Y Nro Medidor"))
        )) \
        .withColumn("Suministro_Final", coalesce(col("Suministro_Final"), col("Suministro_Norm"))) \
        .withColumn(
            # [NEW] Para huérfanos reales (Sin Orden Asociada / Error Sumi…),
            # ORD_TIPO_DETECTADO también es NULL — no encontramos ninguna orden.
            "ORD_TIPO_DETECTADO", coalesce(col("ORD_TIPO_DETECTADO"), lit(None).cast("string"))
        )

    # Regla de origen: si el parte no proviene de PROTELEM → Otro Origen
    df_full = df_full.withColumn("TRAZA_CALIDAD",
        when(
            col("SEC_CODIGO_ORIGEN").isNotNull() & (col("SEC_CODIGO_ORIGEN") != "PROTELEM"),
            lit("Otro Origen"),
        ).otherwise(col("TRAZA_CALIDAD"))
    )

    # Inyección de medidores correctos para las trazas que requieren corrección
    df_full_clean = df_full \
        .withColumn("medidorColocado",
            when(col("TRAZA_CALIDAD").isin(TRAZAS_CORRECCION_MEDIDOR), col("db_colocado"))
            .otherwise(col("medidorColocado"))
        ) \
        .withColumn("medidorRetirado",
            when(col("TRAZA_CALIDAD").isin(TRAZAS_CORRECCION_MEDIDOR), col("db_retirado"))
            .otherwise(col("medidorRetirado"))
        )

    # ── Enriquecimiento: usuarios + fase heurística + maestro de precios ──
    print("   Enriqueciendo con usuarios, fases y maestro de precios...")

    # [H-04] df_usr: broadcast (tabla pequeña y estática).
    # Se hace join por USR_NUMERO pero solo se retiene USR_NOMBRE — CONTRATISTA
    # fue necesaria para construir df_usr_pool pero no debe llegar a la fact table.
    df_enriched = df_full_clean \
        .join(
            df_usr.select("USR_NUMERO", "USR_NOMBRE"),
            df_full_clean.ID_OPERARIO_RAW == df_usr.USR_NUMERO,
            "left",
        ) \
        .withColumnRenamed("ID_OPERARIO_RAW", "USR_ID")

    # Fase heurística: stock → si no existe, infiere por código de tarea
    # df_fases: evaluar tamaño de dim_stk_stock_equipos. Si < ~100MB → broadcast().
    df_con_fase = df_enriched \
        .join(df_fases, df_enriched.medidorColocado == df_fases.MEDIDOR_STOCK, "left") \
        .withColumn("FASE_DESCUBIERTA", coalesce(
            col("FASE_SIGEC"),
            when(col("codTiposManoObra").like("%01%"), lit("TRI")).otherwise(lit("MON")),
        ))

    # [H-04] df_maestro_cod: broadcast (solo los códigos de la contratista actual)
    df_con_precio = df_con_fase.join(
        df_maestro_cod,
        (col("codTiposManoObra") == col("COD_CONTRATISTA_INDIVIDUAL")) &
        ((col("FASE_DESCUBIERTA") == col("FASE")) | (col("FASE") == "AMBAS")),
        "left",
    )

    # ── Deduplicación por suministro ──────────────────────────────────────
    df_para_analizar      = df_con_precio.filter(~col("TRAZA_CALIDAD").isin(TRAZAS_DESCARTE_TECNICO))
    df_descartes_directos = df_con_precio.filter( col("TRAZA_CALIDAD").isin(TRAZAS_DESCARTE_TECNICO))

    # [H-03] Cache antes del split y la deduplicación. Evita que el plan completo
    #         del waterfall se re-ejecute dos veces (una para dedup, una para el select final).
    df_con_precio.cache()

    # [H-03] Sin if count() > 0: un unionByName con un DF vacío es válido en Spark
    w_deduplica = Window.partitionBy("Suministro_Final").orderBy(
        col("prioridad_cod").desc(), col("Fecha").desc(), col("_row_id").desc()
    )
    df_dedup = df_para_analizar.withColumn(
        "prioridad_cod", when(col("COD_EPEC") != "11", lit(1)).otherwise(lit(0))
    )
    df_deduplica = df_dedup \
        .withColumn("posicion", row_number().over(w_deduplica)) \
        .withColumn("TRAZA_CALIDAD",
            when(col("posicion") > 1, lit("Repetido X Sumi")).otherwise(col("TRAZA_CALIDAD"))
        ) \
        .drop("prioridad_cod", "posicion")

    df_final = df_deduplica.unionByName(df_descartes_directos)

    # ── Normalización al schema de la fact table ──────────────────────────
    # Asignar estado e ID_EMPRESA
    df_con_estado = df_final \
        .withColumn("ID_ESTADO_BASE",
            when(col("TRAZA_CALIDAD").isin(TRAZAS_OK),     lit(1))
            .when(col("TRAZA_CALIDAD").isin(TRAZAS_OCR),   lit(2))
            .when(col("TRAZA_CALIDAD").isin(["No Corresponde TOR CE", "Otro Origen"]), lit(4))
            .otherwise(lit(3))  # TRAZAS_RECHAZO
        ) \
        .withColumn("ESTADO_PROCESO",
            when(col("ID_ESTADO_BASE") == 1, lit("Aprobado"))
            .when(col("ID_ESTADO_BASE") == 2, lit("Revisión"))
            .when(col("ID_ESTADO_BASE") == 4, lit("Fuera de Alcance"))
            .otherwise(lit("Rechazado"))
        ) \
        .withColumn("es_pagable",
            when(col("ID_ESTADO_BASE") == 1, lit(1)).otherwise(lit(0))
        ) \
        .withColumnRenamed("ID_ESTADO_BASE", "ID_ESTADO") \
        .withColumn("ID_EMPRESA", lit(id_empresa)) \
        .withColumn("TIMESTAMP_ETL", current_timestamp())

    # [NEW] Reemplazar ORIGEN_ARCHIVO string por ID_ARCHIVO (int)
    # mapa_archivos viene precalculado desde la celda de dimensiones
    mapa_expr = F.create_map(*[
        item for nombre, id_arch in mapa_archivos.items()
        for item in (lit(nombre), lit(id_arch))
    ])
    df_con_archivo = df_con_estado.withColumn(
        "ID_ARCHIVO", mapa_expr[col("ORIGEN_ARCHIVO")]
    )

    # [H-04] df_dim_traza: 12 filas — siempre broadcastable
    df_con_traza = df_con_archivo.join(
        broadcast(df_dim_traza),
        df_con_archivo.TRAZA_CALIDAD == df_dim_traza.DESC_TRAZA,
        "left",
    )

    # Suministro original como string para SUMINISTRO_RAW
    df_con_traza = df_con_traza \
        .withColumn("SUMINISTRO_RAW", col("Suministro").cast("string"))

    # ID_PARTE_HASH determinista — clave estable para el módulo de correcciones
    df_con_hash = df_con_traza.withColumn(
        "ID_PARTE_HASH",
        sha2(
            concat_ws("|",
                col("ORIGEN_ARCHIVO"),
                col("Suministro_Final").cast("string"),
                to_date(col("Fecha")).cast("string"),
                coalesce(col("medidorColocado").cast("string"), lit("NULL")),
                col("codTiposManoObra"),
            ),
            256,
        )
    ).withColumn("FUE_CORREGIDO", lit(False))

    # Selección final al schema canónico de la fact table
    df_normalizado = df_con_hash.select(
        col("ID_Externo").alias("ID_EXTERNO"),
        to_date(col("Fecha")).alias("FECHA"),
        col("ESTADO_PROCESO"),
        col("ID_ARCHIVO"),
        col("Suministro_Final").cast("long").alias("SRV_CODIGO"),
        col("SUMINISTRO_RAW"),
        col("medidorColocado").cast("double").alias("NRO_EQP_COLOCADO"),
        col("medidorRetirado").cast("double").alias("NRO_EQP_RETIRADO"),
        col("codTiposManoObra").cast("string").alias("CODIGO_CONTRATISTA"),
        col("COD_EPEC").cast("long").alias("CODIGO_EPEC"),
        col("NUMERO_ORDEN").alias("ORD_NRO"),
        col("ORD_FECHA_FIN"),
        col("es_pagable"),
        col("ID_EMPRESA"),
        col("ID_ESTADO"),
        col("TIMESTAMP_ETL"),
        col("SEC_CODIGO_ORIGEN"),
        col("USR_ID"),
        col("ID_TRAZA"),
        col("ID_PARTE_HASH"),
        col("FUE_CORREGIDO"),
        col("ORD_TIPO_DETECTADO"),  # [NEW v27] NULL excepto en "No Corresponde TOR CE"
    )

    # Liberar caches del waterfall antes de retornar
    df_con_precio.unpersist()
    df_base.unpersist()

    # IMPORTANTE: NO hacemos TRUNCATE aquí.
    # df_normalizado es un plan LAZY — Spark no lee el staging hasta que el caller
    # ejecute el write/MERGE. Si truncamos ahora, el plan no encontrará datos.
    # El TRUNCATE se ejecuta en la Celda 4, DESPUÉS de confirmar el write.
    return df_normalizado, TABLA_INPUT_PD


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 4 — EJECUCIÓN DEL CORE Y MERGE EN LA FACT TABLE
# ═════════════════════════════════════════════════════════════════════════════

print(f"\n{'='*80}")
print("🚀 INICIANDO PIPELINE CORE v27.3")
print(f"{'='*80}")

# Paso 1: Descubrir los nombres de archivo del lote actual (antes de procesar)
# para poder actualizar dim_archivo_bi con los nuevos IDs antes del waterfall.
nombres_lote = []
for contratista in LISTA_CONTRATISTAS:
    tabla_input = f"datos_generales.pd_{contratista.lower()}_aux"
    if spark.catalog.tableExists(tabla_input):
        nombres = [
            r["ORIGEN_ARCHIVO"]
            for r in spark.table(tabla_input)
                .select("ORIGEN_ARCHIVO")
                .filter(col("ORIGEN_ARCHIVO").isNotNull())
                .distinct()
                .collect()
        ]
        nombres_lote.extend(nombres)

nombres_lote = list(set(nombres_lote))  # Deduplicar entre contratistas

# Paso 2: Actualizar dim_archivo_bi y obtener el mapa {nombre → ID}
mapa_archivos = actualizar_dim_archivo(nombres_lote)

# Paso 3: Cargar dim_traza una sola vez (se pasa a cada invocación del core)
df_dim_traza_global = spark.table("datos_generales.dim_traza_calidad_bi") \
    .select("ID_TRAZA", "DESC_TRAZA")

# Paso 4: Ejecutar el waterfall por contratista y acumular en memoria
# [H-07] Sin escrituras intermedias — todo ocurre en memoria hasta el MERGE final
df_lote_completo  = None
stagings_a_limpiar = []   # Se truncan DESPUÉS del write, no antes

for contratista in LISTA_CONTRATISTAS:
    resultado = ejecutar_core_para_contratista(contratista, mapa_archivos, df_dim_traza_global)
    if resultado is not None:
        df_resultado, tabla_staging = resultado
        stagings_a_limpiar.append(tabla_staging)
        df_lote_completo = df_resultado if df_lote_completo is None \
                           else df_lote_completo.unionByName(df_resultado)

# Paso 5: MERGE único sobre la fact table
# [H-05] MERGE Delta: atómico, sin ventana de inconsistencia, sin collect() al driver.
#         Clave de merge: ID_ARCHIVO + ID_EXTERNO identifica unívocamente cada parte
#         dentro de un archivo. Si el mismo archivo se reprocesa, actualiza en lugar
#         de duplicar (idempotencia garantizada).
#
# DETECCIÓN DE SCHEMA VIEJO: Si la fact table existe pero tiene ORIGEN_ARCHIVO
# en lugar de ID_ARCHIVO (schema pre-v26), el MERGE fallaría con AnalysisException.
# En ese caso se hace DROP + overwrite para migrar al schema nuevo.
# Esto es seguro porque el histórico se regenera corriendo el pipeline con los
# archivos originales cargados en las tablas pd_*_aux.
if df_lote_completo is not None:
    tabla_existe   = spark.catalog.tableExists(TABLA_FACT)
    schema_es_viejo = tabla_existe and "ID_ARCHIVO" not in spark.table(TABLA_FACT).columns

    if schema_es_viejo:
        print(f"\n⚠️  Schema viejo detectado en {TABLA_FACT} (tiene ORIGEN_ARCHIVO en lugar de ID_ARCHIVO).")
        print(f"   Aplicando migración v26: DROP + recreación con schema nuevo...")
        spark.sql(f"DROP TABLE IF EXISTS {TABLA_FACT}")
        tabla_existe = False  # Forzar el path de creación limpia

    if tabla_existe:
        # [FIX] MERGE por ID_PARTE_HASH (SHA256 determinista) en lugar de
        # ID_ARCHIVO + ID_EXTERNO. ID_EXTERNO no es estable entre ejecuciones
        # para COOPLYF (se genera con monotonically_increasing_id), lo que causaba
        # duplicados en reprocesos. ID_PARTE_HASH se calcula con SHA256 sobre
        # ORIGEN_ARCHIVO + Suministro + Fecha + Medidor + Código, garantizando
        # idempotencia real independiente del orden de procesamiento.
        print(f"\n🔄 Aplicando MERGE sobre {TABLA_FACT}...")
        DeltaTable.forName(spark, TABLA_FACT).alias("fact") \
            .merge(
                df_lote_completo.alias("lote"),
                "fact.ID_PARTE_HASH = lote.ID_PARTE_HASH",
            ) \
            .whenMatchedUpdateAll() \
            .whenNotMatchedInsertAll() \
            .execute()
        print(f"✅ MERGE completado en {TABLA_FACT}.")
    else:
        print(f"\n🆕 Creando {TABLA_FACT} con schema v26...")
        df_lote_completo.write \
            .format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .saveAsTable(TABLA_FACT)
        print(f"✅ Tabla creada con schema nuevo.")

    # Limpiar stagings DESPUÉS de confirmar que el write/MERGE completó exitosamente.
    # El plan lazy ya fue materializado — ahora es seguro vaciar las tablas de entrada.
    for tabla_stg in stagings_a_limpiar:
        print(f"   Limpiando staging {tabla_stg}...")
        spark.sql(f"TRUNCATE TABLE {tabla_stg}")

else:
    print("⚠️  No hubo datos en el lote. No se realizaron cambios en la fact table.")


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 5 — DIMENSIÓN GEOGRÁFICA
# ═════════════════════════════════════════════════════════════════════════════

from pyspark.sql.functions import col, regexp_replace, trim

print(f"\n{'='*80}")
print("🗺️  GENERANDO DIMENSIÓN GEOGRÁFICA...")
print(f"{'='*80}")

df_fact_ids = spark.table(TABLA_FACT) \
    .select("SRV_CODIGO") \
    .filter("SRV_CODIGO IS NOT NULL") \
    .distinct()

df_sigec_clean = spark.table("datos_generales.sigec_general").select(
    col("SUMI").cast("long").alias("SRV_CODIGO"),
    regexp_replace(trim(col("LATITUD").cast("string")),  ",", ".").cast("double").alias("LATITUD"),
    regexp_replace(trim(col("LONGITUD").cast("string")), ",", ".").cast("double").alias("LONGITUD"),
    col("CALLE").cast("string"),
    col("DIRECCION").cast("string"),
    col("ALTURA").cast("long"),
    col("DPTO").cast("string").alias("DEPARTAMENTO"),
    col("BARRIO").cast("string"),
    col("PLAN").cast("string"),
    col("ZONA").cast("string"),
)

df_dim_geo = df_sigec_clean \
    .join(df_fact_ids, "SRV_CODIGO", "inner") \
    .dropDuplicates(["SRV_CODIGO"])

TABLA_DIM_GEO = "datos_generales.dim_suministros_geo"
df_dim_geo.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TABLA_DIM_GEO)

count_fact = df_fact_ids.count()
count_geo  = df_dim_geo.count()
print(f"✅ Dimensión Geográfica creada en: {TABLA_DIM_GEO}")
print(f"   Suministros únicos en Fact:     {count_fact}")
print(f"   Suministros con coordenadas:    {count_geo}")
if count_fact > count_geo:
    print(f"   ℹ️  {count_fact - count_geo} suministro(s) sin coordenadas en SIGEC.")


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 6 — DIMENSIÓN CALENDARIO
# ═════════════════════════════════════════════════════════════════════════════

from pyspark.sql.functions import col, min, max, year, month, date_format, weekofyear

TABLA_CALENDARIO = "datos_generales.dim_calendario"

print(f"\n{'='*80}")
print("📅 GENERANDO DIMENSIÓN CALENDARIO...")
print(f"{'='*80}")

try:
    rango = spark.table(TABLA_FACT) \
        .select(min("FECHA").alias("min_date"), max("FECHA").alias("max_date")) \
        .collect()[0]

    fecha_inicio = str(rango["min_date"]) if rango["min_date"] else "2024-01-01"
    fecha_fin    = str(rango["max_date"]) if rango["max_date"] else "2025-12-31"
    print(f"   Rango detectado: {fecha_inicio} → {fecha_fin}")

    df_calendario = spark.sql(
        f"SELECT explode(sequence(to_date('{fecha_inicio}'), to_date('{fecha_fin}'), interval 1 day)) AS Date"
    ).select(
        col("Date"),
        year("Date").alias("Año"),
        month("Date").alias("MesNro"),
        date_format("Date", "MMM").alias("Mes"),
        weekofyear("Date").alias("Semana"),
        date_format("Date", "yyyy-MM").alias("Periodo"),
    )

    df_calendario.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .saveAsTable(TABLA_CALENDARIO)

    print(f"✅ Dimensión Calendario creada con {df_calendario.count()} días.")

except Exception as e:
    print(f"❌ Error generando calendario: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 7 — PANEL DE CONTROL POR CONSOLA
# ═════════════════════════════════════════════════════════════════════════════

from pyspark.sql.functions import col, sum as _sum, count, round, countDistinct, date_format, desc

print(f"\n{'='*80}")
print("📊 PANEL DE CONTROL")
print(f"{'='*80}")

# Cargar la fact table y hacer los joins con las dimensiones
# [H-04] Todas las dimensiones son pequeñas → broadcast
df_fact_panel = spark.table(TABLA_FACT)
df_estado_dim = spark.table("datos_generales.dim_estado_bi")
df_traza_dim  = spark.table("datos_generales.dim_traza_calidad_bi")
df_empresa_dim = spark.table("datos_generales.dim_empresa_bi")
df_maestro_panel = spark.table(TABLA_MAESTRA_COD) \
    .select(col("COD_EPEC").cast("long").alias("COD_JOIN"), col("DESCRIPCION_CODIGO"), col("cant_USE_unitario")) \
    .dropDuplicates(["COD_JOIN"])

df_base_panel = df_fact_panel \
    .join(broadcast(df_estado_dim),  "ID_ESTADO",  "left") \
    .join(broadcast(df_traza_dim),   "ID_TRAZA",   "left") \
    .join(broadcast(df_empresa_dim), "ID_EMPRESA", "left") \
    .join(df_maestro_panel, df_fact_panel.CODIGO_EPEC == df_maestro_panel.COD_JOIN, "left")

# [H-06] Cache antes de múltiples acciones sobre el mismo DF
df_base_panel.cache()

# ── PESTAÑA 1: CALIDAD DE DATOS ───────────────────────────────────────────
print("\n" + " "*25 + "--- 1. CALIDAD DE DATOS ---")

# [H-06] Un único groupBy reemplaza 5 count() separados
kpi_rows = df_base_panel.groupBy("DESC_ESTADO").agg(
    count("*").alias("cantidad"),
    round(_sum("cant_USE_unitario"), 2).alias("total_uses"),
).collect()

kpi_dict         = {r["DESC_ESTADO"]: r["cantidad"] for r in kpi_rows}
total_ingresados = sum(r["cantidad"] for r in kpi_rows)
fuera_alcance    = kpi_dict.get("Fuera de Alcance", 0)
aprobados        = kpi_dict.get("Aprobado",         0)
rechazados       = kpi_dict.get("Rechazado",        0)
ocr              = kpi_dict.get("Revisión",     0)

base_efect  = total_ingresados - fuera_alcance
efectividad = (aprobados / base_efect * 100) if base_efect > 0 else 0.0

print(f"▶ Total Ingresados:  {total_ingresados:,}".replace(",", "."))
print(f"▶ Fuera de Alcance:  {fuera_alcance:,}".replace(",", "."))
print(f"▶ Aprobados:         {aprobados:,}".replace(",", "."))
print(f"▶ Rechazados:        {rechazados:,}".replace(",", "."))
print(f"▶ Pendientes OCR:    {ocr:,}".replace(",", "."))
print(f"⭐ Efectividad:      {efectividad:.2f} %")

# Corregidos dentro de aprobados
df_aprobados = df_base_panel.filter(col("DESC_ESTADO") == "Aprobado")
df_aprobados.cache()  # Se usa 3 veces más abajo

kpi_trazas = df_aprobados.groupBy("DESC_TRAZA").agg(count("*").alias("cantidad")).collect()
total_aprobados_cnt = sum(r["cantidad"] for r in kpi_trazas)
corregidos          = sum(r["cantidad"] for r in kpi_trazas if r["DESC_TRAZA"] != "Original OK")
porc_corregidos     = (corregidos / total_aprobados_cnt * 100) if total_aprobados_cnt > 0 else 0.0

print(f"🛠️ Porc. Corregidos: {porc_corregidos:.2f} %")
print("\n--- Desglose de Traza de Calidad (Solo Aprobados) ---")
df_aprobados.groupBy("DESC_TRAZA").count().orderBy(desc("count")).show(truncate=False)

# ── PESTAÑA 2: ANÁLISIS OPERATIVO ────────────────────────────────────────
print("\n" + " "*25 + "--- 2. ANÁLISIS OPERATIVO (APROBADOS) ---")

# [H-06] Un único agg() reemplaza múltiples collect() separados
kpi_op = df_aprobados.agg(
    count("*").alias("total_partes"),
    round(_sum("cant_USE_unitario"), 2).alias("total_uses"),
    countDistinct("FECHA").alias("dias_trabajados"),
).collect()[0]

total_partes_op = kpi_op["total_partes"]    or 0
total_uses_op   = kpi_op["total_uses"]      or 0.0
dias_trab       = kpi_op["dias_trabajados"] or 1
promedio_uses   = total_uses_op / total_partes_op if total_partes_op > 0 else 0.0
ritmo_diario    = total_partes_op / dias_trab

print(f"▶ Total Partes Aprobados: {total_partes_op:,}".replace(",", "."))
print(f"▶ USES Aprobadas:         {total_uses_op:,.2f}".replace(",", "."))
print(f"▶ Promedio USES x Parte:  {promedio_uses:.2f}")
print(f"▶ Ritmo Diario (Partes):  {ritmo_diario:.2f}")

print("\n--- Detalles por Contratista ---")
df_aprobados.groupBy("EMPRESA").agg(
    count("*").alias("Trabajos"),
    round(_sum("cant_USE_unitario"), 2).alias("Total_USES"),
).show()

print("\n--- Cant. por Código de Cierre ---")
df_aprobados.groupBy("CODIGO_EPEC", "DESCRIPCION_CODIGO").agg(
    count("*").alias("Cantidad"),
    round(_sum("cant_USE_unitario"), 2).alias("Total_USES"),
).orderBy(desc("Cantidad")).show(truncate=False)

print("\n--- Detalle Mensual ---")
df_aprobados.withColumn("Mes", date_format(col("FECHA"), "yyyy/MM")) \
    .groupBy("Mes").agg(
        count("*").alias("Trabajos"),
        round(_sum("cant_USE_unitario"), 2).alias("Total_USES"),
    ).orderBy("Mes").show()

# Liberar caches
df_aprobados.unpersist()
df_base_panel.unpersist()

print(f"{'='*80}")
print("✅ PIPELINE COMPLETADO.")
print(f"{'='*80}")


# In[1]:


# ═════════════════════════════════════════════════════════════════════════════
# CELDA 8 — UTILIDAD: VACIADO DEL HISTÓRICO (SOLO PARA REPROCESO COMPLETO)
# ═════════════════════════════════════════════════════════════════════════════

#  EJECUTAR ESTA CELDA SOLO SI SE NECESITA REPROCESAR TODO EL HISTÓRICO.
# No forma parte del pipeline normal. Correr de forma aislada.

TABLA_FACT = "datos_generales.fact_partes_diarios_full"

try:
    if spark.catalog.tableExists(TABLA_FACT):
         print(f"🧹 Vaciando {TABLA_FACT}...")
         spark.sql(f"TRUNCATE TABLE {TABLA_FACT}")
         print("✅ Tabla vaciada. Correr el pipeline completo para recargar.")
    else:
         print(f"⚠️  La tabla {TABLA_FACT} no existe.")
except Exception as e:
     print(f"❌ Error: {e}")

