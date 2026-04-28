"""Etapa 3.5 — Panel de KPIs del Core (validación contra Power BI).

Portado de la Celda 7 de `pyspark-version/procesar_pd_gral_refactor (5).py`.
Mantiene 1:1 los KPIs y formato de salida del original — el "Panel de Control"
que el usuario contrasta visualmente contra los mosaicos de Power BI.

Diseño en dos capas:

  - `calcular_kpis(df_fact=None)` → dict serializable. Pensado para que un
    endpoint `/api/kpis/dashboard` futuro lo devuelva directo como JSON.
  - `imprimir_panel(kpis)`        → pretty-print en consola (paridad Celda 7).

`run()` calcula + imprime + devuelve el dict. Se invoca al final de
`etapa3_core.run()` y como CLI standalone (`python -m src.etapa3_panel_kpis`).
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
# Carga de inputs (fact + dimensiones + maestro de códigos)
# =============================================================================

def _cargar_base_panel(df_fact: pd.DataFrame | None = None) -> pd.DataFrame:
    """Carga fact + dims + maestro_codigos y deja el DF listo para los KPIs.

    Replica L.948-962 del PySpark: 4 left joins (estado, traza, empresa,
    mapeo_codigos) sobre la fact.
    """
    if df_fact is None:
        df_fact = io.read_table("fact_partes_diarios_full", capa="gold")

    df_estado  = io.read_table("dim_estado_bi",        capa="dim")
    df_traza   = io.read_table("dim_traza_calidad_bi", capa="dim")
    df_empresa = io.read_table("dim_empresa_bi",       capa="dim")

    df_mc = io.read_table("mapeo_codigos_master", capa="master")
    df_mc_panel = (
        df_mc[["COD_EPEC", "DESCRIPCION_CODIGO", "cant_USE_unitario"]]
        .drop_duplicates(subset=["COD_EPEC"])
        .rename(columns={"COD_EPEC": "COD_JOIN"})
    )
    # CODIGO_EPEC en la fact es Int64; el join exige tipo compatible.
    df_mc_panel["COD_JOIN"] = pd.to_numeric(df_mc_panel["COD_JOIN"], errors="coerce").astype("Int64")

    df_base = (
        df_fact
        .merge(df_estado,  on="ID_ESTADO",  how="left")
        .merge(df_traza,   on="ID_TRAZA",   how="left")
        .merge(df_empresa, on="ID_EMPRESA", how="left")
        .merge(df_mc_panel, left_on="CODIGO_EPEC", right_on="COD_JOIN", how="left")
    )
    return df_base


# =============================================================================
# Cálculo (devuelve dict serializable)
# =============================================================================

def _round2(x: float | None) -> float:
    """Redondea a 2 decimales, tolerando None/NaN."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    return float(round(float(x), 2))


def calcular_kpis(df_fact: pd.DataFrame | None = None) -> dict:
    """Devuelve un dict estructurado con todos los KPIs del panel.

    Consumible directo por un endpoint REST futuro. La forma del dict es
    estable y versionable (ver `metadata.schema_version`).
    """
    df_base = _cargar_base_panel(df_fact)

    # ── Pestaña 1: Calidad de datos ──────────────────────────────────────────
    grupo_estado = df_base.groupby("DESC_ESTADO", dropna=False, sort=False).agg(
        cantidad=("DESC_ESTADO", "size"),
        total_uses=("cant_USE_unitario", "sum"),
    )
    cantidad_por_estado = grupo_estado["cantidad"].to_dict()

    total_ingresados = int(cantidad_por_estado.get("Aprobado", 0)
                           + cantidad_por_estado.get("Revisión", 0)
                           + cantidad_por_estado.get("Rechazado", 0)
                           + cantidad_por_estado.get("Fuera de Alcance", 0))
    fuera_alcance    = int(cantidad_por_estado.get("Fuera de Alcance", 0))
    aprobados        = int(cantidad_por_estado.get("Aprobado",         0))
    rechazados       = int(cantidad_por_estado.get("Rechazado",        0))
    ocr              = int(cantidad_por_estado.get("Revisión",         0))

    base_efect      = total_ingresados - fuera_alcance
    efectividad_pct = (aprobados / base_efect * 100) if base_efect > 0 else 0.0

    df_aprobados = df_base.loc[df_base["DESC_ESTADO"] == "Aprobado"].copy()
    desglose_traza = (
        df_aprobados.groupby("DESC_TRAZA", dropna=False, sort=False).size()
        .reset_index(name="cantidad")
        .sort_values("cantidad", ascending=False)
    )
    total_aprobados_cnt = int(desglose_traza["cantidad"].sum())
    corregidos = int(
        desglose_traza.loc[desglose_traza["DESC_TRAZA"] != "Original OK", "cantidad"].sum()
    )
    porc_corregidos = (corregidos / total_aprobados_cnt * 100) if total_aprobados_cnt > 0 else 0.0

    # ── Pestaña 2: Análisis operativo (sobre aprobados) ──────────────────────
    if df_aprobados.empty:
        total_partes_op = 0
        total_uses_op   = 0.0
        dias_trab       = 0
    else:
        total_partes_op = int(len(df_aprobados))
        total_uses_op   = float(df_aprobados["cant_USE_unitario"].fillna(0).sum())
        dias_trab       = int(df_aprobados["FECHA"].nunique())

    promedio_uses = (total_uses_op / total_partes_op) if total_partes_op > 0 else 0.0
    ritmo_diario  = (total_partes_op / dias_trab)     if dias_trab       > 0 else 0.0

    por_contratista = (
        df_aprobados.groupby("EMPRESA", dropna=False, sort=False).agg(
            trabajos=("EMPRESA", "size"),
            total_uses=("cant_USE_unitario", "sum"),
        ).reset_index()
    )

    por_codigo = (
        df_aprobados.groupby(["CODIGO_EPEC", "DESCRIPCION_CODIGO"], dropna=False, sort=False).agg(
            cantidad=("CODIGO_EPEC", "size"),
            total_uses=("cant_USE_unitario", "sum"),
        ).reset_index().sort_values("cantidad", ascending=False)
    )

    if df_aprobados.empty:
        mensual = pd.DataFrame(columns=["mes", "trabajos", "total_uses"])
    else:
        mensual = (
            df_aprobados.assign(mes=pd.to_datetime(df_aprobados["FECHA"]).dt.strftime("%Y/%m"))
            .groupby("mes", sort=True).agg(
                trabajos=("mes", "size"),
                total_uses=("cant_USE_unitario", "sum"),
            ).reset_index()
        )

    # ── Metadata (útil para el frontend: timestamp, rangos, schema) ──────────
    fechas_validas = pd.to_datetime(df_base["FECHA"], errors="coerce").dropna()
    fecha_min = fechas_validas.min()
    fecha_max = fechas_validas.max()

    return {
        "schema_version": "1.0",
        "calidad_datos": {
            "total_ingresados": total_ingresados,
            "fuera_alcance":    fuera_alcance,
            "aprobados":        aprobados,
            "rechazados":       rechazados,
            "ocr":              ocr,
            "base_efectividad": int(base_efect),
            "efectividad_pct":  _round2(efectividad_pct),
            "corregidos":       corregidos,
            "porc_corregidos":  _round2(porc_corregidos),
            "desglose_traza_aprobados": [
                {"DESC_TRAZA": str(r.DESC_TRAZA), "cantidad": int(r.cantidad)}
                for r in desglose_traza.itertuples(index=False)
            ],
        },
        "operativo": {
            "total_partes_aprobados": total_partes_op,
            "total_uses":              _round2(total_uses_op),
            "dias_trabajados":         dias_trab,
            "promedio_uses_x_parte":   _round2(promedio_uses),
            "ritmo_diario_partes":     _round2(ritmo_diario),
            "por_contratista": [
                {
                    "EMPRESA":    str(r.EMPRESA) if pd.notna(r.EMPRESA) else None,
                    "trabajos":   int(r.trabajos),
                    "total_uses": _round2(r.total_uses),
                }
                for r in por_contratista.itertuples(index=False)
            ],
            "por_codigo": [
                {
                    "CODIGO_EPEC":        int(r.CODIGO_EPEC) if pd.notna(r.CODIGO_EPEC) else None,
                    "DESCRIPCION_CODIGO": str(r.DESCRIPCION_CODIGO) if pd.notna(r.DESCRIPCION_CODIGO) else None,
                    "cantidad":           int(r.cantidad),
                    "total_uses":         _round2(r.total_uses),
                }
                for r in por_codigo.itertuples(index=False)
            ],
            "mensual": [
                {
                    "mes":        str(r.mes),
                    "trabajos":   int(r.trabajos),
                    "total_uses": _round2(r.total_uses),
                }
                for r in mensual.itertuples(index=False)
            ],
        },
        "metadata": {
            "rows_fact":     int(len(df_base)),
            "fecha_min":     fecha_min.strftime("%Y-%m-%d") if pd.notna(fecha_min) else None,
            "fecha_max":     fecha_max.strftime("%Y-%m-%d") if pd.notna(fecha_max) else None,
            "calculado_at":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


# =============================================================================
# Pretty-print (formato Celda 7)
# =============================================================================

def _fmt_int(n: int) -> str:
    """Formato 1.234.567 (separador miles con punto, estilo es-AR)."""
    return f"{n:,}".replace(",", ".")


def _fmt_float2(x: float) -> str:
    """Formato 1.234,56 (es-AR: punto miles + coma decimal)."""
    s = f"{x:,.2f}"
    # Truco: intercambiar separadores via marcador único.
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def imprimir_panel(kpis: dict) -> None:
    """Replica el formato de impresión de Celda 7 (paridad visual con Power BI)."""
    cd = kpis["calidad_datos"]
    op = kpis["operativo"]

    print(f"\n{'='*80}")
    print("PANEL DE CONTROL")
    print(f"{'='*80}")

    print("\n" + " " * 25 + "--- 1. CALIDAD DE DATOS ---")
    print(f"  Total Ingresados:  {_fmt_int(cd['total_ingresados'])}")
    print(f"  Fuera de Alcance:  {_fmt_int(cd['fuera_alcance'])}")
    print(f"  Aprobados:         {_fmt_int(cd['aprobados'])}")
    print(f"  Rechazados:        {_fmt_int(cd['rechazados'])}")
    print(f"  Pendientes OCR:    {_fmt_int(cd['ocr'])}")
    print(f"  Efectividad:       {cd['efectividad_pct']:.2f} %")
    print(f"  Porc. Corregidos:  {cd['porc_corregidos']:.2f} %")

    print("\n--- Desglose de Traza de Calidad (Solo Aprobados) ---")
    for row in cd["desglose_traza_aprobados"]:
        print(f"  {row['DESC_TRAZA']:<35} {_fmt_int(row['cantidad']):>10}")

    print("\n" + " " * 25 + "--- 2. ANALISIS OPERATIVO (APROBADOS) ---")
    print(f"  Total Partes Aprobados: {_fmt_int(op['total_partes_aprobados'])}")
    print(f"  USES Aprobadas:         {_fmt_float2(op['total_uses'])}")
    print(f"  Promedio USES x Parte:  {op['promedio_uses_x_parte']:.2f}")
    print(f"  Ritmo Diario (Partes):  {op['ritmo_diario_partes']:.2f}")

    print("\n--- Detalles por Contratista ---")
    for row in op["por_contratista"]:
        empresa = row["EMPRESA"] or "(sin)"
        print(f"  {empresa:<12} trabajos={_fmt_int(row['trabajos']):>8}  "
              f"total_uses={_fmt_float2(row['total_uses']):>12}")

    print("\n--- Cant. por Codigo de Cierre ---")
    for row in op["por_codigo"]:
        cod  = row["CODIGO_EPEC"]
        desc = (row["DESCRIPCION_CODIGO"] or "")[:60]
        print(f"  COD_EPEC={str(cod):<5}  {desc:<62}  "
              f"cantidad={_fmt_int(row['cantidad']):>8}  "
              f"total_uses={_fmt_float2(row['total_uses']):>12}")

    print("\n--- Detalle Mensual ---")
    for row in op["mensual"]:
        print(f"  {row['mes']:<10} trabajos={_fmt_int(row['trabajos']):>8}  "
              f"total_uses={_fmt_float2(row['total_uses']):>12}")

    print(f"\n{'='*80}")
    print("PANEL OK.")
    print(f"{'='*80}")


# =============================================================================
# Entrypoint
# =============================================================================

def run(df_fact: pd.DataFrame | None = None, imprimir: bool = True) -> dict:
    """Calcula los KPIs y opcionalmente los imprime.

    Devuelve el dict para que `etapa3_core.run()` lo incluya en su resumen, y
    para que un endpoint REST futuro pueda servirlo directamente.
    """
    kpis = calcular_kpis(df_fact)
    if imprimir:
        imprimir_panel(kpis)
    return kpis


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
