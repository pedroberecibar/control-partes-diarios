#!/usr/bin/env python
# coding: utf-8

# ## ingesta_adapter_CONECTAR
# 
# null

# ## Ingesta y Adaptacion CONECTAR
# Se leen y se limpian los datos de los partes diarios subidos al sharepoint

# In[2]:


import pandas as pd
import os
import datetime
import shutil
from pyspark.sql.functions import col
from notebookutils import mssparkutils # Librería nativa de Fabric

# =============================================================================
# 1. CONFIGURACIÓN
# =============================================================================

# RUTA TEST
# RUTA_ORIGEN = "abfss://b614be99-f29d-4343-a6ff-7ae15b8c0d5b@onelake.dfs.fabric.microsoft.com/d58d1146-b22f-4b63-b40b-d2c8fed9f56e/Files/fuente_de_partes_diarios/CONECTAR/MI - CONECTAR - PARTES DIARIOS/pd_ce_test"

# RUTA PROD
RUTA_ORIGEN = "abfss://b614be99-f29d-4343-a6ff-7ae15b8c0d5b@onelake.dfs.fabric.microsoft.com/d58d1146-b22f-4b63-b40b-d2c8fed9f56e/Files/fuente_de_partes_diarios/CONECTAR/MI - CONECTAR - PARTES DIARIOS"

TABLA_HISTORICA = "datos_generales.partes_diarios_general_conectar"
TABLA_OUTPUT    = "datos_generales.pd_conectar_aux"
TABLA_MAESTRA   = "datos_generales.mapeo_codigos_master"

MAPEO_COLUMNAS = {
    'ID': 'ID_Externo',
    'Fecha': 'Fecha',
    'Suministro': 'Suministro',
    'Colocado': 'medidorColocado',
    'Retirado': 'medidorRetirado',
    'Codigo': 'codTiposManoObra'
}

# =============================================================================
# 2. FUNCIONES AUXILIARES
# =============================================================================

def obtener_historial_procesados():
 
    try:
        df_spark = spark.sql(f"SELECT DISTINCT ORIGEN_ARCHIVO FROM {TABLA_HISTORICA}")
        return set([row['ORIGEN_ARCHIVO'] for row in df_spark.collect()])
    except:
        return set()

def obtener_codigos_habilitados():

    try:
        df_codigos = spark.table(TABLA_MAESTRA).filter(col("CONTRATISTA") == "CONECTAR").select("COD_CONTRATISTA_INDIVIDUAL").distinct()
        lista = [row['COD_CONTRATISTA_INDIVIDUAL'] for row in df_codigos.collect()]
        return [str(x) for x in lista if x is not None]
    except:
        return []

def procesar_excel_conectar_robusto(file_info, codigos_validos):
    """
    Lee usando mssparkutils y copia temporal para evitar errores de montaje.
    """
    stats = {'total_leido': 0, 'aprobados_ce': 0}
    nombre_archivo = file_info.name
    ruta_origen_one_lake = file_info.path 
    

    ruta_temporal = f"/tmp/{nombre_archivo}"
    
    try:
        # 1. Copiamos del Lago a Temp Local (Forzamos la descarga real)
        mssparkutils.fs.cp(ruta_origen_one_lake, f"file:{ruta_temporal}")
        
        # 2. Lectura con Pandas desde /tmp
        df = pd.read_excel(ruta_temporal, header=2)
        
        # --- LIMPIEZA INMEDIATA ---
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
        
        # ... (RESTO DE TU LÓGICA DE VALIDACIÓN IGUAL QUE ANTES) ...
        # Validaciones básicas
        cols_existentes = [c for c in MAPEO_COLUMNAS.keys() if c in df.columns]
        df = df[cols_existentes].rename(columns=MAPEO_COLUMNAS)
        
        cols_texto = ['ID_Externo', 'Suministro', 'medidorColocado', 'medidorRetirado', 'codTiposManoObra']
        for col_name in cols_texto:
            if col_name in df.columns:
                df[col_name] = df[col_name].astype(str).replace('nan', None).replace('<NA>', None)

        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date

        stats['total_leido'] = len(df)
        
        if 'codTiposManoObra' in df.columns and codigos_validos:
            df_ce = df[df['codTiposManoObra'].isin(codigos_validos)].copy()
            stats['aprobados_ce'] = len(df_ce)
            df = df_ce
        else:
            stats['aprobados_ce'] = 0
            df = pd.DataFrame()

        if df.empty: return None, stats

        df['ORIGEN_ARCHIVO'] = nombre_archivo
        df['fecha_proceso'] = datetime.datetime.now()
        
        return df, stats
        
    except Exception as e:
        print(f"   ❌ Error procesando {nombre_archivo}: {e}")
        # Asegurar limpieza si falla
        if os.path.exists(ruta_temporal): os.remove(ruta_temporal)
        return None, stats

# =============================================================================
# 3. EJECUCIÓN PRINCIPAL (CON MSSPARKUTILS)
# =============================================================================

def main():
    print("--- INICIO PROCESO ADAPTADOR CONECTAR (VÍA MSSPARKUTILS) ---")
    
    MODO_REPROCESO = True # <--- MANTENER EN TRUE PARA TU PRUEBA
    
    if MODO_REPROCESO:
        archivos_ya_en_historico = set()
    else:
        archivos_ya_en_historico = obtener_historial_procesados()

    codigos_validos = obtener_codigos_habilitados()
    if not codigos_validos: return

    # --- CAMBIO CLAVE: DETECCIÓN CON MSSPARKUTILS ---
    print(f"-> Escaneando ruta OneLake: {RUTA_ORIGEN}")
    try:
        # Esto consulta directo al Storage (Verdadera Fuente)
        archivos_detectados = mssparkutils.fs.ls(RUTA_ORIGEN)
    except Exception as e:
        print(f"❌ Error accediendo a la ruta: {e}")
        return

    archivos_a_procesar = []
    for f in archivos_detectados:
        if f.name.endswith((".xlsx", ".xls")):
            if f.name not in archivos_ya_en_historico:
                archivos_a_procesar.append(f) # Guardamos el objeto file_info completo

    total_nuevos = len(archivos_a_procesar)
    print(f"--- SE ENCONTRARON {total_nuevos} ARCHIVOS PENDIENTES ---")
    
    # ... (RESTO DEL MAIN IGUAL, PERO PASANDO file_info) ...
    if total_nuevos == 0: return

    df_lote = pd.DataFrame()
    
    print("-" * 75)
    print(f"{'ARCHIVO':<45} | {'LEÍDOS':<12} | {'APROBADOS'}")
    print("-" * 75)

    for file_info in archivos_a_procesar:
        df_temp, stats = procesar_excel_conectar_robusto(file_info, codigos_validos)
        
        print(f"{file_info.name[:45]:<45} | {stats['total_leido']:<12} | {stats['aprobados_ce']}")
        
        if df_temp is not None:
            df_lote = pd.concat([df_lote, df_temp], ignore_index=True)

    # ... (GUARDADO IGUAL) ...
    if not df_lote.empty:
        sdf = spark.createDataFrame(df_lote)
        sdf.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(TABLA_OUTPUT)
        print(f"\n✅ GUARDADO EXITOSO.")

main()


# In[5]:


print("🧹 Vaciando tabla de Staging (pd_conectar_aux)...")

try:
    spark.sql("TRUNCATE TABLE datos_generales.pd_conectar_aux")
    print("✅ Tabla vaciada correctamente. Ahora tiene 0 registros.")
except Exception as e:
    print(f"❌ Error al intentar vaciar: {e}")

