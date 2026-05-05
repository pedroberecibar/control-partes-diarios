"""Etapa 0 — Extracción de seeds desde Oracle (PRODEBS_SEE).

Pone en `data/seed/` las 6 tablas que el Core (Etapa 3) consume:

  | Tabla                       | Estrategia                                              |
  |-----------------------------|---------------------------------------------------------|
  | dim_ord                     | bootstrap (>=2025-01-01) si no existe; sino MERGE incr. |
  | usuarios_gral               | overwrite full                                          |
  | dim_stk_stock_equipos       | overwrite full                                          |
  | sigec_general               | overwrite full (desde GEOREF.VM_SUMINISTROS)             |
  | pivot_resul_app_movil       | overwrite full (pivot SQL en Oracle)                    |
  | eqp_equipos_ultimos_10      | filtrado por SRV_CODIGOs del staging+fact + pivot local |

`refresh_eqp_ultimos_10()` requiere que stage/pd_*_aux estén poblados, así
que en el orquestador va DESPUÉS de etapa2.

La conexión Oracle usa `OracleReadOnly` (sesión `READ ONLY` server-side).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Iterable

import numpy as np
import pandas as pd

from . import config
from . import io_lakehouse as io
from .oracle_io import OracleReadOnly

log = logging.getLogger(__name__)

CHUNKSIZE_ORACLE = 100_000   # filas por fetch (bootstrap dim_ord)
CHUNK_IN_LIST    = 900       # tope < 1000 (Oracle IN-list limit)

# Rango razonable para timestamps: Oracle a veces devuelve fechas sentinel
# tipo año 0010, que no caben en datetime64[ns] (~1677–2262). Replica el clip
# de los cuadernos Fabric (nb_equipo_eqp_instalados.py L.41-65).
_FECHA_MIN_VALIDA = pd.Timestamp("1899-12-30")
_FECHA_MAX_VALIDA = pd.Timestamp("9999-12-31 23:59:59")


def _normalizar_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """Clip de timestamps fuera de rango + normaliza resolución a [us].

    Oracle puede devolver timestamps con resolución [us] o [ns] según el
    chunk; la promoción de schemas falla si hay fechas fuera de rango [ns].
    Forzamos todas a [us] (rango muy amplio) y reemplazamos las basura por NaT.
    """
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            mask_basura = df[col].notna() & (
                (df[col] < _FECHA_MIN_VALIDA) | (df[col] > _FECHA_MAX_VALIDA)
            )
            if mask_basura.any():
                df[col] = df[col].mask(mask_basura)
            df[col] = df[col].astype("datetime64[us]")
    return df


def _chunks_normalizados(chunks_iter):
    """Wrapper que aplica `_normalizar_fechas` a cada chunk perezosamente."""
    for chunk in chunks_iter:
        if chunk is None or len(chunk) == 0:
            continue
        yield _normalizar_fechas(chunk)


# =============================================================================
# Queries SQL — fuente de verdad: docs/masters_actualization.md
# =============================================================================

_SQL_DIM_ORD_BOOTSTRAP = """
    SELECT *
    FROM xxsigec.ordenativos ord
    WHERE ord.ord_fecha_fin           >= TO_DATE('2025-01-01','YYYY-MM-DD')
       OR ord.ord_fecha_inicio        >= TO_DATE('2025-01-01','YYYY-MM-DD')
       OR ord.ord_ultima_actualizacion >= TO_DATE('2025-01-01','YYYY-MM-DD')
"""

_SQL_DIM_ORD_INCREMENTAL = """
    SELECT *
    FROM xxsigec.ordenativos ord
    WHERE TRUNC(ord.ord_fecha_generacion)    >= TRUNC(SYSDATE - 4)
       OR TRUNC(ord.ord_ultima_actualizacion) >= TRUNC(SYSDATE - 4)
"""

_SQL_USUARIOS = "SELECT * FROM XXSIGEC.XXCO_USUARIOS_V"

_SQL_STOCK_EQUIPOS = """
    SELECT
        stk.STE_NUMERO, stk.STE_FACTOR_EQUIPO, stk.SCF_CODIGO,
        stk.STE_AMPERAJE, stk.STE_MARCA, stk.STE_FECHA_BAJA,
        stk.STE_TIPO, stk.STE_TENSION, stk.STE_SERIE,
        stk.STE_PRECINTO, stk.STE_MODELO, stk.STE_ESTADO,
        stk.STE_ANIO_FABRICACION, stk.STE_DESCRIPCION,
        stk.STE_CLASE, stk.STE_FECHA_ALTA,
        TO_CHAR(stk.STE_AMPERAJE_MAXIMO)  AS AMPERAJE_MAXIMO_MEDIDOR,
        TO_CHAR(stk.STE_AMPERAJE_NOMINAL) AS AMPERAJE_NOMINAL_MEDIDOR,
        stk.STE_FASES, stk.STE_HORARIOS,
        stk.STE_MIDE_ACTIVA, stk.STE_MIDE_HORA, stk.STE_MIDE_POTENCIA,
        stk.STE_MIDE_REACTIVA, stk.STE_MIGRADO, stk.GRC_CODIGO
    FROM XXSIGEC.STOCK_EQUIPOS stk
"""

_SQL_VM_SUMINISTROS = "SELECT * FROM GEOREF.VM_SUMINISTROS"

# Obs (TOB_DESCRIPCION) y fotos (OBO_INFO_ADICIONAL) usan columnas distintas en el pivot,
# por eso se consultan en dos sub-pivots separados y se unen por ORD_NUMERO.
_SQL_PIVOT_APP_MOVIL = """
    SELECT a.ORD_NUMERO,
           a."GABINETE",
           a."SUBTERRANEO",
           a."ALTURA",
           a."AEREO",
           a."EQUIPO_MEDICION_REEMPLAZADO",
           a."ACOMETIDA_REALIZADA",
           a."TAPA_REEMPLAZADA",
           a."EQUIPO_DE_MEDICION_INSTALADO",
           b."IMAGEN_1",
           b."IMAGEN_2",
           b."IMAGEN_3",
           b."IMAGEN_4",
           b."IMAGEN_5"
    FROM (
        SELECT *
        FROM (
            SELECT obs.ORD_NUMERO, obs.TOB_CODIGO, obs.TOB_DESCRIPCION
            FROM xxsigec.xxco_observaciones_ordenativ_v obs,
                 xxsigec.ordenativos ord
            WHERE ord.ord_numero        = obs.ord_numero
              AND ord.tor_codigo        = 'CE'
              AND ord.sec_codigo_origen = 'PROTELEM'
        )
        PIVOT (
            MAX(TOB_DESCRIPCION)
            FOR TOB_CODIGO IN (
                'APP4SITIO_3' AS "GABINETE",
                'APP4SITIO_4' AS "SUBTERRANEO",
                'APP4SITIO_2' AS "ALTURA",
                'APP4SITIO_1' AS "AEREO",
                'APP4TRAB_1'  AS "EQUIPO_MEDICION_REEMPLAZADO",
                'APP4TRAB_2'  AS "ACOMETIDA_REALIZADA",
                'APP4TRAB_3'  AS "TAPA_REEMPLAZADA",
                'APP4TRAB_4'  AS "EQUIPO_DE_MEDICION_INSTALADO"
            )
        )
    ) a
    LEFT JOIN (
        SELECT *
        FROM (
            SELECT obs.ORD_NUMERO, obs.TOB_CODIGO, obs.OBO_INFO_ADICIONAL
            FROM xxsigec.xxco_observaciones_ordenativ_v obs,
                 xxsigec.ordenativos ord
            WHERE ord.ord_numero        = obs.ord_numero
              AND ord.tor_codigo        = 'CE'
              AND ord.sec_codigo_origen = 'PROTELEM'
        )
        PIVOT (
            MAX(OBO_INFO_ADICIONAL)
            FOR TOB_CODIGO IN (
                'APP4OBS_80' AS "IMAGEN_1",
                'APP4OBS_81' AS "IMAGEN_2",
                'APP4OBS_82' AS "IMAGEN_3",
                'APP4OBS_83' AS "IMAGEN_4",
                'APP4OBS_84' AS "IMAGEN_5"
            )
        )
    ) b ON a.ORD_NUMERO = b.ORD_NUMERO
"""

# Columnas que el pivot top-10 produce por equipo (ver cuaderno Fabric v2:
# docs/cuadernos/eqp_equipos_tabla_pivot_ultimo_10_med.py).
_EQP_COLS_PIVOT = [
    "STE_NUMERO", "EQP_FECHA_INSTAL", "EQP_PRECINTO", "EQP_FECHA_RETIRO",
    "EQP_ESTADO", "EQP_OBSERVACIONES",
    "FACTOR_CORRIENTE_MEDIDOR", "FACTOR_TENSION_MEDIDOR",
    "EQP_PROGRAMA", "EQP_ULTIMA_ACTUALIZACION",
]


# =============================================================================
# Refresh por tabla
# =============================================================================

def refresh_usuarios_gral() -> dict:
    log.info("[seeds] refrescando usuarios_gral (full)...")
    t0 = time.perf_counter()
    with OracleReadOnly() as ora:
        df = ora.read_sql(_SQL_USUARIOS)
    df = _normalizar_fechas(df)
    io.write_table(df, "usuarios_gral", capa="seed", mode="overwrite")
    return {"tabla": "usuarios_gral", "filas": len(df),
            "seg": round(time.perf_counter() - t0, 2)}


def refresh_dim_stk_stock_equipos() -> dict:
    log.info("[seeds] refrescando dim_stk_stock_equipos (full, ~2.2M filas)...")
    t0 = time.perf_counter()
    with OracleReadOnly() as ora:
        chunks_iter = ora.read_sql(_SQL_STOCK_EQUIPOS, chunksize=CHUNKSIZE_ORACLE)
        _, total = io.write_table_chunked(
            _chunks_normalizados(chunks_iter), "dim_stk_stock_equipos", capa="seed"
        )
    return {"tabla": "dim_stk_stock_equipos", "filas": total,
            "seg": round(time.perf_counter() - t0, 2)}


def refresh_sigec_general() -> dict:
    """Persiste GEOREF.VM_SUMINISTROS como `sigec_general` (nombre que espera el Core).

    El mapeo de columnas (ej. SUMINISTRO → SUMI/SRV_CODIGO) lo hace la
    Etapa 3.4 al derivar `dim_suministros_geo`. Acá dejamos los datos crudos.
    """
    log.info("[seeds] refrescando sigec_general (full, ~1.2M filas, 91 cols)...")
    t0 = time.perf_counter()
    with OracleReadOnly() as ora:
        chunks_iter = ora.read_sql(_SQL_VM_SUMINISTROS, chunksize=CHUNKSIZE_ORACLE)
        _, total = io.write_table_chunked(
            _chunks_normalizados(chunks_iter), "sigec_general", capa="seed"
        )
    return {"tabla": "sigec_general", "filas": total,
            "seg": round(time.perf_counter() - t0, 2)}


def refresh_pivot_resul_app_movil() -> dict:
    log.info("[seeds] refrescando pivot_resul_app_movil (~285k filas, ~60s)...")
    t0 = time.perf_counter()
    with OracleReadOnly() as ora:
        df = ora.read_sql(_SQL_PIVOT_APP_MOVIL)
    df = _normalizar_fechas(df)
    io.write_table(df, "pivot_resul_app_movil", capa="seed", mode="overwrite")
    return {"tabla": "pivot_resul_app_movil", "filas": len(df),
            "seg": round(time.perf_counter() - t0, 2)}


def refresh_dim_ord(modo: str | None = None) -> dict:
    """Refresca dim_ord. `modo`:

      - `'bootstrap'`: trae todo desde 2025-01-01 (overwrite). Usado en la
        primera corrida.
      - `'incremental'`: trae los últimos 4 días por fecha_generacion o
        ord_ultima_actualizacion y MERGE local por ORD_NUMERO.
      - `None` (default): autodetect — bootstrap si no existe la tabla local,
        incremental si ya existe.
    """
    if modo is None:
        modo = "bootstrap" if not io.table_exists("dim_ord", capa="seed") else "incremental"

    if modo == "bootstrap":
        log.info("[seeds] dim_ord — BOOTSTRAP (>=2025-01-01, ~5.7M filas, streaming)...")
        t0 = time.perf_counter()
        with OracleReadOnly() as ora:
            chunks_iter = ora.read_sql(_SQL_DIM_ORD_BOOTSTRAP, chunksize=CHUNKSIZE_ORACLE)
            _, total = io.write_table_chunked(
                _chunks_normalizados(chunks_iter), "dim_ord", capa="seed"
            )
        return {"tabla": "dim_ord", "modo": "bootstrap", "filas": total,
                "seg": round(time.perf_counter() - t0, 2)}

    if modo == "incremental":
        log.info("[seeds] dim_ord — INCREMENTAL (sysdate-4) + MERGE por ORD_NUMERO...")
        t0 = time.perf_counter()
        with OracleReadOnly() as ora:
            df_new = ora.read_sql(_SQL_DIM_ORD_INCREMENTAL)
        if df_new.empty:
            return {"tabla": "dim_ord", "modo": "incremental", "filas_nuevas": 0,
                    "seg": round(time.perf_counter() - t0, 2)}
        df_new = _normalizar_fechas(df_new)
        io.merge_table(df_new, "dim_ord", capa="seed", key="ORD_NUMERO")
        return {"tabla": "dim_ord", "modo": "incremental", "filas_nuevas": len(df_new),
                "seg": round(time.perf_counter() - t0, 2)}

    raise ValueError(f"modo desconocido: {modo!r}")


# =============================================================================
# eqp_equipos_ultimos_10 — filtrado por SRV_CODIGO + pivot local
# =============================================================================

def _gather_srv_codigos() -> list[int]:
    """Devuelve los SRV_CODIGOs (suministros) presentes en stagings + fact.

    Es lo que va a manejar el Core, así que solo necesitamos los equipos para
    estos suministros.
    """
    srvs: set[int] = set()

    for tabla in ("pd_conectar_aux", "pd_cooplyf_aux"):
        if not io.table_exists(tabla, capa="stage"):
            continue
        df = io.read_table(tabla, capa="stage")
        if "Suministro" not in df.columns:
            continue
        vals = pd.to_numeric(df["Suministro"], errors="coerce").dropna().astype("int64").unique()
        srvs.update(int(x) for x in vals)

    if io.table_exists("fact_partes_diarios_full", capa="gold"):
        df_fact = io.read_table("fact_partes_diarios_full", capa="gold")
        if "SRV_CODIGO" in df_fact.columns:
            vals = pd.to_numeric(df_fact["SRV_CODIGO"], errors="coerce").dropna().astype("int64").unique()
            srvs.update(int(x) for x in vals)

    return sorted(srvs)


def _fetch_eqp_for_srvs(srv_codigos: list[int]) -> pd.DataFrame:
    """Trae XXSIGEC.EQUIPOS filtrado por SRV_CODIGO ∈ srv_codigos.

    Como Oracle limita IN-list a 1000 elementos, particionamos en chunks
    de `CHUNK_IN_LIST` y hacemos varios SELECTs.
    """
    cols_select = """
        srv_codigo, ste_numero, eqp_orden, grm_numero, eqp_fecha_instal,
        eqp_precinto, eqp_fecha_retiro, eqp_estado, eqp_observaciones,
        TO_CHAR(EQP_FACTOR_INTENSIDAD) AS FACTOR_CORRIENTE_MEDIDOR,
        TO_CHAR(EQP_FACTOR_TENSION)    AS FACTOR_TENSION_MEDIDOR,
        eqp_programa, eqp_ultima_actualizacion
    """
    partes: list[pd.DataFrame] = []
    with OracleReadOnly() as ora:
        for i in range(0, len(srv_codigos), CHUNK_IN_LIST):
            chunk = srv_codigos[i : i + CHUNK_IN_LIST]
            in_list = ",".join(str(int(s)) for s in chunk)  # int-cast = sanitizado
            q = f"SELECT {cols_select} FROM XXSIGEC.EQUIPOS WHERE srv_codigo IN ({in_list})"
            df_part = ora.read_sql(q)
            partes.append(df_part)
            log.info("  fetch eqp chunk %d/%d (filas=%d, acum=%d)",
                     (i // CHUNK_IN_LIST) + 1,
                     -(-len(srv_codigos) // CHUNK_IN_LIST),
                     len(df_part),
                     sum(len(p) for p in partes))
    if not partes:
        return pd.DataFrame()
    return pd.concat(partes, ignore_index=True, sort=False)


def _pivot_top10_por_srv(df_eqp: pd.DataFrame) -> pd.DataFrame:
    """Pivot top-10 equipos por SRV_CODIGO, replicando el cuaderno Fabric v2.

    Genera columnas `<COL>_ULTIMO`, `<COL>_ANTERIOR_1`, ..., `<COL>_ANTERIOR_9`
    para cada COL en _EQP_COLS_PIVOT.

    Equivalente a (PySpark):
        Window.partitionBy("SRV_CODIGO").orderBy(EQP_ORDEN.desc(), GRM_NUMERO.desc())
        + row_number() - 1 → rank ∈ [0..N-1]
        + filter rank < 10
        + groupBy(SRV_CODIGO).agg(first(when(rank==i, COL))) por cada (COL,i)
    """
    if df_eqp.empty:
        return pd.DataFrame(columns=["SRV_CODIGO"])

    df_eqp = df_eqp.copy()
    # Normalizar tipos para que el sort sea estable y consistente.
    df_eqp["SRV_CODIGO"] = pd.to_numeric(df_eqp["SRV_CODIGO"], errors="coerce").astype("Int64")
    df_eqp["EQP_ORDEN"]  = pd.to_numeric(df_eqp["EQP_ORDEN"],  errors="coerce")
    df_eqp["GRM_NUMERO"] = pd.to_numeric(df_eqp["GRM_NUMERO"], errors="coerce")

    # Sort: SRV asc, EQP_ORDEN desc, GRM_NUMERO desc → más reciente primero
    df_sorted = df_eqp.sort_values(
        ["SRV_CODIGO", "EQP_ORDEN", "GRM_NUMERO"],
        ascending=[True, False, False],
        kind="mergesort",
        na_position="last",
    )
    df_sorted["rank"] = df_sorted.groupby("SRV_CODIGO", sort=False).cumcount()
    df_top10 = df_sorted.loc[df_sorted["rank"] < 10].copy()

    # Pivot: columnas (COL, rank) → flatten + rename a sufijo ULTIMO/ANTERIOR_N
    df_pivot = df_top10.pivot(index="SRV_CODIGO", columns="rank", values=_EQP_COLS_PIVOT)
    nuevas_cols: list[str] = []
    for col, rank in df_pivot.columns:
        sufijo = "ULTIMO" if rank == 0 else f"ANTERIOR_{rank}"
        nuevas_cols.append(f"{col}_{sufijo}")
    df_pivot.columns = nuevas_cols
    df_pivot = df_pivot.reset_index()
    return df_pivot


def refresh_eqp_ultimos_10(srv_codigos: Iterable[int] | None = None) -> dict:
    """Refresca seed/eqp_equipos_ultimos_10.parquet.

    Si `srv_codigos` es None, los toma del staging+fact (ver `_gather_srv_codigos`).
    """
    t0 = time.perf_counter()
    if srv_codigos is None:
        srv_codigos = _gather_srv_codigos()
    else:
        srv_codigos = sorted({int(s) for s in srv_codigos})

    log.info("[seeds] refrescando eqp_equipos_ultimos_10 para %d SRV_CODIGOs...", len(srv_codigos))
    if not srv_codigos:
        log.warning("  No hay SRV_CODIGOs en staging+fact. Escribo tabla vacía.")
        io.write_table(pd.DataFrame(columns=["SRV_CODIGO"]), "eqp_equipos_ultimos_10",
                       capa="seed", mode="overwrite")
        return {"tabla": "eqp_equipos_ultimos_10", "filas": 0,
                "seg": round(time.perf_counter() - t0, 2)}

    df_raw = _fetch_eqp_for_srvs(srv_codigos)
    df_raw = _normalizar_fechas(df_raw)
    log.info("  filas crudas de XXSIGEC.EQUIPOS: %d", len(df_raw))

    df_pivot = _pivot_top10_por_srv(df_raw)
    log.info("  filas tras pivot top-10 por SRV: %d (cols=%d)",
             len(df_pivot), len(df_pivot.columns))

    io.write_table(df_pivot, "eqp_equipos_ultimos_10", capa="seed", mode="overwrite")
    return {
        "tabla":            "eqp_equipos_ultimos_10",
        "srv_codigos":      len(srv_codigos),
        "filas_crudas":     len(df_raw),
        "filas_pivot":      len(df_pivot),
        "seg":              round(time.perf_counter() - t0, 2),
    }


# =============================================================================
# Orquestación
# =============================================================================

# Subset de seeds que NO dependen del staging — pueden refrescarse en cualquier
# orden y antes de las etapas 1/2.
SEEDS_INDEPENDIENTES = (
    "usuarios_gral",
    "dim_stk_stock_equipos",
    "sigec_general",
    "dim_ord",
    "pivot_resul_app_movil",
)


def run_independientes(seeds: Iterable[str] | None = None) -> list[dict]:
    """Refresca el subset de seeds que NO requieren staging."""
    config.ensure_layout()
    objetivo = list(seeds) if seeds is not None else list(SEEDS_INDEPENDIENTES)
    metricas: list[dict] = []
    fns = {
        "usuarios_gral":          refresh_usuarios_gral,
        "dim_stk_stock_equipos":  refresh_dim_stk_stock_equipos,
        "sigec_general":          refresh_sigec_general,
        "dim_ord":                refresh_dim_ord,
        "pivot_resul_app_movil":  refresh_pivot_resul_app_movil,
    }
    for nombre in objetivo:
        if nombre not in fns:
            log.error("Seed desconocida: %s", nombre)
            continue
        try:
            metricas.append(fns[nombre]())
        except Exception as e:
            log.exception("Error refrescando %s: %s", nombre, e)
            metricas.append({"tabla": nombre, "error": f"{type(e).__name__}: {e}"})
    return metricas


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    import argparse
    parser = argparse.ArgumentParser(description="Etapa 0 — refresh de seeds Oracle")
    parser.add_argument(
        "--seed",
        nargs="*",
        choices=list(SEEDS_INDEPENDIENTES) + ["eqp_equipos_ultimos_10", "all"],
        default=["all"],
        help="Qué seed(s) refrescar. 'all' = independientes + eqp.",
    )
    parser.add_argument(
        "--modo-dim-ord",
        choices=["bootstrap", "incremental", "auto"],
        default="auto",
        help="Solo aplica a dim_ord.",
    )
    args = parser.parse_args()

    sel = set(args.seed)
    if "all" in sel:
        sel = set(SEEDS_INDEPENDIENTES) | {"eqp_equipos_ultimos_10"}

    todas_metricas: list[dict] = []
    for nombre in SEEDS_INDEPENDIENTES:
        if nombre not in sel:
            continue
        if nombre == "dim_ord":
            modo = None if args.modo_dim_ord == "auto" else args.modo_dim_ord
            todas_metricas.append(refresh_dim_ord(modo=modo))
        else:
            todas_metricas.extend(run_independientes([nombre]))

    if "eqp_equipos_ultimos_10" in sel:
        todas_metricas.append(refresh_eqp_ultimos_10())

    print("\n=== RESUMEN seeds ===")
    for m in todas_metricas:
        print(f"  {m}")
