#!/usr/bin/env python
# coding: utf-8

# ## act_mapeo_cod_contratistas_epec
# 
# null

# In[2]:


import pandas as pd
from pyspark.sql.functions import col, split, explode, trim, desc_nulls_last, row_number, to_date
from pyspark.sql.types import StructType, StructField, StringType, FloatType

print("--- 00. ACTUALIZACIÓN DE MAESTROS CON USE (CRUCE POR CÓDIGO EPEC) ---")

# RUTAS DE ARCHIVOS
FILE_PATH_MAPEO = "/lakehouse/default/Files/fuente_de_partes_diarios/AD_PD_para_PBI_COOPLYF/conversion_codigos_contratista_a_PD_PBI.xlsx"
FILE_PATH_USES = "/lakehouse/default/Files/fuente_de_partes_diarios/AD OP MI/OP_MI.xlsx"

TABLA_MAPEO_MASTER = "datos_generales.mapeo_codigos_master"

try:
    # ---------------------------------------------------------
    # 1. PROCESAMIENTO DEL MAPEO DE CÓDIGOS (EXCEL BASE)
    # ---------------------------------------------------------
    p_df = pd.read_excel(FILE_PATH_MAPEO)
    df_mapeo_raw = spark.createDataFrame(p_df)
    
    # Normalizamos columnas (Esto captura automáticamente la nueva columna 'FASE')
    new_columns = [c.replace(" ", "_").upper() for c in df_mapeo_raw.columns]
    df_mapeo_raw = df_mapeo_raw.toDF(*new_columns)
    
    # Explotamos los códigos de contratista e incluimos la FASE
    df_mapeo_base = df_mapeo_raw \
        .withColumn("COD_CONTRATISTA_INDIVIDUAL", explode(split(col("CODIGOS_CONTRATISTA"), ","))) \
        .withColumn("COD_CONTRATISTA_INDIVIDUAL", trim(col("COD_CONTRATISTA_INDIVIDUAL"))) \
        .withColumn("FASE", trim(col("FASE"))) \
        .select(
            col("CONTRATISTA"),
            col("COD_CONTRATISTA_INDIVIDUAL"),
            col("FASE"), # <--- AQUÍ AGREGAMOS LA NUEVA COLUMNA
            col("CODIGOS_F218").alias("COD_EPEC"), # CLAVE DE CRUCE
            col("DESCRIPCION_CODIGO")
        ).distinct()

    # ---------------------------------------------------------
    # 2. PROCESAMIENTO DE VALORES USE (NUEVO EXCEL)
    # ---------------------------------------------------------
    print(f"Leyendo archivo de USEs desde: {FILE_PATH_USES}")
    # Leemos la Hoja 2 donde están los datos
    p_df_uses = pd.read_excel(FILE_PATH_USES, sheet_name='Hoja2')
    
    # Limpieza y preparación para el Join
    # Convertimos el código a string y quitamos decimales (.0) si pandas lo leyó como float
    p_df_uses['CODIGO_JOIN'] = p_df_uses['CODIGOS'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    
    # Convertir 'Cant. USE Unitario' a float
    p_df_uses['cant_USE_unitario'] = p_df_uses['Cant. USE Unitario'].astype(str).str.replace(',', '.', regex=False)
    p_df_uses['cant_USE_unitario'] = pd.to_numeric(p_df_uses['cant_USE_unitario'], errors='coerce').fillna(0.0)
    
    # Seleccionamos columnas
    p_df_uses_clean = p_df_uses[['CODIGO_JOIN', 'cant_USE_unitario']]
    
    # Pasamos a Spark
    df_uses_spark = spark.createDataFrame(p_df_uses_clean)
    
    # ---------------------------------------------------------
    # 3. CRUCE DE DATOS Y GUARDADO
    # ---------------------------------------------------------
    
    # Preparamos df_mapeo_base: Convertimos COD_EPEC a string para asegurar el match
    df_mapeo_base = df_mapeo_base.withColumn("COD_EPEC_JOIN", col("COD_EPEC").cast("string"))
    
    # Hacemos Left Join usando COD_EPEC vs CODIGOS (del Excel de USEs)
    df_mapeo_final = df_mapeo_base.join(
        df_uses_spark,
        df_mapeo_base.COD_EPEC_JOIN == df_uses_spark.CODIGO_JOIN,
        how="left"
    ).drop("CODIGO_JOIN", "COD_EPEC_JOIN") # Limpiamos columnas auxiliares
    
    # Guardamos en Delta con overwriteSchema=true para permitir la nueva columna
    df_mapeo_final.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .saveAsTable(TABLA_MAPEO_MASTER)
        
    print(f"-> Tabla maestra de mapeo actualizada correctamente: {TABLA_MAPEO_MASTER}")
    
    # Validación: Mostramos cuántos códigos obtuvieron USE (no nulos)
    count_con_use = df_mapeo_final.filter(col("cant_USE_unitario").isNotNull() & (col("cant_USE_unitario") > 0)).count()
    print(f"-> Registros con USE asignado: {count_con_use}")
    
    display(df_mapeo_final)

except Exception as e:
    print(f"[ERROR] Fallo al actualizar mapeo: {e}")


# 
