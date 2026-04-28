#!/usr/bin/env python
# coding: utf-8

# ## ingesta_adapter_COOPLYF
# 
# null

# # Ingesta de Datos de COOPLYF desde Sharepoint

# In[3]:


#!/usr/bin/env python
# coding: utf-8

# ## ingesta_adapter_COOPLYF
# 
# null

# # Ingesta de Datos de COOPLYF desde Sharepoint

# In[1]:


import pandas as pd
import os
import datetime
import shutil
import hashlib
from notebookutils import mssparkutils 

# =============================================================================
# 1. CONFIGURACIÓN
# =============================================================================

# Ruta ABFSS directa (TEST)
# RUTA_ORIGEN = "abfss://b614be99-f29d-4343-a6ff-7ae15b8c0d5b@onelake.dfs.fabric.microsoft.com/d58d1146-b22f-4b63-b40b-d2c8fed9f56e/Files/fuente_de_partes_diarios/AD_PD_para_PBI_COOPLYF/COOPLYF/PD_COOPLYF/pd_ce_test"

# Ruta ABFSS directa (PROD)
RUTA_ORIGEN = "abfss://b614be99-f29d-4343-a6ff-7ae15b8c0d5b@onelake.dfs.fabric.microsoft.com/d58d1146-b22f-4b63-b40b-d2c8fed9f56e/Files/fuente_de_partes_diarios/AD_PD_para_PBI_COOPLYF/COOPLYF/PD_COOPLYF"
TABLA_OUTPUT    = "datos_generales.pd_cooplyf_aux" 
TABLA_HISTORICA = "datos_generales.fact_partes_diarios_full"

# Mapeo Exacto
# Mapeo Exacto (Actualizado con formato 'idSuministros' y 'nroMedidor...')
MAPA_RENOMBRES = {
    # --- CÓDIGO DE TAREA ---
    'Codigo': 'codTiposManoObra', 'código': 'codTiposManoObra', 
    'Código': 'codTiposManoObra', 'Tarea': 'codTiposManoObra',
    'codTiposManoObra': 'codTiposManoObra', # Nuevo del Excel

    # --- SUMINISTRO ---
    'Suministro': 'Suministro', 'Suministros': 'Suministro', 
    'NIS': 'Suministro', 'Cuenta': 'Suministro',
    'idSuministros': 'Suministro',          # <--- AGREGADO (Clave del error)

    # --- FECHA ---
    'fecha': 'Fecha', 'FECHA': 'Fecha',

    # --- MEDIDOR COLOCADO ---
    'Medidor Colocado': 'medidorColocado', 'MedidorColocado': 'medidorColocado', 
    'colocado': 'medidorColocado', 'nro_medidor_colocado': 'medidorColocado',
    'nroMedidorColocado': 'medidorColocado', # <--- AGREGADO (Clave del error)

    # --- MEDIDOR RETIRADO ---
    'Medidor Retirado': 'medidorRetirado', 'MedidorRetirado': 'medidorRetirado', 
    'retirado': 'medidorRetirado', 'nro_medidor_retirado': 'medidorRetirado',
    'nroMedidorRetirado': 'medidorRetirado', # <--- AGREGADO

    # --- TIPO DE TRABAJO (TOR) ---
    'Tipo de trabajo': 'TipoTrabajo', 'TipoTrabajo': 'TipoTrabajo', 
    'codTiposTrabajos': 'TipoTrabajo'        # <--- AGREGADO
}

COLS_FINAL = ['ID_Externo', 'Fecha', 'Suministro', 'medidorColocado', 'medidorRetirado', 'codTiposManoObra', 'TipoTrabajo', 'ORIGEN_ARCHIVO']

# =============================================================================
# 2. FUNCIONES
# =============================================================================

def obtener_archivos_ya_procesados():
    try:
        df_spark = spark.table(TABLA_HISTORICA)
        return set([row['ORIGEN_ARCHIVO'] for row in df_spark.select("ORIGEN_ARCHIVO").distinct().collect()])
    except:
        return set()

def leer_archivo_desde_tmp(ruta_tmp, nombre):
    """Lee CSV o Excel desde la ruta local temporal."""
    try:
        if nombre.lower().endswith('.csv'):
            df = pd.read_csv(ruta_tmp, sep=',', dtype=str, encoding='utf-8')
            if len(df.columns) < 2:
                df = pd.read_csv(ruta_tmp, sep=';', dtype=str, encoding='latin-1')
        else:
            df = pd.read_excel(ruta_tmp, engine='openpyxl', dtype=str)
        return df
    except Exception as e:
        print(f"   ❌ Error leyendo {nombre}: {e}")
        return None

def limpiar_decimales_string(serie):
    if serie is None: return None
    return serie.astype(str).str.replace(r'\.0$', '', regex=True).replace({'nan': None, 'NaT': None, '<NA>': None, '': None, 'None': None})

def parsear_fechas_smart(serie):
    """
    Parsea fechas intentando ambos formatos (ISO y europeo) y eligiendo
    el que produzca menos NaT. Esto evita el bug donde un primer registro
    ambiguo (ej: 01/02/2025) hacía que todo el archivo se parsee al revés.
    """
    serie_str = serie.dropna().astype(str)
    if serie_str.empty:
        return pd.to_datetime(serie, errors='coerce')

    # Intentar ambos formatos sobre toda la serie
    parsed_iso = pd.to_datetime(serie, dayfirst=False, errors='coerce')
    parsed_eu  = pd.to_datetime(serie, dayfirst=True, errors='coerce')

    nat_iso = parsed_iso.isna().sum()
    nat_eu  = parsed_eu.isna().sum()

    # Elegir el formato que produzca menos NaT
    # En caso de empate (ej: formatos ambiguos), preferir dayfirst=True (europeo)
    # que es el estándar en Argentina
    return parsed_eu if nat_eu <= nat_iso else parsed_iso

def procesar_archivo_robusto(file_info):
    stats = {'leidos': 0, 'guardados': 0}
    nombre_archivo = file_info.name
    ruta_origen_lago = file_info.path
    
    # 1. Copia a TMP (Magia para evitar errores de montaje)
    ruta_tmp = f"/tmp/{nombre_archivo}"
    
    try:
        mssparkutils.fs.cp(ruta_origen_lago, f"file:{ruta_tmp}")
        
        # 2. Lectura Local
        df = leer_archivo_desde_tmp(ruta_tmp, nombre_archivo)
        
        # Limpieza inmediata del temporal
        if os.path.exists(ruta_tmp): os.remove(ruta_tmp)
        
        if df is None: return None, stats
        
        stats['leidos'] = len(df)
        
        # 3. Transformaciones
        df.columns = df.columns.str.strip()
        df.rename(columns=MAPA_RENOMBRES, inplace=True)
        df = df.loc[:, ~df.columns.duplicated()]

        for c in COLS_FINAL:
            if c not in df.columns: df[c] = None
            
        if 'Fecha' in df.columns:
            df = df[~df['Fecha'].astype(str).str.contains('Total', case=False, na=False)]
            fechas = parsear_fechas_smart(df['Fecha'])
            df = df[fechas.notna()]
            df['Fecha'] = fechas.dt.strftime('%Y-%m-%d')
        
        cols_a_limpiar = ['Suministro', 'codTiposManoObra', 'medidorColocado', 'medidorRetirado']
        for c in cols_a_limpiar:
            if c in df.columns:
                df[c] = limpiar_decimales_string(df[c])

        df['ORIGEN_ARCHIVO'] = nombre_archivo

        # [FIX] ID_Externo determinista: SHA256 sobre los campos clave del registro.
        # monotonically_increasing_id() es volátil entre ejecuciones → con el MERGE
        # de la fact table (que usa ID_PARTE_HASH, calculado sobre ORIGEN_ARCHIVO +
        # Suministro + Fecha + Medidor + Código), necesitamos que los registros sean
        # identificables de forma estable. Generamos el hash en Pandas para que
        # sea consistente antes de la conversión a Spark.
        df['ID_Externo'] = df.apply(
            lambda row: hashlib.sha256(
                f"{nombre_archivo}|{row.get('Suministro','')}|{row.get('Fecha','')}|"
                f"{row.get('medidorColocado','')}|{row.get('codTiposManoObra','')}".encode()
            ).hexdigest()[:16],
            axis=1,
        )

        df = df[COLS_FINAL]
        
        stats['guardados'] = len(df)
        return df, stats

    except Exception as e:
        print(f"❌ Error crítico procesando {nombre_archivo}: {e}")
        if os.path.exists(ruta_tmp): os.remove(ruta_tmp)
        return None, stats

# =============================================================================
# 3. EJECUCIÓN PRINCIPAL (CON MSSPARKUTILS)
# =============================================================================

def main():
    print("--- 🚀 INICIO ADAPTER COOPLYF (VÍA MSSPARKUTILS) ---")
    
    # --- PRUEBA: MODO REPROCESO ---
    MODO_REPROCESO = False
    
    if MODO_REPROCESO:
        print("⚠️ MODO REPROCESO ACTIVO: Ignorando bitácora histórica.")
        archivos_procesados = set()
    else:
        archivos_procesados = obtener_archivos_ya_procesados()

    # 1. LISTADO DIRECTO A ONELAKE (Sin os.walk)
    print(f"-> Escaneando ruta OneLake...")
    try:
        # Esto ve la verdad, toda la verdad y nada más que la verdad
        todos_archivos = mssparkutils.fs.ls(RUTA_ORIGEN)
    except Exception as e:
        print(f"❌ Error de acceso a ruta ABFSS: {e}")
        return

    archivos_nuevos = []
    archivos_omitidos = 0

    for f in todos_archivos:
        if f.name.endswith((".xlsx", ".xls", ".csv")) and not f.name.startswith("~"):
            if f.name in archivos_procesados:
                archivos_omitidos += 1
            else:
                archivos_nuevos.append(f) # Guardamos el objeto file_info
    
    print(f"-> Resumen Escaneo:")
    print(f"   ✅ Archivos NUEVOS a procesar: {len(archivos_nuevos)}")
    print(f"   ⏭️ Archivos OMITIDOS (Viejos): {archivos_omitidos}")

    if len(archivos_nuevos) == 0: 
        print("\n✅ Todo está al día.")
        return

    # 2. PROCESAMIENTO
    df_lote = pd.DataFrame()
    total_guardado = 0

    print("-" * 80)
    print(f"{'ARCHIVO':<45} | {'LEÍDOS':<10} | {'A GUARDAR'}")
    print("-" * 80)

    for file_info in archivos_nuevos:
        df_temp, stats = procesar_archivo_robusto(file_info)
        
        if df_temp is not None:
            print(f"{file_info.name[:45]:<45} | {stats['leidos']:<10} | {stats['guardados']}")
            df_lote = pd.concat([df_lote, df_temp], ignore_index=True)
            total_guardado += stats['guardados']
        else:
            print(f"{file_info.name[:45]:<45} | ERROR")

    print("-" * 80)
    print(f"📊 TOTAL NUEVOS REGISTROS: {total_guardado}")

    # 3. GUARDADO
    if not df_lote.empty:
        spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
        sdf = spark.createDataFrame(df_lote)
        
        sdf.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(TABLA_OUTPUT)
        print(f"\n✅ STAGING ACTUALIZADO: '{TABLA_OUTPUT}' listo con {total_guardado} registros.")
    else:
        print("\n⚠️ No se generaron registros válidos.")

main()



# In[2]:


print("🧹 Vaciando tabla de Staging (pd_cooplyf_aux)...")

try:
    spark.sql("TRUNCATE TABLE datos_generales.pd_cooplyf_aux")
    print("✅ Tabla vaciada correctamente. Ahora tiene 0 registros.")
except Exception as e:
    print(f"❌ Error al intentar vaciar: {e}")

