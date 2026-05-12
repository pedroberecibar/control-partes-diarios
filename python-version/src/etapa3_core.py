"""Etapa 3.3 — Motor Core (Waterfall).

Portado de la Celda 3 de `pyspark-version/procesar_pd_gral_refactor (5).py`.

Estado actual:
  - T#4 Setup: carga de inputs, df_usr_pool, df_ord_ce_propia,
    df_ord_rechazo_tor, df_base, helper rank_one_by_dias.  ✅
  - T#5 Cruce A: parte ↔ orden CE propia (suministro + fecha).  ✅
  - T#6 Cruce B: rechazo TOR (no-CE).  ✅
  - T#7 Cruce C: rescate técnico por medidor.  ✅
  - T#8 Ensamblado + reglas huérfano + correcciones.  ✅
  - T#9 Enriquecimiento USR/FASE/precio + dedup Repetido X Sumi.  ✅
  - T#10 Normalización a COLS_FACT + MERGE a fact + truncate stagings.  ✅
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from datetime import datetime, timezone

from . import config
from . import hashing
from . import io_lakehouse as io

log = logging.getLogger(__name__)


# =============================================================================
# Helper común de cruces — `Window.orderBy(dias_diff asc) + rank == 1` en Spark
# =============================================================================

def rank_one_by_dias(
    df_join: pd.DataFrame,
    key: str = "_row_id",
    fecha_parte_col: str = "Fecha_Norm",
    fecha_ord_col: str = "ord_fecha_ref",
) -> pd.DataFrame:
    """Replica `Window.partitionBy(key).orderBy(dias_diff asc) → rank == 1`.

    Pasos:
      1. Calcula `dias_diff = |Fecha_Norm - ord_fecha_ref|` en días.
      2. Filtra `dias_diff <= DIAS_TOLERANCIA` (15).
      3. Sort estable (`mergesort`) por (key, dias_diff, NUMERO_ORDEN) y se
         queda con la primera fila de cada `key`.

    Tie-breaker `NUMERO_ORDEN`: Spark `row_number()` con empate es
    no-determinista. Acá lo hacemos determinista con la orden más chica
    (ascendente). Documentado en CLAUDE.md (regla #2).
    """
    if df_join.empty:
        return df_join

    out = df_join.copy()
    out["dias_diff"] = (
        (out[fecha_parte_col] - out[fecha_ord_col]).dt.days.abs()
    )
    out = out.loc[out["dias_diff"] <= config.DIAS_TOLERANCIA]
    if out.empty:
        return out

    sort_cols: list[str] = [key, "dias_diff"]
    if "NUMERO_ORDEN" in out.columns:
        sort_cols.append("NUMERO_ORDEN")  # tie-breaker determinista
    out = out.sort_values(sort_cols, kind="mergesort", na_position="last")
    return out.drop_duplicates(subset=[key], keep="first")


# =============================================================================
# Carga de inputs
# =============================================================================

# Columnas de dim_ord que el waterfall necesita. Filtrar en lectura ahorra
# RAM (la fact dim_ord son 5.7M filas × 58 cols).
_COLS_DIM_ORD = [
    "ORD_NUMERO", "SRV_CODIGO", "TOR_CODIGO", "ORD_RESULTADO",
    "ORD_FECHA_FIN", "ORD_FECHA_INICIO",
    "SEC_CODIGO_ORIGEN", "USR_NUMERO_EJEC_ORD",
]


def _to_int64_nullable(s: pd.Series) -> pd.Series:
    """Cast a Int64 (nullable) tolerante a NaN. Equivalente a `.cast("long")` de Spark."""
    s_num = pd.to_numeric(s, errors="coerce")
    return np.trunc(s_num).astype("Int64")


def _to_double(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("float64")


# Rango razonable para fechas de órdenes: dim_ord trae fechas sentinel
# (año 0206, año 2501, año 2919, etc.) que rompen aritmética de tiempos
# cuando Pandas necesita convertir a [ns]. Las clipamos a NaT para que
# no interfieran con `dias_diff = |Fecha - ord_fecha|`.
_FECHA_MIN_ORD = pd.Timestamp("2000-01-01")
_FECHA_MAX_ORD = pd.Timestamp("2100-12-31")


def _clip_fecha_orden(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s, errors="coerce")
    mask = s.notna() & ((s < _FECHA_MIN_ORD) | (s > _FECHA_MAX_ORD))
    if mask.any():
        log.debug("  Clipeando %d fecha(s) sentinel fuera de [%s, %s]",
                  int(mask.sum()), _FECHA_MIN_ORD.date(), _FECHA_MAX_ORD.date())
        s = s.mask(mask)
    # Resolución [us] para compatibilidad con datetime64[ns] sin overflows
    return s.astype("datetime64[us]")


def _cargar_dim_ord() -> pd.DataFrame:
    """Lee dim_ord (seed) proyectando solo las columnas necesarias.

    dim_ord son ~5.7M × 58 cols (~1GB en RAM si se carga full). El waterfall
    solo usa 8 cols, así que `read_table(columns=...)` baja el costo a ~150MB.
    """
    df = io.read_table("dim_ord", capa="seed", columns=_COLS_DIM_ORD)

    if "SRV_CODIGO" in df:
        df["SRV_CODIGO"] = _to_int64_nullable(df["SRV_CODIGO"])
    if "USR_NUMERO_EJEC_ORD" in df:
        df["USR_NUMERO_EJEC_ORD"] = _to_int64_nullable(df["USR_NUMERO_EJEC_ORD"])
    if "ORD_FECHA_FIN" in df:
        df["ORD_FECHA_FIN"] = _clip_fecha_orden(df["ORD_FECHA_FIN"])
    if "ORD_FECHA_INICIO" in df:
        df["ORD_FECHA_INICIO"] = _clip_fecha_orden(df["ORD_FECHA_INICIO"])
    return df


def _cargar_df_tecnica() -> pd.DataFrame:
    """Lee eqp_equipos_ultimos_10 (seed) y deja srv_tecnico/db_colocado/db_retirado."""
    df = io.read_table("eqp_equipos_ultimos_10", capa="seed")
    requeridas = ["SRV_CODIGO", "STE_NUMERO_ULTIMO", "STE_NUMERO_ANTERIOR_1"]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise KeyError(
            f"Seed eqp_equipos_ultimos_10 no tiene columnas requeridas: {faltantes}"
        )
    return pd.DataFrame({
        "srv_tecnico": _to_int64_nullable(df["SRV_CODIGO"]),
        "db_colocado": _to_double(df["STE_NUMERO_ULTIMO"]),
        "db_retirado": _to_double(df["STE_NUMERO_ANTERIOR_1"]),
    })


def _cargar_df_usuarios() -> pd.DataFrame:
    """Lee usuarios_gral y deja USR_NUMERO/USR_NOMBRE/SEC_CODIGO."""
    df = io.read_table("usuarios_gral", capa="seed")
    cols = ["USR_NUMERO", "USR_NOMBRE", "SEC_CODIGO"]
    faltantes = [c for c in cols if c not in df.columns]
    if faltantes:
        raise KeyError(f"Seed usuarios_gral no tiene columnas requeridas: {faltantes}")
    out = df[cols].copy()
    out["USR_NUMERO"] = _to_int64_nullable(out["USR_NUMERO"])
    out["USR_NOMBRE"] = out["USR_NOMBRE"].astype("string")
    out["SEC_CODIGO"] = out["SEC_CODIGO"].astype("string")
    return out


def _cargar_df_fases() -> pd.DataFrame:
    """Lee dim_stk_stock_equipos y deja MEDIDOR_STOCK/FASE_SIGEC distinct."""
    df = io.read_table("dim_stk_stock_equipos", capa="seed")
    if "STE_NUMERO" not in df.columns or "STE_FASES" not in df.columns:
        raise KeyError("Seed dim_stk_stock_equipos sin STE_NUMERO o STE_FASES")
    out = pd.DataFrame({
        "MEDIDOR_STOCK": _to_double(df["STE_NUMERO"]),
        "FASE_SIGEC":    df["STE_FASES"].astype("string"),
    }).drop_duplicates().reset_index(drop=True)
    return out


def _cargar_mapeo_codigos(contratista: str) -> pd.DataFrame:
    """Lee mapeo_codigos_master filtrado por contratista."""
    df = io.read_table("mapeo_codigos_master", capa="master")
    return df.loc[df["CONTRATISTA"] == contratista].copy()


# =============================================================================
# Construcción de DFs derivados (df_ord_ce, df_ord_ce_propia, df_ord_rechazo_tor, df_base)
# =============================================================================

def _construir_df_ord_ce(df_ord: pd.DataFrame) -> pd.DataFrame:
    """Universo completo de órdenes CE con resultado válido. Sin filtro de contratista."""
    cols_dim_ord = set(df_ord.columns)
    mask = (df_ord["TOR_CODIGO"] == "CE") & df_ord["ORD_RESULTADO"].isin(
        ["E", "IN", "D", "EH", "EI"]
    )
    sub = df_ord.loc[mask].copy()

    out = pd.DataFrame({
        "NUMERO_ORDEN":   sub["ORD_NUMERO"],
        "ord_suministro": sub["SRV_CODIGO"],
        "ORD_FECHA_FIN":  sub["ORD_FECHA_FIN"],
        "ord_fecha_ref":  sub["ORD_FECHA_FIN"].dt.normalize(),
        "ORD_RESULTADO":  sub["ORD_RESULTADO"].astype("string"),
    })
    out["SEC_CODIGO_ORIGEN"] = (
        sub["SEC_CODIGO_ORIGEN"].astype("string")
        if "SEC_CODIGO_ORIGEN" in cols_dim_ord
        else pd.Series(pd.NA, index=sub.index, dtype="string")
    )
    out["ID_OPERARIO_RAW"] = (
        sub["USR_NUMERO_EJEC_ORD"]
        if "USR_NUMERO_EJEC_ORD" in cols_dim_ord
        else pd.Series(pd.NA, index=sub.index, dtype="Int64")
    )
    return out.reset_index(drop=True)


def _construir_df_ord_ce_propia(
    df_ord_ce: pd.DataFrame, df_usr_pool: pd.DataFrame
) -> pd.DataFrame:
    """[FIX-A] Solo CE cuyo ejecutante pertenece a ESTA contratista.

    Inner join `df_ord_ce.ID_OPERARIO_RAW == df_usr_pool.USR_NUMERO`.
    """
    out = df_ord_ce.merge(
        df_usr_pool, left_on="ID_OPERARIO_RAW", right_on="USR_NUMERO", how="inner"
    ).drop(columns=["USR_NUMERO"])
    return out.reset_index(drop=True)


def _construir_df_ord_rechazo_tor(df_ord: pd.DataFrame) -> pd.DataFrame:
    """Órdenes no-CE con coalesce(ORD_FECHA_FIN, ORD_FECHA_INICIO) [FIX-G]."""
    cols_dim_ord = set(df_ord.columns)
    sub = df_ord.loc[df_ord["TOR_CODIGO"] != "CE"].copy()

    fecha_ref = sub["ORD_FECHA_FIN"].fillna(sub["ORD_FECHA_INICIO"]).dt.normalize()

    out = pd.DataFrame({
        "NUMERO_ORDEN":         sub["ORD_NUMERO"],
        "ord_suministro":       sub["SRV_CODIGO"],
        "TIPO_ORDEN_DETECTADO": sub["TOR_CODIGO"].astype("string"),
        "ord_fecha_ref":        fecha_ref,
    })
    out["SEC_CODIGO_ORIGEN"] = (
        sub["SEC_CODIGO_ORIGEN"].astype("string")
        if "SEC_CODIGO_ORIGEN" in cols_dim_ord
        else pd.Series(pd.NA, index=sub.index, dtype="string")
    )
    return out.reset_index(drop=True)


def _construir_df_base(df_pd: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame base de partes con _row_id y casts numéricos.

    [H-09] _row_id solo se usa como clave interna del waterfall — para
    identificación persistente usar ID_PARTE_HASH.
    """
    out = df_pd.copy()
    out["_row_id"] = np.arange(len(out), dtype=np.int64)
    out["Suministro_Norm"] = _to_int64_nullable(out["Suministro"])
    out["medidorColocado"] = _to_double(out["medidorColocado"])
    out["medidorRetirado"] = _to_double(out["medidorRetirado"])
    fecha = pd.to_datetime(out["Fecha"], errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(fecha):
        fecha = fecha.dt.normalize()
    # Resolución [us] para evitar overflow al restar contra ord_fecha_ref ([us])
    out["Fecha_Norm"] = fecha.astype("datetime64[us]")
    return out


# =============================================================================
# Cruces del waterfall
# =============================================================================

# Schema canónico de los DFs de resultados parciales. Los 3 cruces (A, B, C)
# producen DataFrames con estas columnas, así pd.concat funciona sin sorpresas.
_COLS_RESULTADO = [
    "_row_id", "NUMERO_ORDEN", "Suministro_Final", "ORD_FECHA_FIN",
    "TRAZA_CALIDAD", "db_colocado", "db_retirado",
    "SEC_CODIGO_ORIGEN", "ID_OPERARIO_RAW", "ORD_TIPO_DETECTADO",
    "ORD_RESULTADO",
]


def _resultado_vacio() -> pd.DataFrame:
    """DataFrame vacío con el schema canónico de resultados parciales."""
    return pd.DataFrame({
        "_row_id":             pd.Series(dtype="int64"),
        "NUMERO_ORDEN":        pd.Series(dtype="Int64"),
        "Suministro_Final":    pd.Series(dtype="Int64"),
        "ORD_FECHA_FIN":       pd.Series(dtype="datetime64[ns]"),
        "TRAZA_CALIDAD":       pd.Series(dtype="string"),
        "db_colocado":         pd.Series(dtype="float64"),
        "db_retirado":         pd.Series(dtype="float64"),
        "SEC_CODIGO_ORIGEN":   pd.Series(dtype="string"),
        "ID_OPERARIO_RAW":     pd.Series(dtype="Int64"),
        "ORD_TIPO_DETECTADO":  pd.Series(dtype="string"),
        "ORD_RESULTADO":       pd.Series(dtype="string"),
    })


def cruce_A(
    df_base: pd.DataFrame,
    df_ord_ce_propia: pd.DataFrame,
    df_tecnica: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cruce A: parte ↔ orden CE de la MISMA contratista por suministro + fecha.

    Replica el bloque Cruce A de procesar_pd_gral_refactor.py L.421-459.
    [FIX-A] usa df_ord_ce_propia (pre-filtrado por ejecutante).

    Devuelve (df_resultados_A, df_pendientes_A):
      - df_resultados_A: partes matcheados, con TRAZA_CALIDAD asignada.
      - df_pendientes_A: partes NO matcheados, pasan al Cruce B.
    """
    if df_base.empty or df_ord_ce_propia.empty:
        log.info("    Cruce A: sin candidatos (df_base o df_ord_ce_propia vacío).")
        return _resultado_vacio(), df_base

    # 1. Join de la parte con su candidato orden CE.
    #    Incluyo medidorColocado/medidorRetirado en el df_base proyectado
    #    para evitar un re-join a df_base después del ranking (optimización
    #    vs PySpark que hace ese re-join explícito).
    df_candidatos = df_base[[
        "_row_id", "Suministro_Norm", "Fecha_Norm",
        "medidorColocado", "medidorRetirado",
    ]].merge(
        df_ord_ce_propia,
        left_on="Suministro_Norm", right_on="ord_suministro",
        how="inner",
    )

    # 2. Quedarse con el candidato de menor |dias_diff| (ties → NUMERO_ORDEN asc).
    df_candidatos = rank_one_by_dias(df_candidatos)
    if df_candidatos.empty:
        log.info("    Cruce A: 0 matches tras filtro <= %d días.", config.DIAS_TOLERANCIA)
        return _resultado_vacio(), df_base

    # 3. Left join con df_tecnica para traer db_colocado/db_retirado.
    df_analisis = df_candidatos.merge(
        df_tecnica,
        left_on="ord_suministro", right_on="srv_tecnico",
        how="left",
    ).drop(columns=["srv_tecnico"], errors="ignore")

    # 4. TRAZA_CALIDAD con np.select. El orden de las condiciones es crítico
    #    (la primera que matchea gana — igual a F.when().when()...otherwise()).
    cond = [
        df_analisis["ORD_RESULTADO"] == "IN",
        df_analisis["medidorColocado"].isna(),
        (df_analisis["medidorColocado"] == df_analisis["db_colocado"])
        & (df_analisis["medidorRetirado"] == df_analisis["db_retirado"]),
        (df_analisis["medidorColocado"] == df_analisis["db_retirado"])
        & (df_analisis["medidorRetirado"] == df_analisis["db_colocado"]),
    ]
    choice = [
        "Informado - No Ejecutado",
        "Corregido Medidor Vacio",
        "Original OK",
        "Corregido Nro EQP Invertidos",
    ]
    df_analisis["TRAZA_CALIDAD"]      = np.select(cond, choice, default="Corregido Nro Medidor")
    df_analisis["TRAZA_CALIDAD"]      = df_analisis["TRAZA_CALIDAD"].astype("string")
    df_analisis["ORD_TIPO_DETECTADO"] = pd.Series(pd.NA, index=df_analisis.index, dtype="string")

    # 5. Normalizar al schema canónico.
    df_resultados_A = df_analisis.rename(
        columns={"ord_suministro": "Suministro_Final"}
    )[_COLS_RESULTADO].copy()

    # Asegurar dtypes estables (importantes para el concat posterior con B y C).
    df_resultados_A = df_resultados_A.astype({
        "_row_id":            "int64",
        "NUMERO_ORDEN":       "Int64",
        "Suministro_Final":   "Int64",
        "TRAZA_CALIDAD":      "string",
        "db_colocado":        "float64",
        "db_retirado":        "float64",
        "SEC_CODIGO_ORIGEN":  "string",
        "ID_OPERARIO_RAW":    "Int64",
        "ORD_TIPO_DETECTADO": "string",
        "ORD_RESULTADO":      "string",
    })

    # 6. Anti-join: partes que no hicieron match quedan para Cruce B.
    matched_ids = set(df_resultados_A["_row_id"])
    df_pendientes_A = df_base.loc[~df_base["_row_id"].isin(matched_ids)].copy()

    log.info(
        "    Cruce A: %d matches / %d pendientes (de %d partes).",
        len(df_resultados_A), len(df_pendientes_A), len(df_base),
    )
    return df_resultados_A, df_pendientes_A


def cruce_B(
    df_pendientes_A: pd.DataFrame,
    df_ord_rechazo_tor: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cruce B: pendientes de A ↔ orden no-CE (cualquier ejecutante).

    Replica el bloque Cruce B de procesar_pd_gral_refactor.py L.461-478.
    [v27.2] Sin filtro de contratista (`df_ord_rechazo_tor` es global) —
    Cruce B solo CLASIFICA como "No Corresponde TOR CE", no asigna usuario.

    Cuando un parte hace match, sabemos que la orden existe pero NO es CE:
    es IC, CX, MP, RX, etc. → fuera del alcance del proceso.
    `TIPO_ORDEN_DETECTADO` viene poblado desde df_ord_rechazo_tor y va a
    `ORD_TIPO_DETECTADO` para que Power BI desglose por tipo de orden
    descartada.

    Devuelve (df_resultados_B, df_pendientes_B). Los pendientes pasan al Cruce C.
    """
    if df_pendientes_A.empty or df_ord_rechazo_tor.empty:
        log.info("    Cruce B: sin candidatos.")
        return _resultado_vacio(), df_pendientes_A

    df_candidatos = df_pendientes_A[[
        "_row_id", "Suministro_Norm", "Fecha_Norm",
    ]].merge(
        df_ord_rechazo_tor,
        left_on="Suministro_Norm", right_on="ord_suministro",
        how="inner",
    )

    df_candidatos = rank_one_by_dias(df_candidatos)
    if df_candidatos.empty:
        log.info("    Cruce B: 0 matches tras filtro <= %d días.", config.DIAS_TOLERANCIA)
        return _resultado_vacio(), df_pendientes_A

    n = len(df_candidatos)
    idx = df_candidatos.index
    df_match = pd.DataFrame({
        "_row_id":             df_candidatos["_row_id"].astype("int64"),
        "NUMERO_ORDEN":        df_candidatos["NUMERO_ORDEN"].astype("Int64"),
        "Suministro_Final":    pd.array([pd.NA] * n, dtype="Int64"),
        "ORD_FECHA_FIN":       pd.Series(pd.NaT, index=idx, dtype="datetime64[us]"),
        "TRAZA_CALIDAD":       pd.array(["No Corresponde TOR CE"] * n, dtype="string"),
        "db_colocado":         np.full(n, np.nan, dtype="float64"),
        "db_retirado":         np.full(n, np.nan, dtype="float64"),
        "SEC_CODIGO_ORIGEN":   df_candidatos["SEC_CODIGO_ORIGEN"].astype("string"),
        "ID_OPERARIO_RAW":     pd.array([pd.NA] * n, dtype="Int64"),
        "ORD_TIPO_DETECTADO":  df_candidatos["TIPO_ORDEN_DETECTADO"].astype("string"),
        "ORD_RESULTADO":       pd.array([pd.NA] * n, dtype="string"),
    })[_COLS_RESULTADO]

    matched_ids = set(df_match["_row_id"])
    df_pendientes_B = df_pendientes_A.loc[~df_pendientes_A["_row_id"].isin(matched_ids)].copy()

    log.info(
        "    Cruce B: %d matches / %d pendientes (de %d entrantes).",
        len(df_match), len(df_pendientes_B), len(df_pendientes_A),
    )
    return df_match, df_pendientes_B


def cruce_C(
    df_pendientes_B: pd.DataFrame,
    df_tecnica: pd.DataFrame,
    df_ord_ce_propia: pd.DataFrame,
    df_base: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cruce C — rescate técnico por número de medidor.

    Replica el bloque "Cruce C: Rescate por número de medidor" de
    procesar_pd_gral_refactor.py L.480-540 (lo que en PySpark se llama
    `df_resultados_B` por nombrado histórico, pero conceptualmente es
    el resultado del Cruce C).

    Idea: el operario escribió mal el suministro pero el número de medidor
    está bien. Usando df_tecnica podemos identificar el suministro REAL
    al que pertenece ese medidor, y luego buscar la orden CE de ese
    suministro real.

    Dos sub-cruces se unen:
      - rescate por `medidorColocado` (cuando está cargado).
      - rescate por `medidorRetirado` (solo si colocado es NaN).

    TRAZA:
      - "Corregido Sumi" si el medidorRetirado del parte == retirado esperado
        en df_tecnica (operario escribió bien los EQP, mal el sumi).
      - "Corregido Sumi Nro EQP" si los retirados no coinciden (operario
        escribió mal el sumi y los EQP).
    """
    if df_pendientes_B.empty or df_tecnica.empty or df_ord_ce_propia.empty:
        log.info("    Cruce C: sin candidatos.")
        return _resultado_vacio(), df_pendientes_B

    # ── Sub-cruce 1: medidorColocado != NaN, match por db_colocado ──────────
    tec_colocado = df_tecnica.rename(columns={
        "db_colocado": "eqp_medidor_colocado",
        "srv_tecnico": "eqp_suministro_real",
        "db_retirado": "eqp_retirado_esperado",
    })
    base_pend_col = df_pendientes_B.loc[
        df_pendientes_B["medidorColocado"].notna(),
        ["_row_id", "medidorColocado"],
    ]
    df_rescate_col = base_pend_col.merge(
        tec_colocado,
        left_on="medidorColocado", right_on="eqp_medidor_colocado",
        how="inner",
    )[[
        "_row_id", "eqp_suministro_real", "eqp_retirado_esperado", "eqp_medidor_colocado",
    ]].rename(columns={"eqp_medidor_colocado": "db_colocado"})

    # ── Sub-cruce 2: medidorColocado NaN AND medidorRetirado != NaN, match por db_retirado ──
    tec_retirado = df_tecnica.rename(columns={
        "db_retirado": "eqp_retirado_match",
        "srv_tecnico": "eqp_suministro_real",
        "db_colocado": "eqp_colocado_inferido",
    })
    base_pend_ret = df_pendientes_B.loc[
        df_pendientes_B["medidorColocado"].isna() & df_pendientes_B["medidorRetirado"].notna(),
        ["_row_id", "medidorRetirado"],
    ]
    df_rescate_ret = base_pend_ret.merge(
        tec_retirado,
        left_on="medidorRetirado", right_on="eqp_retirado_match",
        how="inner",
    )[[
        "_row_id", "eqp_suministro_real", "eqp_retirado_match", "eqp_colocado_inferido",
    ]].rename(columns={
        "eqp_retirado_match":    "eqp_retirado_esperado",
        "eqp_colocado_inferido": "db_colocado",
    })

    df_rescate = pd.concat([df_rescate_col, df_rescate_ret],
                           ignore_index=True, sort=False)
    if df_rescate.empty:
        log.info("    Cruce C: 0 medidores coincidieron con df_tecnica.")
        return _resultado_vacio(), df_pendientes_B

    # ── Buscar la orden CE del suministro REAL (no el escrito en el parte) ──
    df_con_orden = df_rescate.merge(
        df_ord_ce_propia,
        left_on="eqp_suministro_real", right_on="ord_suministro",
        how="inner",
    )
    # Trae Fecha_Norm y medidorRetirado del df_base (necesarios para rank y para TRAZA)
    df_con_orden = df_con_orden.merge(
        df_base[["_row_id", "Fecha_Norm", "medidorRetirado"]],
        on="_row_id", how="inner",
    )

    df_con_orden = rank_one_by_dias(df_con_orden)
    if df_con_orden.empty:
        log.info("    Cruce C: 0 órdenes CE para los suministros rescatados (ventana 15d).")
        return _resultado_vacio(), df_pendientes_B

    # ── TRAZA: si los retirados coinciden → "Corregido Sumi", sino → "Corregido Sumi Nro EQP" ──
    traza = np.where(
        df_con_orden["medidorRetirado"] == df_con_orden["eqp_retirado_esperado"],
        "Corregido Sumi",
        "Corregido Sumi Nro EQP",
    )

    n = len(df_con_orden)
    df_resultados_C = pd.DataFrame({
        "_row_id":             df_con_orden["_row_id"].astype("int64"),
        "NUMERO_ORDEN":        df_con_orden["NUMERO_ORDEN"].astype("Int64"),
        "Suministro_Final":    df_con_orden["eqp_suministro_real"].astype("Int64"),
        "ORD_FECHA_FIN":       df_con_orden["ORD_FECHA_FIN"],
        "TRAZA_CALIDAD":       pd.array(traza, dtype="string"),
        "db_colocado":         df_con_orden["db_colocado"].astype("float64"),
        "db_retirado":         df_con_orden["eqp_retirado_esperado"].astype("float64"),
        "SEC_CODIGO_ORIGEN":   df_con_orden["SEC_CODIGO_ORIGEN"].astype("string"),
        "ID_OPERARIO_RAW":     df_con_orden["ID_OPERARIO_RAW"].astype("Int64"),
        "ORD_TIPO_DETECTADO":  pd.array([pd.NA] * n, dtype="string"),
        "ORD_RESULTADO":       df_con_orden["ORD_RESULTADO"].astype("string"),
    })[_COLS_RESULTADO]

    matched_ids = set(df_resultados_C["_row_id"])
    df_pendientes_C = df_pendientes_B.loc[~df_pendientes_B["_row_id"].isin(matched_ids)].copy()

    log.info(
        "    Cruce C: %d matches / %d pendientes (de %d entrantes).",
        len(df_resultados_C), len(df_pendientes_C), len(df_pendientes_B),
    )
    return df_resultados_C, df_pendientes_C


# =============================================================================
# Ensamblado del waterfall (T#8)
# =============================================================================

def ensamblar_waterfall(
    df_base: pd.DataFrame,
    df_resultados_A: pd.DataFrame,
    df_resultados_B: pd.DataFrame,
    df_resultados_C: pd.DataFrame,
) -> pd.DataFrame:
    """Une los 3 cruces, asigna trazas huérfano y aplica regla "Otro Origen".

    Replica el bloque "Ensamblado final del waterfall" de
    procesar_pd_gral_refactor.py L.554-591.

    Reglas (en orden):
      1. df_base LEFT JOIN concat(A, B, C) por _row_id.
      2. TRAZA_CALIDAD huérfano:
            si Suministro_Norm IS NOT NULL  → "Sin Orden Asociada"
            else si medidorColocado IS NULL → "Error Sumi Sin Nro Medidor"
            else                              → "Error Sumi Y Nro Medidor"
      3. Suministro_Final = coalesce(Suministro_Final, Suministro_Norm).
      4. Regla "Otro Origen": pisa TRAZA si SEC_CODIGO_ORIGEN existe y != "PROTELEM".
      5. Inyección de medidores corregidos: para TRAZAS_CORRECCION_MEDIDOR,
         pisar medidorColocado/Retirado con db_colocado/db_retirado.
    """
    # 1. Concat resultados de los 3 cruces (mismo schema canónico).
    # Filtrar vacíos evita FutureWarning de pandas sobre all-NA columns en concat.
    _partes = [df for df in [df_resultados_A, df_resultados_B, df_resultados_C] if not df.empty]
    df_resultados = (
        pd.concat(_partes, ignore_index=True, sort=False)
        if _partes else _resultado_vacio()
    )

    # 2. Left join con df_base por _row_id.
    df_full = df_base.merge(df_resultados, on="_row_id", how="left", suffixes=("", "_dup"))
    # El concat puede traer dups si alguna col existe en df_base — no es nuestro caso,
    # pero el suffix asegura que si llega a pasar, no rompe silencioso.

    # 3. TRAZA huérfano (coalesce). np.select preserva el orden de evaluación.
    cond_huerfano = [
        df_full["Suministro_Norm"].notna(),
        df_full["medidorColocado"].isna(),
    ]
    choice_huerfano = ["Sin Orden Asociada", "Error Sumi Sin Nro Medidor"]
    traza_huerfano = pd.array(
        np.select(cond_huerfano, choice_huerfano, default="Error Sumi Y Nro Medidor"),
        dtype="string",
    )
    df_full["TRAZA_CALIDAD"] = df_full["TRAZA_CALIDAD"].astype("string").fillna(
        pd.Series(traza_huerfano, index=df_full.index)
    )

    # 4. Suministro_Final = coalesce(Suministro_Final, Suministro_Norm).
    df_full["Suministro_Final"] = df_full["Suministro_Final"].astype("Int64").fillna(
        df_full["Suministro_Norm"].astype("Int64")
    )

    # 5. Regla "Otro Origen" — pisa lo que sea que tenga TRAZA.
    mask_otro_origen = (
        df_full["SEC_CODIGO_ORIGEN"].notna()
        & (df_full["SEC_CODIGO_ORIGEN"].astype("string") != "PROTELEM")
    )
    df_full.loc[mask_otro_origen, "TRAZA_CALIDAD"] = "Otro Origen"

    # 6. Inyección de medidores corregidos. Para las trazas que dicen "el operario
    #    cargó mal el medidor", pisamos con los valores de SIGEC (db_colocado/retirado).
    mask_correccion = df_full["TRAZA_CALIDAD"].isin(config.TRAZAS_CORRECCION_MEDIDOR)
    df_full.loc[mask_correccion, "medidorColocado"] = df_full.loc[mask_correccion, "db_colocado"]
    df_full.loc[mask_correccion, "medidorRetirado"] = df_full.loc[mask_correccion, "db_retirado"]

    # 7. Override TRAZA_CALIDAD con TRAZA_ADAPTER del adapter (Fecha Inválida, Código No Mapeado).
    #    El adapter marca filas que no superaron validación básica antes del waterfall.
    #    Esta asignación tiene máxima prioridad — pisa cualquier traza del waterfall.
    if "TRAZA_ADAPTER" in df_full.columns:
        mask_adapter = df_full["TRAZA_ADAPTER"].notna()
        if mask_adapter.any():
            df_full.loc[mask_adapter, "TRAZA_CALIDAD"] = df_full.loc[mask_adapter, "TRAZA_ADAPTER"]

    return df_full


# =============================================================================
# Enriquecimiento + dedup Repetido X Sumi (T#9)
# =============================================================================

def _expandir_mc_ambas(df_mc: pd.DataFrame) -> pd.DataFrame:
    """Pre-expande filas FASE='AMBAS' a dos (MON y TRI).

    Truco crítico (CLAUDE.md regla #4): permite hacer un merge estándar por
    (codTiposManoObra, FASE) en lugar de la condición Spark
    `(FASE == FASE_DESCUBIERTA) OR (FASE == "AMBAS")`, que en Pandas no se
    mapea a un merge nativo.
    """
    if "FASE" not in df_mc.columns:
        return df_mc
    fase = df_mc["FASE"].astype("string")
    df_otras = df_mc.loc[fase != "AMBAS"].copy()
    df_ambas = df_mc.loc[fase == "AMBAS"].copy()

    if df_ambas.empty:
        return df_otras

    df_mon = df_ambas.copy()
    df_mon["FASE"] = "MON"
    df_tri = df_ambas.copy()
    df_tri["FASE"] = "TRI"
    return pd.concat([df_otras, df_mon, df_tri], ignore_index=True, sort=False)


def enriquecer_y_deduplicar(
    df_full: pd.DataFrame,
    df_usr: pd.DataFrame,
    df_fases: pd.DataFrame,
    df_mc: pd.DataFrame,
) -> pd.DataFrame:
    """Enriquece con USR_NOMBRE / FASE / precio + dedup Repetido X Sumi.

    Replica L.593-646 de procesar_pd_gral_refactor.py.

    Pasos:
      1. Left join con df_usr para traer USR_NOMBRE; rename ID_OPERARIO_RAW → USR_ID.
      2. Left join con df_fases por medidorColocado → FASE_SIGEC. FASE_DESCUBIERTA
         = coalesce(FASE_SIGEC, "TRI" si codTiposManoObra contiene "01" sino "MON").
      3. Pre-expandir df_mc para FASE='AMBAS' y left join por
         (codTiposManoObra, FASE_DESCUBIERTA) para traer COD_EPEC + cant_USE_unitario.
      4. Split por TRAZAS_DESCARTE_TECNICO: los descartados no entran a la dedup.
      5. Dedup por Suministro_Final con prioridad: COD_EPEC != "11" gana, luego
         Fecha más reciente, luego _row_id más alto. Posiciones >1 → "Repetido X Sumi".
    """
    # ── 1. USR_NOMBRE ────────────────────────────────────────────────────────
    df_enriched = df_full.merge(
        df_usr[["USR_NUMERO", "USR_NOMBRE"]],
        left_on="ID_OPERARIO_RAW", right_on="USR_NUMERO",
        how="left",
    ).drop(columns=["USR_NUMERO"], errors="ignore")
    df_enriched = df_enriched.rename(columns={"ID_OPERARIO_RAW": "USR_ID"})

    # ── 2. FASE_DESCUBIERTA ──────────────────────────────────────────────────
    df_con_fase = df_enriched.merge(
        df_fases,
        left_on="medidorColocado", right_on="MEDIDOR_STOCK",
        how="left",
    ).drop(columns=["MEDIDOR_STOCK"], errors="ignore")

    fase_heuristica = np.where(
        df_con_fase["codTiposManoObra"].astype("string").str.contains("01", na=False),
        "TRI", "MON",
    )
    df_con_fase["FASE_DESCUBIERTA"] = df_con_fase["FASE_SIGEC"].astype("string").fillna(
        pd.Series(fase_heuristica, index=df_con_fase.index, dtype="string")
    )

    # ── 3. Join con maestro (con expansión AMBAS) ────────────────────────────
    df_mc_expandido = _expandir_mc_ambas(df_mc)
    df_con_precio = df_con_fase.merge(
        df_mc_expandido,
        left_on=["codTiposManoObra", "FASE_DESCUBIERTA"],
        right_on=["COD_CONTRATISTA_INDIVIDUAL", "FASE"],
        how="left",
    )

    # ── 4. Split para dedup ──────────────────────────────────────────────────
    mask_descarte = df_con_precio["TRAZA_CALIDAD"].isin(config.TRAZAS_DESCARTE_TECNICO)
    df_descartes_directos = df_con_precio.loc[mask_descarte].copy()
    df_para_analizar      = df_con_precio.loc[~mask_descarte].copy()

    # ── 5. Dedup Repetido X Sumi ─────────────────────────────────────────────
    if not df_para_analizar.empty:
        # prioridad_cod=1 si COD_EPEC != "11" (Informado), sino 0.
        # Spark: `when(COD_EPEC != "11", 1).otherwise(0)` — NULL evalúa NULL → 0.
        # Pandas: fillna("11") trata NaN como "11" → prioridad 0 (mismo semántico).
        cod_epec_str = df_para_analizar["COD_EPEC"].astype("string").fillna("11")
        df_para_analizar["prioridad_cod"] = np.where(
            (cod_epec_str != "11").to_numpy(), 1, 0
        )

        # Window equivalente: orden estable con tie-breakers explícitos.
        # Ascendente Suministro_Final para que groupby/cumcount sea correcto;
        # descendente prioridad_cod / Fecha_Norm / _row_id para que la "primera"
        # fila por suministro sea la mejor.
        df_para_analizar = df_para_analizar.sort_values(
            ["Suministro_Final", "prioridad_cod", "Fecha_Norm", "_row_id"],
            ascending=[True, False, False, False],
            kind="mergesort",
            na_position="last",
        )
        df_para_analizar["posicion"] = (
            df_para_analizar.groupby("Suministro_Final", sort=False).cumcount() + 1
        )
        df_para_analizar.loc[df_para_analizar["posicion"] > 1, "TRAZA_CALIDAD"] = "Informados con ORD-SUMI aprobado"
        df_para_analizar = df_para_analizar.drop(columns=["prioridad_cod", "posicion"])

    df_final = pd.concat([df_para_analizar, df_descartes_directos],
                         ignore_index=True, sort=False)
    return df_final


# =============================================================================
# Normalización a COLS_FACT (T#10)
# =============================================================================

def normalizar_a_fact_schema(
    df_final: pd.DataFrame,
    contratista: str,
    mapa_archivos: dict[str, int],
    df_dim_traza: pd.DataFrame,
) -> pd.DataFrame:
    """Aplica los enriquecimientos restantes y selecciona el schema canónico COLS_FACT.

    Replica L.648-730 de procesar_pd_gral_refactor.py.

    Pasos:
      1. ID_ESTADO + ESTADO_PROCESO + es_pagable según TRAZA.
      2. ID_EMPRESA según contratista (1=CONECTAR, 2=COOPLYF).
      3. TIMESTAMP_ETL = ahora (UTC).
      4. ID_ARCHIVO via lookup en mapa_archivos.
      5. ID_TRAZA via merge con dim_traza_calidad_bi.
      6. SUMINISTRO_RAW = Suministro original (string).
      7. ID_PARTE_HASH determinista vía hashing.id_parte_hash.
      8. FUE_CORREGIDO = False (flag para módulo de correcciones futuro).
      9. Select final al schema COLS_FACT.
    """
    df = df_final.copy()
    id_empresa = 1 if contratista == "CONECTAR" else 2

    # 1. ID_ESTADO + ESTADO_PROCESO + es_pagable
    cond_estado = [
        df["TRAZA_CALIDAD"].isin(config.TRAZAS_OK),
        df["TRAZA_CALIDAD"].isin(config.TRAZAS_REVISION),
        df["TRAZA_CALIDAD"].isin(["No Corresponde TOR CE", "Otro Origen"]),
    ]
    choice_estado = [1, 2, 4]
    df["ID_ESTADO"] = np.select(cond_estado, choice_estado, default=3).astype("int64")

    df["ESTADO_PROCESO"] = (
        df["ID_ESTADO"]
        .map({1: "Aprobado", 2: "Revisión", 3: "Rechazado", 4: "Fuera de Alcance"})
        .astype("string")
    )
    df["es_pagable"] = (df["ID_ESTADO"] == 1).astype("int64")

    # 2. ID_EMPRESA
    df["ID_EMPRESA"] = id_empresa

    # 3. TIMESTAMP_ETL — UTC explícito (CLAUDE.md / plan §3.10).
    df["TIMESTAMP_ETL"] = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))

    # 4. ID_ARCHIVO via mapa
    df["ID_ARCHIVO"] = df["ORIGEN_ARCHIVO"].map(mapa_archivos).astype("Int64")

    # 5. ID_TRAZA via merge con dim_traza
    df = df.merge(
        df_dim_traza[["ID_TRAZA", "DESC_TRAZA"]],
        left_on="TRAZA_CALIDAD", right_on="DESC_TRAZA",
        how="left",
    ).drop(columns=["DESC_TRAZA"], errors="ignore")
    df["ID_TRAZA"] = df["ID_TRAZA"].astype("Int64")

    # 6. SUMINISTRO_RAW = Suministro string original (lo que cargó el operario)
    df["SUMINISTRO_RAW"] = df["Suministro"].astype("string")

    # 7. ID_PARTE_HASH determinista — clave del MERGE idempotente.
    df["ID_PARTE_HASH"] = hashing.id_parte_hash(
        origen_archivo=df["ORIGEN_ARCHIVO"],
        srv_codigo=df["Suministro_Final"],
        fecha=df["Fecha_Norm"],
        medidor_colocado=df["medidorColocado"],
        cod_tipos_mano_obra=df["codTiposManoObra"],
    )

    # 8. FUE_CORREGIDO — flag de override de auditoría, default False.
    df["FUE_CORREGIDO"] = False

    # Renombres y casts finales para llegar al schema canónico.
    df_normalizado = pd.DataFrame({
        "ID_EXTERNO":         df["ID_Externo"].astype("string"),
        "FECHA":              df["Fecha_Norm"],  # ya es datetime64[us] normalizado
        "ESTADO_PROCESO":     df["ESTADO_PROCESO"],
        "ID_ARCHIVO":         df["ID_ARCHIVO"],
        "SRV_CODIGO":         df["Suministro_Final"].astype("Int64"),
        "SUMINISTRO_RAW":     df["SUMINISTRO_RAW"],
        "NRO_EQP_COLOCADO":   df["medidorColocado"].astype("float64"),
        "NRO_EQP_RETIRADO":   df["medidorRetirado"].astype("float64"),
        "CODIGO_CONTRATISTA": df["codTiposManoObra"].astype("string"),
        "CODIGO_EPEC":        pd.to_numeric(df["COD_EPEC"], errors="coerce").astype("Int64"),
        "ORD_NRO":            df["NUMERO_ORDEN"].astype("Int64"),
        "ORD_FECHA_FIN":      df["ORD_FECHA_FIN"],
        "es_pagable":         df["es_pagable"],
        "ID_EMPRESA":         df["ID_EMPRESA"].astype("int64"),
        "ID_ESTADO":          df["ID_ESTADO"],
        "TIMESTAMP_ETL":      df["TIMESTAMP_ETL"],
        "SEC_CODIGO_ORIGEN":  df["SEC_CODIGO_ORIGEN"].astype("string"),
        "USR_ID":             df["USR_ID"].astype("Int64"),
        "ID_TRAZA":           df["ID_TRAZA"],
        "ID_PARTE_HASH":      df["ID_PARTE_HASH"].astype("string"),
        "FUE_CORREGIDO":      df["FUE_CORREGIDO"],
        "ORD_TIPO_DETECTADO": df["ORD_TIPO_DETECTADO"].astype("string"),
    })

    # Garantizar el orden exacto de COLS_FACT (defensa en profundidad).
    return df_normalizado[config.COLS_FACT]


# =============================================================================
# Entrypoint del waterfall (estado: T#4–T#10 — completo)
# =============================================================================

def ejecutar_core_para_contratista(
    contratista: str,
    mapa_archivos: dict[str, int],
    df_dim_traza: pd.DataFrame,
    df_pd_input: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame | None, dict | None]:
    """Ejecuta el waterfall completo para una contratista.

    Devuelve (df_normalizado, resumen):
      - df_normalizado: DataFrame con schema COLS_FACT, listo para MERGE.
      - resumen: dict de métricas (counts por TRAZA, USES total, etc.).

    Si la tabla de staging no existe o está vacía → (None, None).
    """
    log.info("=" * 80)
    log.info("INICIANDO PROCESO PARA: %s", contratista)
    log.info("=" * 80)

    if df_pd_input is not None:
        df_pd = df_pd_input.copy()
    else:
        tabla_input = f"pd_{contratista.lower()}_aux"
        if not io.table_exists(tabla_input, capa="stage"):
            log.warning("Tabla %s no existe. Saltando.", tabla_input)
            return None, None

        df_pd = io.read_table(tabla_input, capa="stage")
        
    if df_pd.empty:
        log.warning("DataFrame de entrada vacío para %s. Saltando.", contratista)
        return None, None

    log.info("  Cargando maestros y seeds...")
    df_mc       = _cargar_mapeo_codigos(contratista)
    df_tecnica  = _cargar_df_tecnica()
    df_usr      = _cargar_df_usuarios()
    df_usr_pool = (
        df_usr.loc[df_usr["SEC_CODIGO"] == contratista, ["USR_NUMERO"]]
              .drop_duplicates()
              .reset_index(drop=True)
    )
    df_fases    = _cargar_df_fases()
    df_ord      = _cargar_dim_ord()

    log.info("  Construyendo df_ord_ce / df_ord_ce_propia / df_ord_rechazo_tor...")
    df_ord_ce         = _construir_df_ord_ce(df_ord)
    df_ord_ce_propia  = _construir_df_ord_ce_propia(df_ord_ce, df_usr_pool)
    df_ord_rechazo_tor = _construir_df_ord_rechazo_tor(df_ord)

    log.info("  Construyendo df_base con _row_id...")
    df_base = _construir_df_base(df_pd)

    # ── CRUCES ──────────────────────────────────────────────────────────────
    log.info("  Ejecutando Cruce A (suministro + orden CE propia)...")
    df_resultados_A, df_pendientes_A = cruce_A(df_base, df_ord_ce_propia, df_tecnica)

    log.info("  Ejecutando Cruce B (rechazo TOR no-CE)...")
    df_resultados_B, df_pendientes_B = cruce_B(df_pendientes_A, df_ord_rechazo_tor)

    log.info("  Ejecutando Cruce C (rescate técnico por medidor)...")
    df_resultados_C, df_pendientes_C = cruce_C(
        df_pendientes_B, df_tecnica, df_ord_ce_propia, df_base
    )

    log.info("  Ensamblando waterfall + reglas huérfano + correcciones...")
    df_full = ensamblar_waterfall(df_base, df_resultados_A, df_resultados_B, df_resultados_C)

    log.info("  Enriqueciendo (USR/FASE/precio) + dedup Repetido X Sumi...")
    df_final = enriquecer_y_deduplicar(df_full, df_usr, df_fases, df_mc)

    log.info("  Normalizando a schema COLS_FACT...")
    df_normalizado = normalizar_a_fact_schema(df_final, contratista, mapa_archivos, df_dim_traza)

    def _conteo(df: pd.DataFrame) -> dict:
        return df["TRAZA_CALIDAD"].value_counts().to_dict() if not df.empty else {}

    resumen = {
        "contratista":              contratista,
        "df_pd":                    len(df_pd),
        "df_mc (filtrado)":         len(df_mc),
        "df_tecnica":               len(df_tecnica),
        "df_usr_pool":              len(df_usr_pool),
        "df_fases":                 len(df_fases),
        "df_ord_ce_propia":         len(df_ord_ce_propia),
        "df_ord_rechazo_tor":       len(df_ord_rechazo_tor),
        "df_base":                  len(df_base),
        "cruce_A matches":          len(df_resultados_A),
        "cruce_A pendientes":       len(df_pendientes_A),
        "cruce_A por TRAZA":        _conteo(df_resultados_A),
        "cruce_B matches":          len(df_resultados_B),
        "cruce_B pendientes":       len(df_pendientes_B),
        "cruce_B por TIPO_ORDEN":   df_resultados_B["ORD_TIPO_DETECTADO"].value_counts().to_dict() if not df_resultados_B.empty else {},
        "cruce_C matches":          len(df_resultados_C),
        "cruce_C pendientes":       len(df_pendientes_C),
        "cruce_C por TRAZA":        _conteo(df_resultados_C),
        "huerfanos_finales":        len(df_pendientes_C),
        "df_full (post-ensamblado)": len(df_full),
        "TRAZA_CALIDAD post-ensamblado": _conteo(df_full),
        "df_final (post-dedup)":     len(df_final),
        "TRAZA_CALIDAD final":       _conteo(df_final),
        "USES total":                round(float(df_final["cant_USE_unitario"].fillna(0).sum()), 4),
        "df_normalizado":            len(df_normalizado),
        "ID_ESTADO breakdown":       df_normalizado["ID_ESTADO"].value_counts().to_dict(),
        "Aprobados (ID_ESTADO=1)":   int((df_normalizado["ID_ESTADO"] == 1).sum()),
    }

    log.info("  Resumen:")
    for k, v in resumen.items():
        if k == "contratista":
            continue
        if isinstance(v, dict):
            log.info("    %-22s", k)
            for traza, n in sorted(v.items(), key=lambda kv: -kv[1] if isinstance(kv[1], (int, float)) else 0):
                log.info("      %-35s %s", str(traza), f"{n:>10,}" if isinstance(n, (int, float)) else str(n))
        elif isinstance(v, (int, float)):
            log.info("    %-22s %s", k, f"{v:>10,}")
        else:
            log.info("    %-22s %s", k, v)

    return df_normalizado, resumen


def run(truncate_stagings: bool = False) -> dict:
    """Orquesta Fase 3 completa: dims BI + waterfall por contratista + MERGE.

    `truncate_stagings`: si True, vacía pd_*_aux después del MERGE (matches
    Fabric H-07). Default False para safety durante la migración —
    permite re-correr el Core sin re-ejecutar el adapter.
    """
    config.ensure_layout()

    # ── Generar dimensiones BI (T#1+T#2+T#3) ──────────────────────────────
    log.info("=" * 80)
    log.info("FASE 3 — Generando dimensiones BI...")
    log.info("=" * 80)
    from . import etapa3_dims_bi
    dim_metricas = etapa3_dims_bi.run()
    log.info("Dims BI: %s", dim_metricas)

    # mapa_archivos para normalizar ORIGEN_ARCHIVO → ID_ARCHIVO
    if io.table_exists("dim_archivo_bi", capa="dim"):
        df_dim_arch = io.read_table("dim_archivo_bi", capa="dim")
        mapa_archivos = dict(zip(df_dim_arch["NOMBRE_ARCHIVO"], df_dim_arch["ID_ARCHIVO"].astype(int)))
    else:
        mapa_archivos = {}

    # dim_traza para asignar ID_TRAZA en el normalizador
    df_dim_traza = io.read_table("dim_traza_calidad_bi", capa="dim")

    # ── Waterfall por contratista ─────────────────────────────────────────
    resultados: dict[str, dict | None] = {}
    df_lote_completo: list[pd.DataFrame] = []
    stagings_a_limpiar: list[str] = []

    for contratista in config.LISTA_CONTRATISTAS:
        df_normalizado, resumen = ejecutar_core_para_contratista(
            contratista, mapa_archivos, df_dim_traza,
        )
        resultados[contratista] = resumen
        if df_normalizado is not None:
            df_lote_completo.append(df_normalizado)
            stagings_a_limpiar.append(f"pd_{contratista.lower()}_aux")

    # ── MERGE único a la fact table ───────────────────────────────────────
    if df_lote_completo:
        df_lote = pd.concat(df_lote_completo, ignore_index=True, sort=False)
        log.info("=" * 80)
        log.info("MERGE de %d filas a fact_partes_diarios_full por ID_PARTE_HASH...",
                 len(df_lote))
        log.info("=" * 80)
        io.merge_table(df_lote, "fact_partes_diarios_full", capa="gold",
                       key="ID_PARTE_HASH")
        log.info("MERGE OK.")

        # Truncate stagings DESPUÉS del MERGE [H-07]. Solo si el caller lo pide.
        if truncate_stagings:
            for tabla_stg in stagings_a_limpiar:
                log.info("Truncando staging %s...", tabla_stg)
                io.truncate_table(tabla_stg, capa="stage")
        else:
            log.info("Stagings PRESERVADOS (truncate_stagings=False). Para vaciarlos: "
                     "io.truncate_table(...) manual o run(truncate_stagings=True).")
    else:
        log.warning("No hubo datos en el lote. No se realizaron cambios en la fact table.")

    return resultados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
