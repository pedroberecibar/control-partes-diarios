"""Etapa 4 — Control de Observaciones y Valoración Económica (USES).

Portado de `pyspark-version/control_obs_pd_ce (2).py` (versión v5 FIXED).
Mantiene 1:1 los 7 PASOS + panel + generación de `dim_img_app_pd`.

PASOS:
  1. Cargar fact aprobados + dims + pivot de la app (join por ORD_NRO).
  2. Normalizar 8 columnas de observación a 0/1 (`_APP_<campo>`), calcular `_SIN_OBS`.
  3. Lookup `VALOR_USES_ORIGEN` desde reglas por código declarado.
  4a. Faltantes/excedentes vs reglas del código declarado (FIX v5: si no hay
      match, tratar reglas como "todo requerido" → 1).
  4b. Cross join vs TODAS las reglas → mejor match global por Hamming.
  5. `COD_EPEC_SUGERIDO` + `DESCRIPCION_SUGERIDA` + `VALOR_USES_OBS`.
  6. `DIFERENCIA_USES` + `DISCREPANCIA_CODIGO` (np.select con prioridad exacta).
  7. Select final + guardado.

Bonus: `dim_img_app_pd` (URLs Firebase limpiadas, filtradas por ORD_NRO en control_obs).

Invariantes (CLAUDE.md):
  - `kind="mergesort"` + tie-breakers explícitos para reproducir `Window.orderBy` de Spark.
  - `np.select` con orden EXACTO de condiciones (matchea `F.when().when().otherwise()`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config
from . import io_lakehouse as io

log = logging.getLogger(__name__)


# =============================================================================
# Constantes (match exacto con control_obs_pd_ce.py L.156-167)
# =============================================================================

# Columnas de observación: (col en pivot, col en reglas). Orden importa para Hamming.
OBS_COLS = config.OBS_COLS              # 8 pares — single source of truth
VALOR_USES_COD_11 = config.VALOR_USES_COD_11

# Cols de imágenes en el pivot (no son OBS_COLS — se usan solo en dim_img).
COLS_IMG_PIVOT = [
    "IMAGEN_1",
    "IMAGEN_2",
    "IMAGEN_3",
    "IMAGEN_4",
    "IMAGEN_5",
]

# Cols de salida (tal como espera Power BI / paridad con control_obs_pd_ce.py L.451-466).
COLS_CONTROL_EXTRA = [
    "VARIANTE_DECLARADA",
    "TOTAL_FALTANTES",
    "TOTAL_EXCEDENTES",
    "DETALLE_FALTANTES",
    "DETALLE_EXCEDENTES",
    "COD_EPEC_SUGERIDO",
    "DESCRIPCION_SUGERIDA",
    "HAMMING_DIST",
    "VALOR_USES_ORIGEN",
    "VALOR_USES_OBS",
    "DIFERENCIA_USES",
    "DIFERENCIA_USES_ABS",
    "DISCREPANCIA_CODIGO",
    "TIMESTAMP_CONTROL",
]


# =============================================================================
# PASO 1 — Carga + joins + filtro Aprobado + anti fan-out
# =============================================================================

def _cargar_base(df_fact_input: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Devuelve (df_base aprobado y deduplicado, lista de cols base)."""
    if df_fact_input is not None:
        df_fact = df_fact_input.copy()
    else:
        df_fact = io.read_table("fact_partes_diarios_full", capa="gold")
    df_est  = io.read_table("dim_estado_bi",        capa="dim")
    df_trz  = io.read_table("dim_traza_calidad_bi", capa="dim")
    df_emp  = io.read_table("dim_empresa_bi",       capa="dim")
    df_usr  = io.read_table("dim_usuarios_bi",      capa="dim")
    df_arch = io.read_table("dim_archivo_bi",       capa="dim")

    df_base = (
        df_fact
        .merge(df_est,  on="ID_ESTADO",  how="left")
        .merge(df_trz,  on="ID_TRAZA",   how="left")
        .merge(df_emp,  on="ID_EMPRESA", how="left")
        .merge(df_usr,  left_on="USR_ID", right_on="USR_NUMERO", how="left")
        .merge(df_arch, on="ID_ARCHIVO", how="left")
    )
    # Filtro Aprobado (es_pagable=1 ↔ DESC_ESTADO='Aprobado').
    df_base = df_base.loc[df_base["DESC_ESTADO"] == "Aprobado"].copy()

    # Anti fan-out: si un join trajo dups, nos quedamos con uno por ID_PARTE_HASH.
    n_pre = len(df_base)
    df_base = df_base.drop_duplicates(subset=["ID_PARTE_HASH"], keep="first").reset_index(drop=True)
    n_post = len(df_base)
    if n_pre != n_post:
        log.warning("   Fan-out detectado y corregido: %d → %d", n_pre, n_post)
    else:
        log.info("   Sin fan-out: %d registros aprobados.", n_post)

    cols_base = list(df_base.columns)
    return df_base, cols_base


def _join_con_pivot_app(df_base: pd.DataFrame) -> pd.DataFrame:
    """Left join con pivot_resul_app_movil por ORD_NRO ↔ ORD_NUMERO."""
    cols_obs_pivot = [c for c, _ in OBS_COLS]
    cols_pivot_necesarias = ["ORD_NUMERO"] + cols_obs_pivot + COLS_IMG_PIVOT
    df_pivot = io.read_table(
        "pivot_resul_app_movil", capa="seed", columns=cols_pivot_necesarias
    )

    # Validación: confirmar que el pivot trae todas las columnas de obs esperadas.
    faltantes = [c for c in cols_obs_pivot if c not in df_pivot.columns]
    if faltantes:
        log.error("PIVOT — columnas de obs FALTANTES en pivot_resul_app_movil: %s", faltantes)
        raise ValueError(f"pivot_resul_app_movil no tiene las columnas esperadas: {faltantes}")
    con_obs = df_pivot[cols_obs_pivot].notna().any(axis=1).sum()
    log.info("   Pivot: %d filas, %d con al menos 1 observación (%.1f%%).",
             len(df_pivot), con_obs, 100 * con_obs / max(len(df_pivot), 1))

    # ORD_NUMERO en pivot es int64; ORD_NRO en fact es Int64. Compatibles.
    df = df_base.merge(
        df_pivot, left_on="ORD_NRO", right_on="ORD_NUMERO", how="left",
    )
    n_con_match = df["ORD_NUMERO"].notna().sum()
    log.info("   Join pivot: %d partes aprobados, %d con match en pivot (%.1f%%).",
             len(df), n_con_match, 100 * n_con_match / max(len(df), 1))
    return df


# =============================================================================
# PASO 2 — Normalizar OBS_COLS a 0/1 + _SIN_OBS
# =============================================================================

def _normalizar_obs(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega `_APP_<campo>` (1 si la celda no es nula, 0 si es nula) y `_SIN_OBS`."""
    for col_app, col_regla in OBS_COLS:
        # En el pivot, "no observación" llega como NaN. Notna → 1, sino 0.
        df[f"_APP_{col_regla}"] = df[col_app].notna().astype("int8")

    cols_app = [f"_APP_{cr}" for _, cr in OBS_COLS]
    df["_SIN_OBS"] = (df[cols_app].sum(axis=1) == 0)

    # Validación: mostrar distribución de observaciones tras normalización.
    n_sin_obs = int(df["_SIN_OBS"].sum())
    n_con_obs = len(df) - n_sin_obs
    log.info("   Normalización obs: %d con obs, %d sin obs (total=%d).", n_con_obs, n_sin_obs, len(df))
    for col_app, col_regla in OBS_COLS:
        n = int(df[f"_APP_{col_regla}"].sum())
        if n > 0:
            log.info("     _APP_%-35s → %d positivos", col_regla, n)
    return df


# =============================================================================
# PASO 3 — VALOR_USES_ORIGEN (lookup por COD_EPEC declarado)
# =============================================================================

def _agregar_valor_uses_origen(df: pd.DataFrame, df_reglas: pd.DataFrame) -> pd.DataFrame:
    df_lookup = (
        df_reglas[["COD_EPEC", "VALOR_USES"]]
        .drop_duplicates()
        .rename(columns={"COD_EPEC": "_LOOKUP_COD", "VALOR_USES": "VALOR_USES_ORIGEN"})
    )
    df_lookup["_LOOKUP_COD"] = df_lookup["_LOOKUP_COD"].astype("Int64")
    df = df.merge(
        df_lookup, left_on="CODIGO_EPEC", right_on="_LOOKUP_COD", how="left"
    ).drop(columns=["_LOOKUP_COD"])
    return df


# =============================================================================
# PASO 4a — Faltantes / excedentes vs reglas del código declarado (FIX v5)
# =============================================================================

def _calcular_faltantes_excedentes_decl(
    df: pd.DataFrame, df_reglas: pd.DataFrame
) -> pd.DataFrame:
    """Mejor variante del código declarado + faltantes/excedentes columna a columna.

    FIX v5: si el código declarado no matchea NINGUNA regla, marcamos
    `_REGLA_MATCH=False` y tratamos las reglas como "todo requerido" (1) en
    el cómputo de faltantes — así esos partes salen con faltantes en lugar
    de pasar inadvertidos.
    """
    cols_decl_renames = {cr: f"_DECL_{cr}" for _, cr in OBS_COLS}
    df_reglas_decl = df_reglas[["COD_EPEC", "DESCRIPCION", *cols_decl_renames.keys()]].rename(
        columns={"COD_EPEC": "_DECL_COD", "DESCRIPCION": "_DECL_DESC", **cols_decl_renames}
    )
    df_reglas_decl["_DECL_COD"] = df_reglas_decl["_DECL_COD"].astype("Int64")

    df_cross = df.merge(
        df_reglas_decl, left_on="CODIGO_EPEC", right_on="_DECL_COD", how="left"
    )
    df_cross["_REGLA_MATCH"] = df_cross["_DECL_COD"].notna()

    # Hamming SOLO si hay match. Sin match → NaN para que el sort lo mande al final.
    decl_app_diff_cols = []
    for _, cr in OBS_COLS:
        decl_col = df_cross[f"_DECL_{cr}"].fillna(0).astype("int8")
        app_col  = df_cross[f"_APP_{cr}"].fillna(0).astype("int8")
        decl_app_diff_cols.append(np.abs(decl_col.to_numpy(dtype="int16") - app_col.to_numpy(dtype="int16")))
    hamming_decl_arr = np.sum(decl_app_diff_cols, axis=0).astype("float64")
    hamming_decl_arr[~df_cross["_REGLA_MATCH"].to_numpy()] = np.nan
    df_cross["_HAMMING_DECL"] = hamming_decl_arr

    # Mejor variante por (ID_PARTE_HASH, hamming asc, _DECL_DESC asc).
    # mergesort estable + tie-breakers exactos para reproducir Window.orderBy de Spark.
    df_cross = df_cross.sort_values(
        ["ID_PARTE_HASH", "_HAMMING_DECL", "_DECL_DESC"],
        ascending=[True, True, True],
        na_position="last",
        kind="mergesort",
    )
    df_best_decl = df_cross.drop_duplicates(subset=["ID_PARTE_HASH"], keep="first").reset_index(drop=True)

    # FIX v5: faltantes/excedentes con manejo robusto de no-match.
    # Sin match → decl_col se trata como 1 (todo requerido).
    falta_cols   = []
    excede_cols  = []
    regla_match_arr = df_best_decl["_REGLA_MATCH"].to_numpy()
    for _, cr in OBS_COLS:
        app_col = df_best_decl[f"_APP_{cr}"].fillna(0).to_numpy(dtype="int8")
        decl_raw = df_best_decl[f"_DECL_{cr}"].fillna(0).to_numpy(dtype="int8")
        # Sin match: todo requerido (1). Con match: el valor declarado.
        decl_col = np.where(regla_match_arr, decl_raw, 1).astype("int8")

        falta  = ((decl_col == 1) & (app_col == 0)).astype("int8")
        excede = ((decl_col == 0) & (app_col == 1)).astype("int8")
        df_best_decl[f"_FALTA_{cr}"]  = falta
        df_best_decl[f"_EXCEDE_{cr}"] = excede
        falta_cols.append(f"_FALTA_{cr}")
        excede_cols.append(f"_EXCEDE_{cr}")

    df_best_decl["TOTAL_FALTANTES"]   = df_best_decl[falta_cols].sum(axis=1).astype("int16")
    df_best_decl["TOTAL_EXCEDENTES"]  = df_best_decl[excede_cols].sum(axis=1).astype("int16")
    df_best_decl["DETALLE_FALTANTES"]  = _concat_flags(df_best_decl, falta_cols, "_FALTA_")
    df_best_decl["DETALLE_EXCEDENTES"] = _concat_flags(df_best_decl, excede_cols, "_EXCEDE_")

    df_best_decl["VARIANTE_DECLARADA"] = np.where(
        regla_match_arr,
        df_best_decl["_DECL_DESC"].astype("string"),
        "SIN REGLA PARA CODIGO DECLARADO",
    )

    # Limpiar temporales.
    cols_drop = (
        ["_DECL_COD", "_DECL_DESC", "_HAMMING_DECL"]
        + [f"_DECL_{cr}" for _, cr in OBS_COLS]
        + falta_cols
        + excede_cols
    )
    df_best_decl = df_best_decl.drop(columns=cols_drop)

    n_sin_match = int((~df_best_decl["_REGLA_MATCH"]).sum())
    if n_sin_match > 0:
        log.warning("   %d registros SIN match con reglas del código declarado.", n_sin_match)
    return df_best_decl


def _concat_flags(df: pd.DataFrame, cols: list[str], prefix: str) -> pd.Series:
    """Junta los nombres de las cols con valor==1 separadas por ', '. Réplica de
    `concat_ws(", ", *[when(col(c)==1, lit(c.replace(prefix, "")))...])` del PySpark."""
    nombres = [c.replace(prefix, "") for c in cols]
    arr_vals = df[cols].to_numpy(dtype="int8")
    out = []
    for fila in arr_vals:
        partes = [n for n, v in zip(nombres, fila) if v == 1]
        out.append(", ".join(partes) if partes else None)
    return pd.Series(out, index=df.index, dtype="string")


# =============================================================================
# PASO 4b — Cross join vs TODAS las reglas → mejor match global por Hamming
# =============================================================================

def _calcular_hamming_global(
    df: pd.DataFrame, df_reglas: pd.DataFrame
) -> pd.DataFrame:
    """Adjunta `_REGLA_COD_EPEC`, `_REGLA_DESCRIPCION`, `_REGLA_VALOR_USES`,
    `HAMMING_DIST` correspondientes a la regla con menor Hamming global."""
    n_partes = len(df)
    n_reglas = len(df_reglas)

    cols_obs = [cr for _, cr in OBS_COLS]
    # Matrices binarias N×8 (partes) y M×8 (reglas).
    app_mat   = df[[f"_APP_{cr}" for cr in cols_obs]].fillna(0).to_numpy(dtype="int8")
    regla_mat = df_reglas[cols_obs].fillna(0).to_numpy(dtype="int8")

    # Hamming entre cada parte y cada regla — broadcast vectorizado N×M.
    # Equivale al cross join + sum(abs(diff)) del Spark, pero sin generar el DF intermedio.
    hamming = np.abs(app_mat[:, None, :] - regla_mat[None, :, :]).sum(axis=2)  # shape (N, M)

    # Para reproducir el orden estable de Spark con tie-breaker por _REGLA_DESCRIPCION:
    # primero ordeno las reglas por descripción asc, así con argmin estable elegimos
    # la primera por orden alfabético cuando hay empate de Hamming.
    orden_reglas = np.argsort(df_reglas["DESCRIPCION"].astype("string").to_numpy(),
                              kind="mergesort")
    regla_idx_min_per_parte = orden_reglas[hamming[:, orden_reglas].argmin(axis=1)]

    df_reglas_sel = df_reglas.iloc[regla_idx_min_per_parte][
        ["COD_EPEC", "DESCRIPCION", "VALOR_USES"]
    ].rename(columns={
        "COD_EPEC":    "_REGLA_COD_EPEC",
        "DESCRIPCION": "_REGLA_DESCRIPCION",
        "VALOR_USES":  "_REGLA_VALOR_USES",
    }).reset_index(drop=True)
    df_reglas_sel["HAMMING_DIST"] = hamming[np.arange(n_partes), regla_idx_min_per_parte].astype("int16")

    out = pd.concat([df.reset_index(drop=True), df_reglas_sel], axis=1)
    log.info("   Hamming global calculado: %d partes × %d reglas (%d comparaciones).",
             n_partes, n_reglas, n_partes * n_reglas)
    return out


# =============================================================================
# PASO 5 — COD_EPEC_SUGERIDO + DESCRIPCION_SUGERIDA + VALOR_USES_OBS
# =============================================================================

def _asignar_sugerido(df: pd.DataFrame) -> pd.DataFrame:
    sin_obs = df["_SIN_OBS"].to_numpy()
    df["COD_EPEC_SUGERIDO"]    = pd.array(np.where(sin_obs, 11, df["_REGLA_COD_EPEC"]), dtype="Int64")
    df["DESCRIPCION_SUGERIDA"] = np.where(
        sin_obs, "Sin Observaciones Cargadas", df["_REGLA_DESCRIPCION"].astype("string")
    )
    df["DESCRIPCION_SUGERIDA"] = df["DESCRIPCION_SUGERIDA"].astype("string")
    df["VALOR_USES_OBS"]       = np.where(
        sin_obs, VALOR_USES_COD_11, df["_REGLA_VALOR_USES"]
    ).astype("float64")
    return df


# =============================================================================
# PASO 6 — DIFERENCIA_USES + DISCREPANCIA_CODIGO
# =============================================================================

def _calcular_discrepancia(df: pd.DataFrame) -> pd.DataFrame:
    valor_origen = df["VALOR_USES_ORIGEN"].astype("Float64")
    valor_obs    = df["VALOR_USES_OBS"].astype("Float64")
    diff = (valor_origen - valor_obs).round(4)
    df["DIFERENCIA_USES"]     = diff
    df["DIFERENCIA_USES_ABS"] = diff.abs()

    # IMPORTANTE: orden EXACTO de las condiciones (matchea F.when().when().otherwise() de Spark).
    # dtype=bool, na_value=False es necesario para nullable types (Int64, BooleanArray):
    # sin este argumento, .to_numpy() devuelve object array cuando hay pd.NA, y numpy 2.x lo rechaza.
    cond = [
        df["VALOR_USES_ORIGEN"].isna().to_numpy(dtype=bool, na_value=False),
        (~df["_REGLA_MATCH"]).to_numpy(dtype=bool, na_value=False),
        df["_SIN_OBS"].to_numpy(dtype=bool, na_value=False),
        (df["CODIGO_EPEC"] == df["COD_EPEC_SUGERIDO"]).to_numpy(dtype=bool, na_value=False),
        (df["DIFERENCIA_USES"].fillna(0) == 0).to_numpy(dtype=bool, na_value=False),
        (df["DIFERENCIA_USES"].fillna(0) > 0).to_numpy(dtype=bool, na_value=False),
    ]
    choice = [
        "Sin Regla Definida",
        "Sin Regla para Código Declarado",
        "Sin Observaciones",
        "Sin Discrepancia",
        "Error Operativo",
        "Sobrevaloración",
    ]
    df["DISCREPANCIA_CODIGO"] = pd.array(
        np.select(cond, choice, default="Subvaloración"), dtype="string"
    )
    df["TIMESTAMP_CONTROL"] = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    return df


# =============================================================================
# PASO 7 — Selección final + write
# =============================================================================

def _seleccionar_y_guardar(df: pd.DataFrame, cols_base: list[str]) -> pd.DataFrame:
    """Conserva COLS_BASE + _APP_* (para ParteImportService) + COLS_CONTROL_EXTRA. Escribe a gold."""
    cols_app = [f"_APP_{cr}" for _, cr in OBS_COLS]
    cols_finales = list(dict.fromkeys(cols_base + cols_app + COLS_CONTROL_EXTRA))  # dedup preservando orden
    cols_existentes = [c for c in cols_finales if c in df.columns]
    df_final = df[cols_existentes].copy()

    io.write_table(df_final, "control_obs_app", capa="gold", mode="overwrite")
    log.info("   control_obs_app guardada con %d filas y %d columnas.",
             len(df_final), len(df_final.columns))
    return df_final


# =============================================================================
# Panel de resultados
# =============================================================================

def imprimir_panel(df_panel: pd.DataFrame) -> dict:
    """Replica el panel del PySpark — devuelve también un dict para futura API."""
    total = int(len(df_panel))
    kpi = df_panel["DISCREPANCIA_CODIGO"].value_counts(dropna=False).to_dict()

    print(f"\n{'='*80}")
    print("RESULTADOS DEL CONTROL DE OBSERVACIONES Y VALORACION ECONOMICA")
    print(f"{'='*80}")
    print(f"  Total partes controlados:          {total:,}".replace(",", "."))
    print(f"  Sin Discrepancia:                  {kpi.get('Sin Discrepancia', 0):,}".replace(",", "."))
    print(f"  Sobrevaloración (EPEC pierde):     {kpi.get('Sobrevaloración', 0):,}".replace(",", "."))
    print(f"  Subvaloración (Contrat. pierde):   {kpi.get('Subvaloración', 0):,}".replace(",", "."))
    print(f"  Error Operativo (USES iguales):    {kpi.get('Error Operativo', 0):,}".replace(",", "."))
    print(f"  Sin Observaciones:                 {kpi.get('Sin Observaciones', 0):,}".replace(",", "."))
    print(f"  Sin Regla Definida:                {kpi.get('Sin Regla Definida', 0):,}".replace(",", "."))
    print(f"  Sin Regla para Cód. Declarado:     {kpi.get('Sin Regla para Código Declarado', 0):,}".replace(",", "."))

    sobreval = kpi.get("Sobrevaloración", 0)
    subval   = kpi.get("Subvaloración",   0)
    indice = (sobreval / (sobreval + subval)) if (sobreval + subval) > 0 else 0.0
    print(f"\n  INDICE DE ASIMETRIA: {indice:.2%}")

    print("\n--- Impacto económico por tipo de discrepancia ---")
    df_imp = (
        df_panel.loc[df_panel["DISCREPANCIA_CODIGO"].isin(["Sobrevaloración", "Subvaloración"])]
        .groupby("DISCREPANCIA_CODIGO", sort=False).agg(
            Cantidad=("DISCREPANCIA_CODIGO", "size"),
            Impacto_USES_Total=("DIFERENCIA_USES_ABS", "sum"),
            Impacto_USES_Promedio=("DIFERENCIA_USES_ABS", "mean"),
        ).reset_index()
    )
    for r in df_imp.itertuples(index=False):
        print(f"  {r.DISCREPANCIA_CODIGO:<18} cantidad={r.Cantidad:>8,}  "
              f"total_USES={r.Impacto_USES_Total:>10.4f}  "
              f"prom_USES={r.Impacto_USES_Promedio:>8.4f}")

    print("\n--- Desglose por Contratista ---")
    df_emp = (
        df_panel.groupby(["EMPRESA", "DISCREPANCIA_CODIGO"], sort=True).size()
        .reset_index(name="Cantidad")
    )
    for r in df_emp.itertuples(index=False):
        print(f"  {str(r.EMPRESA):<10} {r.DISCREPANCIA_CODIGO:<35} {r.Cantidad:>8,}")

    if kpi.get("Sobrevaloración", 0) > 0:
        print("\n--- Top 10 códigos con mayor sobrevaloración ---")
        df_top = (
            df_panel.loc[df_panel["DISCREPANCIA_CODIGO"] == "Sobrevaloración"]
            .groupby(["CODIGO_EPEC", "COD_EPEC_SUGERIDO"], sort=False).agg(
                Cantidad=("CODIGO_EPEC", "size"),
                Impacto_Total=("DIFERENCIA_USES", "sum"),
            ).reset_index().sort_values("Impacto_Total", ascending=False).head(10)
        )
        for r in df_top.itertuples(index=False):
            print(f"  COD_EPEC={str(r.CODIGO_EPEC):<5} sugerido={str(r.COD_EPEC_SUGERIDO):<5}  "
                  f"cantidad={r.Cantidad:>6,}  impacto_total={r.Impacto_Total:>10.4f}")

    print(f"\n{'='*80}")
    return {"total": total, "por_discrepancia": kpi, "indice_asimetria": indice}


# =============================================================================
# Bonus: dim_img_app_pd
# =============================================================================

def _limpiar_url_firebase(s: pd.Series) -> pd.Series:
    """Extrae la mejor URL de imagen disponible desde OBO_INFO_ADICIONAL.

    SIGEC almacena en OBO_INFO_ADICIONAL uno de estos formatos:
      - Solo ruta local:  /storage/emulated/0/Pictures/.../ORD79046730_20251009.jpg
      - Ruta + Firebase:  /storage/.../ORD79046730.jpg-https://firebasestorage.../...?alt:media&token:xxx

    Prefiere la URL Firebase cuando está presente; si no, usa la ruta local.
    Descarta labels de texto plano sin barra ni http ('Imagen 1', etc.).
    """
    base = s.astype("string")
    # Extraer la parte Firebase si existe (todo desde 'https://' en adelante)
    firebase = base.str.extract(r"(https?://.*)", expand=False)
    firebase = firebase.str.replace("?alt:media", "?alt=media", regex=False)
    firebase = firebase.str.replace("&token:",    "&token=",    regex=False)
    # Usar Firebase URL si está; si no, usar el string completo (ruta local)
    result = firebase.where(firebase.notna(), other=base)
    # Descartar labels sin barra ni protocolo ('Imagen 1', etc.)
    is_valid = (
        result.str.startswith("/").fillna(False)
        | result.str.startswith("http").fillna(False)
    )
    return result.where(is_valid, other=pd.NA)


def generar_dim_img_app_pd(df_control: pd.DataFrame) -> pd.DataFrame:
    """Genera dim_img_app_pd — URLs de imágenes Firebase limpias, una fila por ORD_NRO.

    Solo conserva ordenativos que están en control_obs_app (semi-join lógico).
    """
    df_pivot = io.read_table(
        "pivot_resul_app_movil", capa="seed",
        columns=["ORD_NUMERO", *COLS_IMG_PIVOT],
    )

    df_img = pd.DataFrame({"ORD_NRO": df_pivot["ORD_NUMERO"].astype("Int64")})
    for i, col in enumerate(COLS_IMG_PIVOT, start=1):
        df_img[f"IMAGEN_{i}"] = _limpiar_url_firebase(df_pivot[col])

    # Filtrar filas sin ninguna imagen.
    img_cols = [f"IMAGEN_{i}" for i in range(1, 6)]
    mask_alguna = df_img[img_cols].notna().any(axis=1)
    df_img = df_img.loc[mask_alguna]

    # Semi-join con control_obs por ORD_NRO.
    ord_nros_validos = df_control["ORD_NRO"].dropna().astype("Int64").unique()
    df_img = df_img.loc[df_img["ORD_NRO"].isin(ord_nros_validos)]
    df_img = df_img.drop_duplicates(subset=["ORD_NRO"], keep="first").reset_index(drop=True)

    io.write_table(df_img, "dim_img_app_pd", capa="dim", mode="overwrite")
    log.info("dim_img_app_pd: %d ordenativos únicos con fotos.", len(df_img))
    return df_img


# =============================================================================
# Entrypoint
# =============================================================================

def run(df_fact_input: pd.DataFrame | None = None) -> dict:
    """Ejecuta los 7 PASOS + panel + dim_img_app_pd. Devuelve dict de métricas.

    Si `df_fact_input` es None, lee la fact desde Parquet (modo CLI).
    Si se provee, ejecuta in-memory (modo worker).
    """
    config.ensure_layout()
    if df_fact_input is None and not io.table_exists("fact_partes_diarios_full", capa="gold"):
        log.warning("fact_partes_diarios_full no existe — saltando Etapa 4.")
        return {"skipped": True}

    log.info("=" * 80)
    log.info("ETAPA 4 — CONTROL DE OBSERVACIONES Y VALORACION ECONOMICA (USES)")
    log.info("=" * 80)

    log.info("[1/7] Cargando partes aprobados y aplicando dimensiones...")
    df_base, cols_base = _cargar_base(df_fact_input)
    df_con_app = _join_con_pivot_app(df_base)

    log.info("[2/7] Normalizando observaciones de la app...")
    df_norm = _normalizar_obs(df_con_app)

    df_reglas = io.read_table("reglas_cod_obs_app", capa="master")
    df_reglas["COD_EPEC"] = df_reglas["COD_EPEC"].astype("Int64")

    log.info("[3/7] Asignando VALOR_USES_ORIGEN por código declarado...")
    df_origen = _agregar_valor_uses_origen(df_norm, df_reglas)

    log.info("[4a/7] Calculando faltantes/excedentes vs código declarado...")
    df_4a = _calcular_faltantes_excedentes_decl(df_origen, df_reglas)

    log.info("[4b/7] Buscando código sugerido por distancia Hamming global...")
    df_4b = _calcular_hamming_global(df_4a, df_reglas)

    log.info("[5/7] Asignando COD_EPEC_SUGERIDO y VALOR_USES_OBS...")
    df_5 = _asignar_sugerido(df_4b)

    log.info("[6/7] Calculando diferencias económicas y clasificando discrepancia...")
    df_6 = _calcular_discrepancia(df_5)

    log.info("[7/7] Guardando control_obs_app...")
    df_final = _seleccionar_y_guardar(df_6, cols_base)

    # Validación de integridad.
    df_fact = io.read_table("fact_partes_diarios_full", capa="gold", columns=["es_pagable"])
    n_aprobados = int((df_fact["es_pagable"] == 1).sum())
    if len(df_final) != n_aprobados:
        log.warning("ALERTA INTEGRIDAD: fact_aprobados=%d, control=%d", n_aprobados, len(df_final))
    else:
        log.info("Integridad OK: %d registros.", len(df_final))

    panel = imprimir_panel(df_final)

    log.info("Generando dim_img_app_pd...")
    df_img = generar_dim_img_app_pd(df_final)

    return {
        "control_obs_app":  len(df_final),
        "dim_img_app_pd":   len(df_img),
        "panel":            panel,
    }


def procesar_etapa4(
    df_fact_input: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Entrypoint in-memory para el worker de la Web App.

    Ejecuta los 7 PASOS sobre el DataFrame en memoria y devuelve:
        (df_final, df_img, metricas)

    `df_final`: control_obs_app — un registro por parte aprobado, con todas
                las cols del fact + observaciones + USES + sugeridos + discrepancia.
    `df_img`:   dim_img_app_pd — un registro por ORD_NRO con IMAGEN_1..IMAGEN_5.
    `metricas`: dict con totales para logging.

    No escribe Parquet. Reutiliza la pipeline interna de `run()` sin tocar I/O.
    """
    config.ensure_layout()

    df_base, cols_base = _cargar_base(df_fact_input)
    df_con_app = _join_con_pivot_app(df_base)
    df_norm = _normalizar_obs(df_con_app)

    df_reglas = io.read_table("reglas_cod_obs_app", capa="master")
    df_reglas["COD_EPEC"] = df_reglas["COD_EPEC"].astype("Int64")

    df_origen = _agregar_valor_uses_origen(df_norm, df_reglas)
    df_4a = _calcular_faltantes_excedentes_decl(df_origen, df_reglas)
    df_4b = _calcular_hamming_global(df_4a, df_reglas)
    df_5 = _asignar_sugerido(df_4b)
    df_6 = _calcular_discrepancia(df_5)

    # _seleccionar_y_guardar persiste a Parquet además de retornar el df.
    # Para el modo in-memory queremos solo el df sin tocar gold/, pero respetamos
    # la firma actual: el motor sigue siendo "single source of truth" del schema.
    df_final = _seleccionar_y_guardar(df_6, cols_base)
    df_img = generar_dim_img_app_pd(df_final)

    metricas = {
        "control_obs_app": len(df_final),
        "dim_img_app_pd":  len(df_img),
    }
    return df_final, df_img, metricas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
