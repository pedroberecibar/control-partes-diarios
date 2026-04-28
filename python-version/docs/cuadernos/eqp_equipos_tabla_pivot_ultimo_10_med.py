#!/usr/bin/env python
# coding: utf-8

# ## eqp_equipos_tabla_pivot_ultimo_10_med
# 
# New notebook

# In[1]:


# Welcome to your new notebook
# Type here in the cell editor to add code!


# In[1]:


from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col, when, to_timestamp, lit
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime
from delta.tables import *
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")


df = spark.sql("SELECT * FROM datos_generales.eqp_equipos_gral")


from pyspark.sql.functions import col, when, to_timestamp, lit

# Lista de columnas tipo timestamp
timestamp_columns = [
    "EQP_FECHA_INSTAL",
    "EQP_FECHA_RETIRO",
    "EQP_ULTIMA_ACTUALIZACION"
]

# Rango válido de fechas
min_valid_date = to_timestamp(lit("1899-12-30 00:00:00"))
max_valid_date = to_timestamp(lit("9999-12-31 23:59:59"))

# Normalizar fechas fuera de rango
for column in timestamp_columns:
    df = df.withColumn(
        column,
        when(
            (col(column) < min_valid_date) | (col(column) > max_valid_date),
            min_valid_date  # o podrías usar lit(None) si preferís poner null
        ).otherwise(col(column))
    )


# # 1v

# In[3]:


from pyspark.sql import functions as F

# 1. Crear columna combinada de clave
df = df.withColumn("orden_grm", F.concat_ws("-", F.col("EQP_ORDEN").cast("int"), F.col("GRM_NUMERO").cast("int")))

# 2. Lista de columnas a pivotear
columnas_a_pivotear = [
    "STE_NUMERO", "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES", "FACTOR_CORRIENTE_MEDIDOR",
    "FACTOR_TENSION_MEDIDOR", "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION"
]

# 3. Obtener todas las combinaciones únicas de orden_grm
ordenes = df.select("EQP_ORDEN", "GRM_NUMERO").distinct().collect()
combinaciones = [f"{int(row['EQP_ORDEN'])}-{int(row['GRM_NUMERO'])}" for row in ordenes]

# 4. Crear expresiones condicionales para cada campo por combinación
exprs = []
for comb in combinaciones:
    for col in columnas_a_pivotear:
        new_col_name = f"{col}_{comb}"
        expr = F.first(F.when(F.col("orden_grm") == comb, F.col(col)), ignorenulls=True).alias(new_col_name)
        exprs.append(expr)

# 5. Agrupar y generar columnas pivoteadas
df_pivot = df.groupBy("SRV_CODIGO").agg(*exprs)

df_pivot.printSchema()


# In[ ]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime

# resultados = predictions.select("SRV_CODIGO","prediction").dropDuplicates() #resultados_unicos = resultados.dropDuplicates(["SRV_CODIGO"])

# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")


# Seleccionar la base de datos
spark.sql("USE datos_generales")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_equipos_srv_orden_grm_1'

# Guardar la tabla como una tabla administrada
df_pivot.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# In[7]:


df_pivot.printSchema()


# In[8]:


# ordenado al inverso para tener el ultimo como la combinacion 1-1

from pyspark.sql import functions as F, Window

# 1. Crear clave de combinación
df = df.withColumn("orden_grm", F.concat_ws("-", F.col("EQP_ORDEN").cast("int"), F.col("GRM_NUMERO").cast("int")))

# 2. Obtener la última EQP_FECHA_INSTAL para cada combinación
comb_df = df.select("EQP_ORDEN", "GRM_NUMERO", "EQP_FECHA_INSTAL") \
    .withColumn("orden_grm", F.concat_ws("-", F.col("EQP_ORDEN").cast("int"), F.col("GRM_NUMERO").cast("int"))) \
    .groupBy("orden_grm").agg(F.max("EQP_FECHA_INSTAL").alias("ultima_instal"))

# 3. Obtener combinaciones ordenadas por EQP_FECHA_INSTAL descendente
combinaciones = comb_df.orderBy(F.col("ultima_instal").desc()) \
    .select("orden_grm") \
    .rdd.flatMap(lambda x: x) \
    .collect()

# 4. Columnas a pivotear
columnas_a_pivotear = [
    "STE_NUMERO", "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES", "FACTOR_CORRIENTE_MEDIDOR",
    "FACTOR_TENSION_MEDIDOR", "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION"
]

# 5. Crear expresiones condicionales ordenadas
exprs = []
for comb in combinaciones:
    for col in columnas_a_pivotear:
        new_col_name = f"{col}_{comb}"
        expr = F.first(F.when(F.col("orden_grm") == comb, F.col(col)), ignorenulls=True).alias(new_col_name)
        exprs.append(expr)

# 6. Generar tabla final agrupada por SRV_CODIGO
df_pivot_2 = df.groupBy("SRV_CODIGO").agg(*exprs)

df_pivot_2.printSchema()


# In[9]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime

# resultados = predictions.select("SRV_CODIGO","prediction").dropDuplicates() #resultados_unicos = resultados.dropDuplicates(["SRV_CODIGO"])

# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")


# Seleccionar la base de datos
spark.sql("USE datos_generales")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_equipos_srv_orden_grm'

# Guardar la tabla como una tabla administrada
df_pivot_2.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# In[ ]:


df_pivot_2.show(6)


# # 2v
# 

# In[2]:


from pyspark.sql import functions as F
from pyspark.sql.window import Window

# 1. Definir ventana de orden por EQP_ORDEN y GRM_NUMERO DESC
w = Window.partitionBy("SRV_CODIGO").orderBy(F.col("EQP_ORDEN").desc(), F.col("GRM_NUMERO").desc())

# 2. Rankear los equipos por servicio
df_ranked = df.withColumn("rank", F.row_number().over(w) - 1)  # 0 es el más reciente

# 3. Filtrar solo los últimos 10
df_top10 = df_ranked.filter(F.col("rank") < 10)

# 4. Lista de columnas a pivotear
columnas_a_pivotear = [
    "STE_NUMERO", "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES", "FACTOR_CORRIENTE_MEDIDOR",
    "FACTOR_TENSION_MEDIDOR", "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION"
]

# 5. Renombrar columnas según rank
def renombrar_columnas(df):
    for col in columnas_a_pivotear:
        for i in range(10):
            sufijo = "ULTIMO" if i == 0 else f"ANTERIOR_{i}"
            df = df.withColumnRenamed(f"{col}_{i}", f"{col}_{sufijo}")
    return df

# 6. Pivotear por SRV_CODIGO y rank
# Creamos una tabla con todas las columnas separadas por rank
df_pivot = df_top10.select("SRV_CODIGO", "rank", *columnas_a_pivotear) \
    .groupBy("SRV_CODIGO") \
    .agg(*[
        F.first(F.when(F.col("rank") == i, F.col(col)), ignorenulls=True).alias(f"{col}_{i}")
        for i in range(10) for col in columnas_a_pivotear
    ])

# 7. Renombrar columnas
df_pivot_final = renombrar_columnas(df_pivot)

df_pivot_final.printSchema()

# df_pivot_final.show()


# In[3]:


spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")

df_pivot_final.printSchema()

df_pivot_final.show()


# In[3]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime

# resultados = predictions.select("SRV_CODIGO","prediction").dropDuplicates() #resultados_unicos = resultados.dropDuplicates(["SRV_CODIGO"])

# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")


# Seleccionar la base de datos
spark.sql("USE datos_generales")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_equipos_ultimos_10'

# Guardar la tabla como una tabla administrada
df_pivot_final.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# In[4]:


from pyspark.sql import functions as F
from pyspark.sql.window import Window

# 1. DataFrame original (asegúrate que se llama 'df' o cambialo si tiene otro nombre)

# 2. Definir ventana por SRV_CODIGO ordenando por EQP_ORDEN y GRM_NUMERO descendente
window_spec = Window.partitionBy("SRV_CODIGO").orderBy(
    F.col("EQP_ORDEN").desc(), F.col("GRM_NUMERO").desc()
)

# 3. Agregar columna de ranking (0: el más reciente)
df_ranked = df.withColumn("rank", F.row_number().over(window_spec) - 1)

# 4. Filtrar solo los 5 más recientes
df_top5 = df_ranked.filter(F.col("rank") < 5)

# 5. Columnas a pivotear
columnas_a_pivotear = [
    "STE_NUMERO", "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES", "FACTOR_CORRIENTE_MEDIDOR",
    "FACTOR_TENSION_MEDIDOR", "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION"
]

# 6. Crear tabla pivot con las columnas separadas por rank
df_pivot = df_top5.select("SRV_CODIGO", "rank", *columnas_a_pivotear) \
    .groupBy("SRV_CODIGO") \
    .agg(*[
        F.first(F.when(F.col("rank") == i, F.col(col)), ignorenulls=True).alias(f"{col}_{i}")
        for i in range(5) for col in columnas_a_pivotear
    ])

# 7. Función para renombrar columnas según sufijo deseado
def renombrar_columnas_5(df):
    for col in columnas_a_pivotear:
        for i in range(5):
            sufijo = "ULTIMO" if i == 0 else f"ANTERIOR_{i}"
            df = df.withColumnRenamed(f"{col}_{i}", f"{col}_{sufijo}")
    return df

# 8. Renombrar columnas finales
df_pivot_final_2 = renombrar_columnas_5(df_pivot)


# In[6]:


df_pivot_final_2 = df_pivot_final_2.dropDuplicates()


# In[7]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime


# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_equipos_ultimos_5'

# Guardar la tabla como una tabla administrada
df_pivot_final_2.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# # Creacion de tabla de medidor con los ultimos 10 srv_codigo donde estuvo conectado

# ### 1. Intento 1 (bloqueado)
# Se trato de filtrar por retirado desde la tabla de eqp_equipos_ultimos_5 creando eqp_equipos_ultimos_5_solo_intalados pero hay problemas de dublicados
# 

# In[11]:


from pyspark.sql.functions import col

valores_excluir = [999999999, 99, 99999999, 1, 0]

df_ult_5_filtrado = df_pivot_final_2.filter(
    (col("STE_NUMERO_ULTIMO").isin(valores_excluir) == False) &
    (col("EQP_ESTADO_ULTIMO").isNull())
)


# In[13]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime


# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_equipos_ultimos_5_solo_intalados'

# Guardar la tabla como una tabla administrada
df_ult_5_filtrado.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# In[3]:


df.printSchema()


# ### 2. Intento 2: se busca hacer una tabla pivot de equipos y ultimos 10 sumis donde fue instalado

# In[2]:


# v1
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# 1. Ventana por STE_NUMERO, ordenando por fecha de instalación (más reciente primero)
w = Window.partitionBy("STE_NUMERO").orderBy(F.col("EQP_FECHA_INSTAL").desc())

# 2. Rankear los servicios por equipo
df_ranked = df.withColumn("rank", F.row_number().over(w) - 1)  # 0 = más reciente

# 3. Filtrar solo los últimos 10 servicios por equipo
df_top10 = df_ranked.filter(F.col("rank") < 10)

# 4. Lista de columnas a pivotear (ahora incluimos SRV_CODIGO + EQP_ORDEN + GRM_NUMERO también)
columnas_a_pivotear = [
    "SRV_CODIGO", "EQP_ORDEN", "GRM_NUMERO",
    "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES", "FACTOR_CORRIENTE_MEDIDOR",
    "FACTOR_TENSION_MEDIDOR", "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION"
]

# 5. Función para renombrar columnas
def renombrar_columnas(df):
    for col in columnas_a_pivotear:
        for i in range(10):
            sufijo = "ULTIMO" if i == 0 else f"ANTERIOR_{i}"
            df = df.withColumnRenamed(f"{col}_{i}", f"{col}_{sufijo}")
    return df

# 6. Pivotear por STE_NUMERO y rank
df_pivot = df_top10.select("STE_NUMERO", "rank", *columnas_a_pivotear) \
    .groupBy("STE_NUMERO") \
    .agg(*[
        F.first(F.when(F.col("rank") == i, F.col(col)), ignorenulls=True).alias(f"{col}_{i}")
        for i in range(10) for col in columnas_a_pivotear
    ])

# 7. Renombrar columnas
df_pivot_final_equipo = renombrar_columnas(df_pivot)

# 8. Resultado
df_pivot_final_equipo.printSchema()
# df_pivot_final_equipo.show(truncate=False)


# In[3]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime


# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'eqp_ultimos_10_srv_por_eqp'

# Guardar la tabla como una tabla administrada
df_pivot_final_equipo.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')

