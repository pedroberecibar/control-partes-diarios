#!/usr/bin/env python
# coding: utf-8

# ## nb_equipo_eqp_instalados
# 
# New notebook

# In[1]:


# Welcome to your new notebook
# Type here in the cell editor to add code!


# # Actualizacion via MERGE

# In[7]:


eqp_backup = spark.sql("SELECT * FROM datos_generales.eqp_equipos_gral")
eqp_backup.printSchema()

srv = spark.sql("SELECT * FROM datos_generales.dim_srv")
srv.printSchema()
# 
# eqp_aux = spark.sql("SELECT * FROM datos_generales.eqp_equipos_aux")
# eqp_aux.printSchema()


# In[10]:


# crear copia de tabla a actualizar

from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col, when, to_timestamp, lit
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime
from delta.tables import *

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# Lista de columnas de tipo timestamp a normalizar
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
    eqp_backup = eqp_backup.withColumn(
        column,
        when(
            (col(column) < min_valid_date) | (col(column) > max_valid_date),
            min_valid_date  # o podrías usar lit(None) si preferís poner null
        ).otherwise(col(column))
    )

#
delta_table_name = 'backup_eqp_equipos'

# Guardar la tabla como una tabla administrada
eqp_backup.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')


# In[ ]:


## OPCION PARAMETRIZADA HAMU
## código parametrizado, utilizando las variables que definiste al inicio para actualizar la tabla

from pyspark.sql.functions import col, when, to_timestamp, lit
from delta.tables import *
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")

# 1. Parámetros definidos al inicio o hay que usar el nombre de la tabla en datalake
tabla_original = "eqp_equipos_gral"
tabla_update = "eqp_equipos_aux"

# columna_key_original = "N CONTROL"
# columna_key_update = "N CONTROL"

# 2. Cargar la tabla Delta existente
deltaTable = DeltaTable.forName(spark, tabla_original)

# 3. Cargar el DataFrame con los datos actualizados
updates_df = spark.sql(f"SELECT * FROM datos_generales.{tabla_update}")

# Lista de columnas de tipo timestamp a normalizar
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
    updates_df = updates_df.withColumn(
        column,
        when(
            (col(column) < min_valid_date) | (col(column) > max_valid_date),
            min_valid_date  # o podrías usar lit(None) si preferís poner null
        ).otherwise(col(column))
    )

# 6. Ejecutar MERGE entre tabla original y actualizaciones usar el nombre de todas las columnas necesarias
deltaTable.alias("tgt") \
  .merge(
    updates_df.alias("src"),
    "tgt.SRV_CODIGO = src.SRV_CODIGO and tgt.STE_NUMERO = src.STE_NUMERO and tgt.EQP_ORDEN = src.EQP_ORDEN and tgt.GRM_NUMERO = src.GRM_NUMERO"
  ) \
  .whenMatchedUpdateAll() \
  .whenNotMatchedInsertAll() \
  .execute()


# ## 2. Codigo usado para obtener el listado de med instalados (codigo bloqueado), se reemplaza por el notebook "eqp_equipos_tabla_pivot_ultimo_10_med"
# Pero lo que se necesita es tranformar la tabla equipos para que agrupe por srv_codigo y haga pivot para tener N columnas con el medidor instalado actual y los N retirados anteriores.

# In[20]:


# 1. Parámetros definidos al inicio o hay que usar el nombre de la tabla en datalake
tabla_original = "eqp_equipos_gral"

# leer de la tabla actualizada y cargarla a un dataframe de spark
eqp = spark.read.table(tabla_original)


# In[21]:


from pyspark.sql.functions import col

eqp_instalado_act = eqp.filter(
    (col("EQP_ESTADO").isNull()) & (col("STE_NUMERO") != 99999999) & (col("STE_NUMERO") != 1)
)



# In[22]:


# # Aplicar filtro para corregir fechas menores a 1900-01-01 sobre las columnas tipo fechas que generan problema en el guardado
# from pyspark.sql.functions import col, when, to_timestamp, lit
# 
# # Lista de columnas de tipo timestamp a normalizar
# timestamp_columns = [
#  "EQP_FECHA_INSTAL",
#  "EQP_FECHA_RETIRO",
#  "EQP_ULTIMA_ACTUALIZACION"
# ]
# 
# # Valor mínimo válido para las fechas
# min_date = to_timestamp(lit("1900-01-01 00:00:00"))
# 
# # Iterar sobre cada columna de fecha y aplicar la normalización
# for column in timestamp_columns:
#     eqp_instalado = eqp_instalado.withColumn(
#         column,
#         when(
#             col(column) < min_date,
#             min_date
#         ).otherwise(col(column))
#     )


# In[23]:


# ## eliminar duplicados y dejar las filas mas actualizadas
# 
# from pyspark.sql import SparkSession
# from pyspark.sql.functions import col, row_number
# from pyspark.sql.window import Window
# 
# # --------------------------------------------
# # 🔧 PARAMETROS INICIALES
# var_nombre_tabla_origen = "eqp_instalado"        # nombre del DataFrame con los datos
# var_nombre_tabla_resultado = "eqp_instalado_act"           # nombre que tendrá el DataFrame final
# var_columna_clave = "STE_NUMERO"                     # clave para agrupar
# var_columna_orden = "EQP_ULTIMA_ACTUALIZACION"        # campo para obtener el registro más reciente
# num_partitions = 2000                                 # particiones opcionales para rendimiento
# # --------------------------------------------
# 
# # Crear sesión de Spark (si no existe)
# spark = SparkSession.builder \
#     .appName("Actualización de tabla deduplicada") \
#     .config("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY") \
#     .getOrCreate()
# 
# # Obtener el DataFrame de origen usando globals()
# df_origen = globals()[var_nombre_tabla_origen].repartition(num_partitions)
# 
# # Definir la ventana para deduplicar por la clave y ordenar por fecha descendente
# windowSpec = Window.partitionBy(var_columna_clave).orderBy(col(var_columna_orden).desc())
# 
# # Agregar columna para numerar cada grupo
# df_with_rownum = df_origen.withColumn("row_num", row_number().over(windowSpec))
# 
# # Filtrar solo el registro más reciente por clave
# df_deduplicado = df_with_rownum.filter(col("row_num") == 1).drop("row_num")
# 
# # Guardar el resultado con el nombre deseado
# globals()[var_nombre_tabla_resultado] = df_deduplicado
# 
# # Mostrar esquema final
# print(f"Esquema de la tabla '{var_nombre_tabla_resultado}':")
# globals()[var_nombre_tabla_resultado].printSchema()
# 


# Aclaracion, hasta este punto el listado de equipos trae casos  duplicados de medidores que figuran en 2 suministros a la vez sin tener fecha de retiro cargado.
# Se debe hacer un left join de dim_srv para traer _estado_srv_ y marca _telemedible_ para que se filtran los casos donde estado_srv es FR pero con telemedible = null

# In[24]:


#  eqp_instalado_act


# In[25]:


'''
from pyspark.sql.functions import col

srv_prefixed = srv.select(
    col("SRV_CODIGO"),
    col("SRV_ESTADO").alias("srv_SRV_ESTADO"),
    col("SRV_TELEMEDIBLE").alias("srv_SRV_TELEMEDIBLE")
)

eqp_srv = eqp_instalado_act.join(
    srv_prefixed,
    on="SRV_CODIGO",
    how="left"
)
'''
from pyspark.sql.functions import col

eqp_srv = eqp_instalado_act.join(
    srv.select("SRV_CODIGO", "SRV_ESTADO", "SRV_TELEMEDIBLE"),
    on="SRV_CODIGO",   # <- clave única, así NO se duplica
    how="left"
)


# In[26]:


eqp_srv.printSchema()


# In[27]:


# Eliminar duplicados (basado en todas las columnas)
eqp_srv_2 = eqp_srv.dropDuplicates()


# In[28]:


# se agrega una columna de control que verifica casos de suministros FR que nunca cargaron el medidor retirado, pero control que no sean telemedibles caduco para evitar problemas con los interligentes que se dejan en el pilar

from pyspark.sql.functions import when, col

eqp_srv_2 = eqp_srv_2.withColumn(
    "estado_retirado",
    when(
        (col("SRV_ESTADO") == "FR") & (
            col("SRV_TELEMEDIBLE").isNull() | (col("SRV_TELEMEDIBLE") == "NC")
        ),
        "RET"
    ).otherwise(None)
)


# In[29]:


from pyspark.sql.functions import col

eqp_srv_3 = eqp_srv_2.filter(col("estado_retirado").isNull())


# In[30]:


eqp_srv_3.printSchema()


# In[31]:


from pyspark.sql.functions import col, when, to_timestamp, lit

# Lista de columnas de tipo timestamp a normalizar
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
    eqp_srv_3 = eqp_srv_3.withColumn(
        column,
        when(
            (col(column) < min_valid_date) | (col(column) > max_valid_date),
            min_valid_date  # o podrías usar lit(None) si preferís poner null
        ).otherwise(col(column))
    )


# In[32]:


# guardar datos en tabla delta con la fecha de guardado en el nombre

from pyspark.sql import SparkSession
from pyspark.sql.types import DecimalType
from pyspark.sql.functions import col
from pyspark.sql.functions import current_timestamp, date_format
from datetime import datetime

# Crear o obtener la sesión de Spark con configuraciones optimizadas
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")


# Seleccionar la base de datos
# spark.sql("USE datos_generales")

# Nombre de la tabla Delta con la fecha actual
# fecha_actual = datetime.now().strftime("%d_%m_%Y_%H_%M")
# delta_table_name = f'casos_probables_fraude_{fecha_actual}'

delta_table_name = 'br_eqp__equipos_instalados'

# Guardar la tabla como una tabla administrada
eqp_srv_3.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f'Se guardo en la tabla delta {delta_table_name}')

