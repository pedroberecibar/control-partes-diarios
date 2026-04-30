"""
Genera los archivos Parquet de prueba (seeds, masters, dims) necesarios para
que el motor analítico pueda correr sin datos reales de Oracle.

No descarga nada de internet — todo es generado localmente con Pandas.

Tablas generadas
────────────────
data/seed/
  mapa_archivos.parquet          ARCHIVO_X, ID_ARCHIVO
  dim_ord.parquet                Órdenes de trabajo (CE y otras)
  eqp_equipos_ultimos_10.parquet Últimos medidores por suministro
  usuarios_gral.parquet          Operarios de CONECTAR y COOPLYF
  dim_stk_stock_equipos.parquet  Stock de equipos (fases)
  sigec_general.parquet          Geografía de suministros (para dims geo)
  pivot_resul_app_movil.parquet  Observaciones app móvil (vacío con schema)

data/master/
  mapeo_codigos_master.parquet   Códigos contratista ↔ COD_EPEC + USE
  reglas_cod_obs_app.parquet     Reglas de observaciones (literal de negocio)

data/dim/
  dim_traza_calidad_bi.parquet   Catálogo de trazas (13 valores)
  dim_estado_bi.parquet          Catálogo de estados (4 valores)
  dim_empresa_bi.parquet         Catálogo de empresas (CONECTAR / COOPLYF)
  dim_usuarios_bi.parquet        Dedup de usuarios_gral
  dim_archivo_bi.parquet         Archivos registrados (vacío — se llenará al procesar lotes)

Uso (desde python-version/):
    python scripts/generar_mock_parquets.py
"""
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from src import config
from src import io_lakehouse as io

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(nombre: str, capa: str, n: int) -> None:
    print(f"  OK  {capa}/{nombre}.parquet  ({n} filas)")


# =============================================================================
# SEEDS
# =============================================================================

def _seed_mapa_archivos() -> None:
    """Mapa ARCHIVO_X → ID_ARCHIVO.
    El worker usa esto para normalizar el nombre del archivo subido a un entero.
    Se crea vacío — a medida que se suban archivos reales se puede poblar vía
    dim_archivo_bi (que actualizar_dim_archivo mantiene automáticamente).
    """
    df = pd.DataFrame({
        "ARCHIVO_X": pd.Series(dtype="string"),
        "ID_ARCHIVO": pd.Series(dtype="int64"),
    })
    io.write_table(df, "mapa_archivos", capa="seed", mode="overwrite")
    _ok("mapa_archivos", "seed", len(df))


def _seed_dim_ord() -> None:
    """Órdenes de trabajo de muestra. El waterfall busca en esta tabla.
    Sin filas que matcheen los suministros del archivo COOPLYF, los partes
    quedarán como 'Sin Orden Asociada' (traza válida, no un crash).
    """
    t = pd.Timestamp
    df = pd.DataFrame({
        "ORD_NUMERO":           [100001, 100002, 100003, 100004, 100005,
                                 200001, 200002],
        "SRV_CODIGO":           [412881, 412882, 412883, 412881, 412884,
                                 500001, 500002],
        "TOR_CODIGO":           ["CE",   "CE",   "CE",   "MI",   "CE",
                                 "CE",   "TN"],
        "ORD_RESULTADO":        ["E",    "IN",   "E",    "E",    "D",
                                 "E",    "E"],
        "ORD_FECHA_FIN":        [t("2025-03-15"), t("2025-03-20"), t("2025-04-01"),
                                 t("2025-03-10"), t("2025-04-05"),
                                 t("2025-03-18"), t("2025-04-02")],
        "ORD_FECHA_INICIO":     [t("2025-03-10"), t("2025-03-15"), t("2025-03-28"),
                                 t("2025-03-05"), t("2025-03-30"),
                                 t("2025-03-13"), t("2025-03-28")],
        "SEC_CODIGO_ORIGEN":    ["COOPLYF", "COOPLYF", "CONECTAR", "CONECTAR", "COOPLYF",
                                 "CONECTAR", "COOPLYF"],
        "USR_NUMERO_EJEC_ORD":  [101, 102, 201, 201, 103,
                                 201, 101],
    })
    df["SRV_CODIGO"]          = df["SRV_CODIGO"].astype("Int64")
    df["USR_NUMERO_EJEC_ORD"] = df["USR_NUMERO_EJEC_ORD"].astype("Int64")
    df["ORD_FECHA_FIN"]       = df["ORD_FECHA_FIN"].astype("datetime64[us]")
    df["ORD_FECHA_INICIO"]    = df["ORD_FECHA_INICIO"].astype("datetime64[us]")
    io.write_table(df, "dim_ord", capa="seed", mode="overwrite")
    _ok("dim_ord", "seed", len(df))


def _seed_eqp_equipos_ultimos_10() -> None:
    """Últimos 10 medidores instalados por suministro (SIGEC).
    STE_NUMERO_ULTIMO = medidor colocado actual; STE_NUMERO_ANTERIOR_1 = el previo.
    """
    df = pd.DataFrame({
        "SRV_CODIGO":            [412881, 412882, 412883, 412884, 500001, 500002],
        "STE_NUMERO_ULTIMO":     [74829103.0, 74830200.0, 74831500.0,
                                  74832100.0, 74900001.0, 74900002.0],
        "STE_NUMERO_ANTERIOR_1": [74828900.0, 74830100.0, 74831200.0,
                                  74832000.0, 74899900.0, 74899901.0],
    })
    df["SRV_CODIGO"] = df["SRV_CODIGO"].astype("Int64")
    io.write_table(df, "eqp_equipos_ultimos_10", capa="seed", mode="overwrite")
    _ok("eqp_equipos_ultimos_10", "seed", len(df))


def _seed_usuarios_gral() -> None:
    """Operarios. USR_NUMERO debe coincidir con USR_NUMERO_EJEC_ORD en dim_ord."""
    df = pd.DataFrame({
        "USR_NUMERO": [101, 102, 103, 201, 202],
        "USR_NOMBRE": ["LOPEZ MARIO",   "GARCIA JUAN",  "PEREZ LUIS",
                       "FERNANDEZ ANA", "TORRES CARLOS"],
        "SEC_CODIGO": ["COOPLYF", "COOPLYF", "COOPLYF", "CONECTAR", "CONECTAR"],
    })
    df["USR_NUMERO"] = df["USR_NUMERO"].astype("Int64")
    df["USR_NOMBRE"] = df["USR_NOMBRE"].astype("string")
    df["SEC_CODIGO"] = df["SEC_CODIGO"].astype("string")
    io.write_table(df, "usuarios_gral", capa="seed", mode="overwrite")
    _ok("usuarios_gral", "seed", len(df))


def _seed_dim_stk_stock_equipos() -> None:
    """Medidores en stock con información de fase (MON/TRI)."""
    df = pd.DataFrame({
        "STE_NUMERO": [
            74829103.0, 74830200.0, 74831500.0, 74832100.0,
            74900001.0, 74900002.0, 74828900.0, 74830100.0,
        ],
        "STE_FASES": ["MON", "TRI", "MON", "TRI", "MON", "TRI", "MON", "MON"],
    })
    df["STE_NUMERO"] = df["STE_NUMERO"].astype("float64")
    df["STE_FASES"]  = df["STE_FASES"].astype("string")
    io.write_table(df, "dim_stk_stock_equipos", capa="seed", mode="overwrite")
    _ok("dim_stk_stock_equipos", "seed", len(df))


def _seed_sigec_general() -> None:
    """Tabla geográfica de suministros (SIGEC). Sólo la usa etapa3_dims_geo_calendario.
    Se crea con unas pocas filas para que el pipeline completo no falle en --stage 3.
    """
    df = pd.DataFrame({
        "SUMINISTRO":          [412881, 412882, 412883, 412884, 500001, 500002],
        "LATITUD":             [-31.4201, -31.4205, -31.4210, -31.4215, -31.4300, -31.4310],
        "LONGITUD":            [-64.1885, -64.1890, -64.1895, -64.1900, -64.1950, -64.1955],
        "CALLE":               ["SAN MARTIN", "COLON", "BELGRANO", "RIVADAVIA", "AV VELEZ", "MAIPU"],
        "ALTURA":              [100, 200, 300, 400, 500, 600],
        "BARRIO":              ["CENTRO", "CENTRO", "GENERAL PAZ", "GENERAL PAZ", "NUEVA CBA", "NUEVA CBA"],
        "DISTRITO_DESCRIPCION":["CAPITAL", "CAPITAL", "CAPITAL", "CAPITAL", "CAPITAL", "CAPITAL"],
        "ZONA":                ["ZON1", "ZON1", "ZON2", "ZON2", "ZON3", "ZON3"],
    })
    df["SUMINISTRO"] = df["SUMINISTRO"].astype("Int64")
    df["LATITUD"]    = df["LATITUD"].astype("float64")
    df["LONGITUD"]   = df["LONGITUD"].astype("float64")
    df["ALTURA"]     = df["ALTURA"].astype("Int64")
    io.write_table(df, "sigec_general", capa="seed", mode="overwrite")
    _ok("sigec_general", "seed", len(df))


def _seed_pivot_resul_app_movil() -> None:
    """Pivot de observaciones de la app móvil por orden de trabajo.
    Se crea vacío con el schema correcto — se llenará cuando haya datos reales.
    Los nombres de columnas con comillas simples replican el Parquet de Fabric.
    """
    obs_cols = {
        "'APP4SITIO_3'": pd.Series(dtype="object"),
        "'APP4SITIO_4'": pd.Series(dtype="object"),
        "'APP4SITIO_2'": pd.Series(dtype="object"),
        "'APP4SITIO_1'": pd.Series(dtype="object"),
        "'APP4TRAB_1'":  pd.Series(dtype="object"),
        "'APP4TRAB_2'":  pd.Series(dtype="object"),
        "'APP4TRAB_3'":  pd.Series(dtype="object"),
        "'APP4TRAB_4'":  pd.Series(dtype="object"),
    }
    img_cols = {
        "'APP4OBS_80'_TOB_DESCRIPCION": pd.Series(dtype="object"),
        "'APP4OBS_81'_TOB_DESCRIPCION": pd.Series(dtype="object"),
        "'APP4OBS_82'_TOB_DESCRIPCION": pd.Series(dtype="object"),
        "'APP4OBS_83'_TOB_DESCRIPCION": pd.Series(dtype="object"),
        "'APP4OBS_84'_TOB_DESCRIPCION": pd.Series(dtype="object"),
    }
    df = pd.DataFrame({"ORD_NUMERO": pd.Series(dtype="int64"), **obs_cols, **img_cols})
    io.write_table(df, "pivot_resul_app_movil", capa="seed", mode="overwrite")
    _ok("pivot_resul_app_movil", "seed", len(df))


# =============================================================================
# MASTERS
# =============================================================================

def _master_mapeo_codigos_master() -> None:
    """Mapeo de códigos de tarea del contratista → COD_EPEC + valor USE.
    Incluye los códigos más frecuentes de COOPLYF y CONECTAR.
    FASE: 'MON'=monofásico, 'TRI'=trifásico, 'AMBAS'=ambas fases.
    """
    rows = [
        # CONTRATISTA  COD_IND  FASE    COD_EPEC  DESCRIPCION                               USE
        ("COOPLYF",    "07",    "AMBAS",  7,  "Cambio de equipo",                          0.0600),
        ("COOPLYF",    "07A",   "AMBAS",  7,  "Cambio de equipo",                          0.0600),
        ("COOPLYF",    "22",    "MON",   22,  "Normalización Monofasica Aérea SIN tapa",   0.1860),
        ("COOPLYF",    "01",    "TRI",    1,  "Normalización Trifasica Aérea",             0.7600),
        ("COOPLYF",    "25",    "MON",   25,  "Normalización Monofasica Altura",           0.3600),
        ("COOPLYF",    "15",    "TRI",   15,  "Normalización Trifasica Altura",            1.0000),
        ("COOPLYF",    "02",    "MON",    2,  "Normalización Monofasica Aérea",            0.3100),
        ("COOPLYF",    "43",    "AMBAS", 43,  "Cambio equipo Monofasico con tapa",         0.1000),
        ("COOPLYF",    "44",    "AMBAS", 44,  "Cambio equipo Trifasico con tapa",          0.1000),
        ("COOPLYF",    "11",    "AMBAS", 11,  "Informado",                                 0.0100),
        ("CONECTAR",   "07",    "AMBAS",  7,  "Cambio de equipo",                          0.0600),
        ("CONECTAR",   "22",    "MON",   22,  "Normalización Monofasica Aérea SIN tapa",   0.1860),
        ("CONECTAR",   "01",    "TRI",    1,  "Normalización Trifasica Aérea",             0.7600),
        ("CONECTAR",   "25",    "MON",   25,  "Normalización Monofasica Altura",           0.3600),
        ("CONECTAR",   "15",    "TRI",   15,  "Normalización Trifasica Altura",            1.0000),
        ("CONECTAR",   "02",    "MON",    2,  "Normalización Monofasica Aérea",            0.3100),
        ("CONECTAR",   "43",    "AMBAS", 43,  "Cambio equipo Monofasico con tapa",         0.1000),
        ("CONECTAR",   "44",    "AMBAS", 44,  "Cambio equipo Trifasico con tapa",          0.1000),
        ("CONECTAR",   "11",    "AMBAS", 11,  "Informado",                                 0.0100),
    ]
    df = pd.DataFrame(rows, columns=[
        "CONTRATISTA", "COD_CONTRATISTA_INDIVIDUAL", "FASE",
        "COD_EPEC", "DESCRIPCION_CODIGO", "cant_USE_unitario",
    ])
    df["CONTRATISTA"]               = df["CONTRATISTA"].astype("string")
    df["COD_CONTRATISTA_INDIVIDUAL"] = df["COD_CONTRATISTA_INDIVIDUAL"].astype("string")
    df["FASE"]                      = df["FASE"].astype("string")
    df["COD_EPEC"]                  = df["COD_EPEC"].astype("int64")
    df["DESCRIPCION_CODIGO"]        = df["DESCRIPCION_CODIGO"].astype("string")
    df["cant_USE_unitario"]         = df["cant_USE_unitario"].astype("float64")
    io.write_table(df, "mapeo_codigos_master", capa="master", mode="overwrite")
    _ok("mapeo_codigos_master", "master", len(df))


def _master_reglas_cod_obs_app() -> None:
    """Reglas de observaciones — literal de negocio (ya está en etapa1_maestros).
    Se importa directamente para no duplicar el dato.
    """
    from src.etapa1_maestros import generar_reglas_cod_obs_app
    df = generar_reglas_cod_obs_app()
    _ok("reglas_cod_obs_app", "master", len(df))


# =============================================================================
# DIMS (normalmente generadas por etapa3_dims_bi.run())
# =============================================================================

def _dims_bi() -> None:
    """Genera las tablas de dimensiones BI a partir de los datos seed ya creados."""
    from src.etapa3_dims_bi import (
        generar_dim_empresa_bi,
        generar_dim_estado_bi,
        generar_dim_traza_calidad_bi,
        generar_dim_usuarios_bi,
    )

    df = generar_dim_empresa_bi()
    _ok("dim_empresa_bi", "dim", len(df))

    df = generar_dim_estado_bi()
    _ok("dim_estado_bi", "dim", len(df))

    df = generar_dim_traza_calidad_bi()
    _ok("dim_traza_calidad_bi", "dim", len(df))

    df = generar_dim_usuarios_bi()      # lee usuarios_gral (seed recién creado)
    _ok("dim_usuarios_bi", "dim", len(df))

    # dim_archivo_bi vacío — se pobla automáticamente al procesar el primer lote
    df_arch = pd.DataFrame({
        "ID_ARCHIVO":    pd.Series(dtype="int64"),
        "NOMBRE_ARCHIVO": pd.Series(dtype="string"),
    })
    io.write_table(df_arch, "dim_archivo_bi", capa="dim", mode="overwrite")
    _ok("dim_archivo_bi", "dim", 0)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    config.ensure_layout()
    print("\n-- Seeds --------------------------------------------------")
    _seed_mapa_archivos()
    _seed_dim_ord()
    _seed_eqp_equipos_ultimos_10()
    _seed_usuarios_gral()
    _seed_dim_stk_stock_equipos()
    _seed_sigec_general()
    _seed_pivot_resul_app_movil()

    print("\n-- Masters ------------------------------------------------")
    _master_mapeo_codigos_master()
    _master_reglas_cod_obs_app()

    print("\n-- Dims BI ------------------------------------------------")
    _dims_bi()

    print(f"\nListo. Parquets en: {config.DATA}")


if __name__ == "__main__":
    main()
