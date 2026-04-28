"""Etapa 3.4 — Dimensiones derivadas de la fact: geo + calendario.

Portado de las Celdas 5 y 6 de `pyspark-version/procesar_pd_gral_refactor (5).py`.

Las dos dimensiones se construyen DESPUÉS del MERGE de la fact (a diferencia
de las estáticas de `etapa3_dims_bi.py`, que pueden generarse antes), porque:

  - `dim_suministros_geo` filtra `sigec_general` (seed, 1.2M filas) por los
    SRV_CODIGO únicos que aparecen en la fact — sino traeríamos suministros
    que nadie consume.
  - `dim_calendario` construye el rango exacto FECHA_MIN..FECHA_MAX de la fact.

Diferencias contra el PySpark original (documentadas en plan §0.2.1):

  - `SUMI` (Fabric) ↔ `SUMINISTRO` (parquet local): el seed que generó
    `etapa0_seeds` desde `GEOREF.VM_SUMINISTROS` mantiene el nombre original
    `SUMINISTRO`. Se renombra a `SRV_CODIGO` (alias canónico) en este módulo.
  - `LATITUD`/`LONGITUD` ya vienen como float64 → no aplica `regexp_replace`.
  - `DPTO` (Fabric) ↔ `DISTRITO_DESCRIPCION` (parquet local): el seed actual
    no expone una columna llamada `DPTO`. Se mapea a `DEPARTAMENTO` desde
    `DISTRITO_DESCRIPCION` (texto), que es lo que el dashboard necesita
    mostrar al usuario. Si Power BI espera código en lugar de descripción,
    cambiar a `DISTRITO`.
  - `DIRECCION` no existe en el seed → se construye como `CALLE + ALTURA`.
  - `PLAN` no existe en el seed → omitida.
"""

from __future__ import annotations

import logging

import pandas as pd

from . import config
from . import io_lakehouse as io

log = logging.getLogger(__name__)


# =============================================================================
# 3.4.a — dim_suministros_geo
# =============================================================================

# Columnas mínimas a proyectar del seed (proyectar reduce ~95% el peso, dado
# que sigec_general tiene 91 columnas y nosotros usamos 9).
_COLS_SIGEC_GEO = [
    "SUMINISTRO", "LATITUD", "LONGITUD",
    "CALLE", "ALTURA", "BARRIO", "DISTRITO_DESCRIPCION", "ZONA",
]

_COLS_DIM_GEO_OUTPUT = [
    "SRV_CODIGO", "LATITUD", "LONGITUD",
    "CALLE", "DIRECCION", "ALTURA",
    "DEPARTAMENTO", "BARRIO", "ZONA",
]


def generar_dim_suministros_geo() -> pd.DataFrame:
    """Inner-join de SRV_CODIGO únicos de la fact con sigec_general (seed)."""
    df_fact_ids = io.read_table(
        "fact_partes_diarios_full", capa="gold", columns=["SRV_CODIGO"]
    )
    fact_ids = (
        df_fact_ids["SRV_CODIGO"]
        .dropna().drop_duplicates()
        .astype("Int64").to_frame(name="SRV_CODIGO")
    )

    df_sigec = io.read_table("sigec_general", capa="seed", columns=_COLS_SIGEC_GEO)

    # SUMINISTRO → SRV_CODIGO (alias canónico, plan §0.2.1).
    df_sigec = df_sigec.rename(columns={
        "SUMINISTRO": "SRV_CODIGO",
        "DISTRITO_DESCRIPCION": "DEPARTAMENTO",
    })
    df_sigec["SRV_CODIGO"] = df_sigec["SRV_CODIGO"].astype("Int64")
    df_sigec["LATITUD"]    = pd.to_numeric(df_sigec["LATITUD"],  errors="coerce")
    df_sigec["LONGITUD"]   = pd.to_numeric(df_sigec["LONGITUD"], errors="coerce")
    df_sigec["ALTURA"]     = pd.to_numeric(df_sigec["ALTURA"],   errors="coerce").astype("Int64")

    # DIRECCION = "CALLE ALTURA" (compat con la columna que Power BI espera).
    calle  = df_sigec["CALLE"].astype("string").fillna("")
    altura = df_sigec["ALTURA"].astype("string").fillna("")
    direccion = (calle + " " + altura).str.strip()
    df_sigec["DIRECCION"] = direccion.where(direccion != "", pd.NA).astype("string")

    df_sigec = df_sigec[_COLS_DIM_GEO_OUTPUT]

    df_dim_geo = (
        df_sigec.merge(fact_ids, on="SRV_CODIGO", how="inner")
        .drop_duplicates(subset=["SRV_CODIGO"])
        .reset_index(drop=True)
    )

    io.write_table(df_dim_geo, "dim_suministros_geo", capa="dim", mode="overwrite")

    n_fact, n_geo = len(fact_ids), len(df_dim_geo)
    cobertura = (100 * n_geo / n_fact) if n_fact else 0.0
    log.info("dim_suministros_geo: %d / %d suministros con coordenadas (%.1f%%).",
             n_geo, n_fact, cobertura)
    if n_fact > n_geo:
        log.info("  %d suministro(s) sin coordenadas en SIGEC.", n_fact - n_geo)
    return df_dim_geo


# =============================================================================
# 3.4.b — dim_calendario
# =============================================================================

def generar_dim_calendario() -> pd.DataFrame:
    """Calendario denso entre FECHA_MIN y FECHA_MAX de la fact."""
    df_fact = io.read_table("fact_partes_diarios_full", capa="gold", columns=["FECHA"])
    fechas = pd.to_datetime(df_fact["FECHA"], errors="coerce").dropna()

    if fechas.empty:
        fecha_inicio = pd.Timestamp("2024-01-01")
        fecha_fin    = pd.Timestamp("2025-12-31")
        log.warning("Fact sin FECHA válida → rango default %s a %s.",
                    fecha_inicio.date(), fecha_fin.date())
    else:
        fecha_inicio = fechas.min().normalize()
        fecha_fin    = fechas.max().normalize()
        log.info("dim_calendario: rango %s → %s.",
                 fecha_inicio.date(), fecha_fin.date())

    rango = pd.date_range(fecha_inicio, fecha_fin, freq="D")
    df_cal = pd.DataFrame({
        "Date":    rango,
        "Año":    rango.year.astype("int64"),
        "MesNro":  rango.month.astype("int64"),
        # Spark `date_format(d, "MMM")` → abreviatura inglesa ("Jan", "Feb"...).
        # `strftime("%b")` reproduce ese formato (asumiendo locale C, que es el
        # que pandas usa por defecto independiente del locale del SO).
        "Mes":     rango.strftime("%b"),
        "Semana":  rango.isocalendar().week.astype("int64").to_numpy(),
        "Periodo": rango.strftime("%Y-%m"),
    })

    io.write_table(df_cal, "dim_calendario", capa="dim", mode="overwrite")
    log.info("dim_calendario: %d días.", len(df_cal))
    return df_cal


# =============================================================================
# Entrypoint
# =============================================================================

def run() -> dict:
    """Ejecuta 3.4.a + 3.4.b. Asume que la fact ya está poblada."""
    config.ensure_layout()
    if not io.table_exists("fact_partes_diarios_full", capa="gold"):
        log.warning("fact_partes_diarios_full no existe — saltando dims geo/calendario.")
        return {"dim_suministros_geo": 0, "dim_calendario": 0, "skipped": True}

    df_geo = generar_dim_suministros_geo()
    df_cal = generar_dim_calendario()
    return {
        "dim_suministros_geo": len(df_geo),
        "dim_calendario":      len(df_cal),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
