"""Etapa 1 — Maestros.

Portado de `pyspark-version/act_mapeo_cod_contratistas_epec.py` + celda 1
de `control_obs_pd_ce.py` (reglas de observaciones).

Genera dos tablas estáticas:

  - master/mapeo_codigos_master.parquet
      Cruce de códigos de contratista vs. códigos EPEC + valor USE unitario.
      Es la tabla que usa el Core para asignar COD_EPEC y cant_USE_unitario
      a cada parte.

  - master/reglas_cod_obs_app.parquet
      21 reglas (combinaciones válidas de observaciones por código) que usa
      la etapa 4 para calcular discrepancias y valoración económica.
"""

from __future__ import annotations

import logging

import pandas as pd

from . import config
from . import io_lakehouse as io

log = logging.getLogger(__name__)


# =============================================================================
# 1) Mapeo de códigos (Excel) + USES (Excel) → mapeo_codigos_master
# =============================================================================

def _construir_mapeo_codigos() -> pd.DataFrame:
    """Lee el Excel base y explota `CODIGOS_CONTRATISTA` por coma."""
    log.info("Leyendo Excel de mapeo: %s (hoja %s)", config.FILE_MAPEO, config.HOJA_MAPEO)
    df = pd.read_excel(config.FILE_MAPEO, sheet_name=config.HOJA_MAPEO)

    # Normalización de nombres: espacios → "_" y upper (idéntico a la versión Spark).
    df.columns = [c.replace(" ", "_").upper() for c in df.columns]

    # Explode del string "001, 002, 003" → una fila por código.
    df["COD_CONTRATISTA_INDIVIDUAL"] = df["CODIGOS_CONTRATISTA"].astype("string").str.split(",")
    df = df.explode("COD_CONTRATISTA_INDIVIDUAL", ignore_index=True)

    df["COD_CONTRATISTA_INDIVIDUAL"] = df["COD_CONTRATISTA_INDIVIDUAL"].str.strip()
    df["FASE"] = df["FASE"].astype("string").str.strip()

    df = df.rename(columns={"CODIGOS_F218": "COD_EPEC"})
    df = df[[
        "CONTRATISTA", "COD_CONTRATISTA_INDIVIDUAL", "FASE",
        "COD_EPEC", "DESCRIPCION_CODIGO",
    ]].drop_duplicates(ignore_index=True)

    return df


def _construir_tabla_uses() -> pd.DataFrame:
    """Lee OP_MI.xlsx (Hoja2) y normaliza código + USE unitario."""
    log.info("Leyendo Excel de USEs: %s (hoja %s)", config.FILE_USES, config.HOJA_USES)
    df = pd.read_excel(config.FILE_USES, sheet_name=config.HOJA_USES)

    # CODIGO_JOIN: string sin ".0" espurio si pandas lo leyó como float.
    df["CODIGO_JOIN"] = (
        df["CODIGOS"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    )

    # Valor USE: puede venir con coma decimal — normalizar a punto y a float.
    df["cant_USE_unitario"] = (
        df["Cant. USE Unitario"].astype("string").str.replace(",", ".", regex=False)
    )
    df["cant_USE_unitario"] = pd.to_numeric(df["cant_USE_unitario"], errors="coerce").fillna(0.0)

    return df[["CODIGO_JOIN", "cant_USE_unitario"]]


def _cruzar_mapeo_con_uses(df_mapeo: pd.DataFrame, df_uses: pd.DataFrame) -> pd.DataFrame:
    """Left join por COD_EPEC (string) ↔ CODIGO_JOIN."""
    df = df_mapeo.copy()
    df["COD_EPEC_JOIN"] = df["COD_EPEC"].astype("string")

    df_final = df.merge(
        df_uses, how="left", left_on="COD_EPEC_JOIN", right_on="CODIGO_JOIN",
    ).drop(columns=["COD_EPEC_JOIN", "CODIGO_JOIN"])

    return df_final


def generar_mapeo_codigos_master() -> pd.DataFrame:
    df_mapeo = _construir_mapeo_codigos()
    df_uses  = _construir_tabla_uses()
    df_final = _cruzar_mapeo_con_uses(df_mapeo, df_uses)

    io.write_table(df_final, "mapeo_codigos_master", capa="master", mode="overwrite")

    n_total   = len(df_final)
    n_con_use = int((df_final["cant_USE_unitario"].fillna(0) > 0).sum())
    log.info("mapeo_codigos_master: %d filas; con USE asignado: %d", n_total, n_con_use)
    return df_final


# =============================================================================
# 2) Reglas estáticas de observaciones por código → reglas_cod_obs_app
# =============================================================================

# Datos literales copiados tal cual de la celda 1 de control_obs_pd_ce.py.
# NO simplificar — son reglas de negocio validadas por el equipo funcional.
_DATOS_REGLAS: list[tuple] = [
    # COD  DESCRIPCION                                                            GAB SUB ALT AER MED ACO TAP INS   USES
    (  22, "Normalización Monofasica Aérea SIN tapa",                               0,  0,  0,  1,  1,  1,  0,  1, 0.1860),
    (  44, "Cambio de equipo Trifasico con tapa (subterraneo)",                     0,  1,  0,  0,  1,  0,  1,  1, 0.1000),
    (  44, "Cambio de equipo Trifasico con tapa (aereo)",                           0,  0,  0,  1,  1,  0,  1,  1, 0.1000),
    (  44, "Cambio de equipo Trifasico con tapa (altura)",                          0,  0,  1,  0,  1,  0,  1,  1, 0.1000),
    (  43, "Cambio de equipo Monofasico con tapa (subterraneo)",                    0,  1,  0,  0,  1,  0,  1,  1, 0.1000),
    (  43, "Cambio de equipo Monofasico con tapa (aereo)",                          0,  0,  0,  1,  1,  0,  1,  1, 0.1000),
    (  43, "Cambio de equipo Monofasico con tapa (altura)",                         0,  0,  1,  0,  1,  0,  1,  1, 0.1000),
    (  11, "Informado",                                                             0,  0,  0,  0,  0,  0,  1,  0, 0.0100),
    (  12, "Normalización Trifasica Aérea SIN tapa",                                0,  0,  0,  1,  1,  1,  0,  1, 0.4560),
    (   1, "Normalización Trifasica Aérea",                                         0,  0,  0,  1,  1,  1,  0,  1, 0.7600),
    (  15, "Normalización Trifasica en Altura con cambio de tapa",                  0,  0,  1,  0,  1,  1,  1,  1, 1.0000),
    (  15, "Normalización Trifasica en Altura sin cambio de tapa",                  0,  0,  1,  0,  1,  1,  0,  1, 1.0000),
    (  15, "Normalización Trifasica en linea Aerea con Cruce de calle",             0,  0,  1,  0,  1,  1,  1,  1, 1.0000),
    (   7, "Cambio de equipo (en gabinete)",                                        1,  0,  0,  0,  1,  0,  0,  1, 0.0600),
    (   7, "Cambio de equipo (subterraneo)",                                        0,  1,  0,  0,  1,  0,  0,  1, 0.0600),
    (   7, "Cambio de equipo (aereo)",                                              0,  0,  0,  1,  1,  0,  0,  1, 0.0600),
    (   7, "Cambio de equipo (altura)",                                             0,  0,  1,  0,  1,  0,  0,  1, 0.0600),
    (  25, "Normalización Monofasica Altura con cambio de tapa",                    0,  0,  1,  0,  1,  1,  1,  1, 0.3600),
    (  25, "Normalización Monofasica Altura sin cambio de tapa",                    0,  0,  1,  0,  1,  1,  0,  1, 0.3600),
    (  25, "Normalización Monofasica en linea Aerea con Cruce de calle",            0,  0,  1,  0,  1,  1,  0,  1, 0.3600),
    (   2, "Normalización Monofasica Aérea",                                        0,  0,  0,  1,  1,  1,  1,  1, 0.3100),
]

_COLS_REGLAS = [
    "COD_EPEC", "DESCRIPCION",
    "GABINETE", "SUBTERRANEO", "ALTURA", "AEREO",
    "EQUIPO_MEDICION_REEMPLAZADO", "ACOMETIDA_REALIZADA",
    "TAPA_REEMPLAZADA", "EQUIPO_DE_MEDICION_INSTALADO",
    "VALOR_USES",
]


def generar_reglas_cod_obs_app() -> pd.DataFrame:
    df = pd.DataFrame(_DATOS_REGLAS, columns=_COLS_REGLAS)
    df = df.astype({
        "COD_EPEC": "int64",
        "DESCRIPCION": "string",
        "GABINETE": "int8",
        "SUBTERRANEO": "int8",
        "ALTURA": "int8",
        "AEREO": "int8",
        "EQUIPO_MEDICION_REEMPLAZADO": "int8",
        "ACOMETIDA_REALIZADA": "int8",
        "TAPA_REEMPLAZADA": "int8",
        "EQUIPO_DE_MEDICION_INSTALADO": "int8",
        "VALOR_USES": "float64",
    })
    io.write_table(df, "reglas_cod_obs_app", capa="master", mode="overwrite")
    log.info("reglas_cod_obs_app: %d reglas escritas", len(df))
    return df


# =============================================================================
# Entrypoint
# =============================================================================

def run() -> dict:
    """Ejecuta la etapa completa. Devuelve métricas para el orquestador."""
    config.ensure_layout()
    df_mapeo  = generar_mapeo_codigos_master()
    df_reglas = generar_reglas_cod_obs_app()
    return {
        "mapeo_codigos_master": len(df_mapeo),
        "reglas_cod_obs_app":   len(df_reglas),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    metricas = run()
    print(metricas)
