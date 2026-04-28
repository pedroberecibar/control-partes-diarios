--------------------------------------------------------------------------------------------------------
1. Tabla: dim_ord
--------------------------------------------------------------------------------------------------------

Odbc.Query("dsn=STBY", "select#(lf)*#(lf)from#(lf)xxsigec.ordenativos ord#(lf)WHERE#(lf)trunc(ord.ord_fecha_generacion) >= trunc(sysdate - 4)#(lf)or trunc(ord.ord_ultima_actualizacion) >= trunc(sysdate - 4)#(lf)/*trunc(ord.ord_fecha_generacion) >= to_date('01/01/2025','dd/mm/yyyy')#(lf)*/")

# actualizar dim_ord_aux con la consulta del df que crea la tabla ord_ordenativos

## OPCION PARAMETRIZADA HAMU
## código parametrizado, utilizando las variables que definiste al inicio para actualizar la tabla

# Establecer la configuración para manejar fechas y marcas de tiempo antiguas
# spark.sql.parquet.datetimeRebaseModeInWrite" to "LEGACY"
#datetimeRebaseMode
#spark.sql.parquet.datetimeRebaseModeInRead

spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")  # O "CORRECTED" según sea necesario
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "LEGACY")



from pyspark.sql.functions import col, when, to_timestamp, lit
from delta.tables import *


# 1. Parámetros definidos al inicio o hay que usar el nombre de la tabla en datalake
tabla_original = "dim_ord_aux"
tabla_update = "ord_ordenativos"

columna_key_original = "ORD_NUMERO"
columna_key_update = "ORD_NUMERO"

# 2. Cargar la tabla Delta existente
deltaTable = DeltaTable.forName(spark, tabla_original)

# 3. Cargar el DataFrame con los datos actualizados
updates_df = spark.sql(f"SELECT * FROM datos_generales.{tabla_update}")

# Lista de columnas de tipo timestamp a normalizar
timestamp_columns = [
    "ORD_FECHA_GENERACION",
    "ORD_FECHA_INICIO",
    "ORD_FECHA_VENCIMIENTO",
    "ORD_FECHA_FIN",
    "ORD_FECHA_CARGA_RESULTADO",
    "ORD_FECHA_ANULA",
    "ORD_FECHA_INICIO_ORIGINAL",
    "ORD_ULTIMA_ACTUALIZACION"
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

# 6. Ejecutar MERGE entre tabla original y actualizaciones
deltaTable.alias("tgt") \
  .merge(
    updates_df.alias("src"),
    f"tgt.`{columna_key_original}` = src.`{columna_key_update}`"
  ) \
  .whenMatchedUpdateAll() \
  .whenNotMatchedInsertAll() \
  .execute()

print(f"Se actualizo la tabla {tabla_original} a partir de la tabla {tabla_update}")

# Leer tablas completas del datalake leemos la tabla dim_ord_aux actualizada para crear dim_ord

dim_ord = spark.read.table("dim_ord_aux")

# Agregar la columna id_sumi_cnt
from pyspark.sql.functions import col, concat_ws, when


# Convertir SRV_CODIGO y CNT_NUMERO a enteros y luego agregar la columna nueva id_sumi_cnt
dim_ord = dim_ord.withColumn(
    "id_sumi_cnt",
    when(
        (col("SRV_CODIGO").isNotNull()) & (col("CNT_NUMERO").isNotNull()),
        concat_ws("|", col("SRV_CODIGO").cast("int"), col("CNT_NUMERO").cast("int"))
    ).otherwise(None)
)

# Mostrar el esquema y algunas filas del DataFrame resultante
dim_ord.printSchema()


# Establecer la configuración para manejar fechas y marcas de tiempo antiguas
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")  # O "CORRECTED" según sea necesario
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")

# Nombre de la tabla nueva
delta_table_name = 'dim_ord'

# Guardar la tabla como una tabla administrada
dim_ord.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f"Los datos se guardaron en la tabla: {delta_table_name}")

# tabla indice de srv cnt y ordenativo

df_ord_sel = dim_ord.select(
    "id_sumi_cnt",
    "ORD_NUMERO",
    "SRV_CODIGO"
)

# Establecer la configuración para manejar fechas y marcas de tiempo antiguas
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")  # O "CORRECTED" según sea necesario
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")

# Nombre de la tabla nueva
# tabla indice de srv cnt y ordenativo
delta_table_name = 'srv_id_sumi_cnt_ord'

# Guardar la tabla como una tabla administrada
df_ord_sel.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(delta_table_name)

print(f"Los datos se guardaron en la tabla: {delta_table_name}")


--------------------------------------------------------------------------------------------------------
2. Tabla: eqp_equipos_ultimos_10
--------------------------------------------------------------------------------------------------------

Odbc.Query("dsn=STBY", "select#(lf)eqp.srv_codigo,#(lf)eqp.ste_numero,#(lf)eqp.eqp_orden,#(lf)eqp.grm_numero,#(lf)eqp.eqp_fecha_instal,#(lf)eqp.eqp_precinto,#(lf)eqp.eqp_fecha_retiro,#(lf)eqp.eqp_estado,#(lf)eqp.eqp_observaciones,#(lf)TO_CHAR(eqp.EQP_FACTOR_INTENSIDAD) FACTOR_CORRIENTE_MEDIDOR,#(lf)TO_CHAR(eqp.EQP_FACTOR_TENSION) FACTOR_TENSION_MEDIDOR,#(lf)eqp.eqp_programa,#(lf)eqp.eqp_ultima_actualizacion#(lf)from#(lf)XXSIGEC.EQUIPOS eqp#(lf)where#(lf)trunc(eqp.eqp_fecha_instal) > trunc( sysdate - 10)#(lf)or trunc(eqp.eqp_ultima_actualizacion) > trunc( sysdate - 10)")

Cuadernos ejecutados luego de lo anterior, en el siguiente orden:
    1. "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\docs\cuadernos\nb_equipo_eqp_instalados.py"
    2. "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\docs\cuadernos\eqp_equipos_tabla_pivot_ultimo_10_med.py"


--------------------------------------------------------------------------------------------------------
3. Tabla: dim_stk_stock_equipos.parquet
--------------------------------------------------------------------------------------------------------

Odbc.Query("dsn=STBY", "select#(lf)stk.STE_NUMERO ,#(lf)stk.STE_FACTOR_EQUIPO ,#(lf)stk.SCF_CODIGO ,#(lf)stk.STE_AMPERAJE ,#(lf)stk.STE_MARCA ,#(lf)stk.STE_FECHA_BAJA ,#(lf)stk.STE_TIPO ,#(lf)stk.STE_TENSION ,#(lf)stk.STE_SERIE ,#(lf)stk.STE_PRECINTO ,#(lf)stk.STE_MODELO ,#(lf)stk.STE_ESTADO ,#(lf)stk.STE_ANIO_FABRICACION ,#(lf)stk.STE_DESCRIPCION ,#(lf)stk.STE_CLASE ,#(lf)stk.STE_FECHA_ALTA ,#(lf)TO_CHAR(stk.STE_AMPERAJE_MAXIMO) AMPERAJE_MAXIMO_MEDIDOR,#(lf)TO_CHAR(stk.STE_AMPERAJE_NOMINAL) AMPERAJE_NOMINAL_MEDIDOR,#(lf)stk.STE_FASES ,#(lf)stk.STE_HORARIOS ,#(lf)stk.STE_MIDE_ACTIVA ,#(lf)stk.STE_MIDE_HORA ,#(lf)stk.STE_MIDE_POTENCIA ,#(lf)stk.STE_MIDE_REACTIVA ,#(lf)stk.STE_MIGRADO ,#(lf)stk.GRC_CODIGO#(lf)#(lf)from#(lf)XXSIGEC.STOCK_EQUIPOS stk")


--------------------------------------------------------------------------------------------------------
4. Tabla: usuarios_gral.parquet
--------------------------------------------------------------------------------------------------------

Odbc.Query("dsn=STBY", "SELECT #(lf)    *#(lf)FROM #(lf)XXSIGEC.XXCO_USUARIOS_V ;")

--------------------------------------------------------------------------------------------------------
5. Tabla:  sigec_general.parquet (corregido: tabla: dim_suministros_geo)
--------------------------------------------------------------------------------------------------------
Datos de suministros con lat/lon, calle, barrio, etc. Estos datos vienen de la tabla dim_suministros_geo

No encontre como se actualiza desde fabric, pero si encontre una consulta que ejecute directamente desde Oracle SQL Developer.  La consulta es:
SELECT * FROM GEOREF.VM_SUMINISTROS
El resultado de esta se encuentra dentro del archivo .json cuya ruta es:
"D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\docs\ejemplo_consulta_VM_GEOREFERENCIA\.json"

--------------------------------------------------------------------------------------------------------
6. Tabla:  pivot_resul_app_movil.parquet
--------------------------------------------------------------------------------------------------------

Odbc.Query("dsn=STBY", "SELECT *#(lf)FROM (#(lf)  SELECT obs_ord.ORD_NUMERO, obs_ord.TOB_CODIGO, obs_ord.TOB_DESCRIPCION, obs_ord.OBO_INFO_ADICIONAL, obs_ord.IMD_ID#(lf)  FROM #(lf)  xxsigec.xxco_observaciones_ordenativ_v obs_ord,#(lf)  xxsigec.ordenativos ord#(lf)  WHERE #(lf)  ord.ord_numero = obs_ord.ord_numero#(lf)  AND ord.tor_codigo = 'CE'#(lf)  AND ord.sec_codigo_origen = 'PROTELEM'#(lf))#(lf)PIVOT (#(lf)  MAX(TOB_DESCRIPCION), max(OBO_INFO_ADICIONAL) AS TOB_DESCRIPCION#(lf)  FOR TOB_CODIGO IN (#(lf)    'APP4SITIO_1', 'APP4SITIO_2', 'APP4SITIO_3', 'APP4SITIO_4',#(lf)    'APP4TRAB_1', 'APP4TRAB_2', 'APP4TRAB_3', 'APP4TRAB_4', 'APP4TRAB_5',#(lf)    'APP4OBS_4', 'APP4OBS_80', 'APP4OBS_81', 'APP4OBS_82', 'APP4OBS_83', 'APP4OBS_84' , 'APP4OBS_11'#(lf)  ) #(lf))")