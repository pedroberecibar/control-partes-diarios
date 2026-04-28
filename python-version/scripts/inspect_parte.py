"""Helper de debugging: traza completa de un parte individual.

Permite inspeccionar el pipeline step-by-step para un ID_PARTE_HASH,
un Suministro+Fecha, o un ORD_NRO específico. Útil cuando un KPI
difiere respecto a Power BI y hay que entender por qué.

Uso:
    python scripts/inspect_parte.py --hash <ID_PARTE_HASH>
    python scripts/inspect_parte.py --suministro 123456 --fecha 2025-07-15
    python scripts/inspect_parte.py --ord-nro 4567890
    python scripts/inspect_parte.py --suministro 123456   # todos los partes de ese sumi
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Permite correr el script desde cualquier cwd sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from src import config  # noqa: E402
from src import io_lakehouse as io  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("inspect_parte")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 60)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sep(titulo: str) -> None:
    print(f"\n{'='*80}")
    print(f"  {titulo}")
    print(f"{'='*80}")


def _print_df(df: pd.DataFrame, max_rows: int = 20) -> None:
    if df.empty:
        print("  (sin resultados)")
    else:
        print(df.head(max_rows).to_string(index=False))
        if len(df) > max_rows:
            print(f"  ... y {len(df) - max_rows} filas mas.")


def _cargar_fact() -> pd.DataFrame:
    df = io.read_table("fact_partes_diarios_full", capa="gold")
    # Enriquecer con dims para que la info sea legible
    for dim, on_col in [
        ("dim_estado_bi", "ID_ESTADO"),
        ("dim_traza_calidad_bi", "ID_TRAZA"),
        ("dim_empresa_bi", "ID_EMPRESA"),
    ]:
        try:
            df_dim = io.read_table(dim, capa="dim")
            df = df.merge(df_dim, on=on_col, how="left")
        except FileNotFoundError:
            pass
    return df


def _cargar_control_obs() -> pd.DataFrame | None:
    try:
        return io.read_table("control_obs_app", capa="gold")
    except FileNotFoundError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Inspección
# ─────────────────────────────────────────────────────────────────────────────

def inspect_by_hash(hash_val: str) -> None:
    """Traza completa para un ID_PARTE_HASH."""
    config.ensure_layout()
    df_fact = _cargar_fact()

    filas = df_fact.loc[df_fact["ID_PARTE_HASH"] == hash_val]
    _sep(f"FACT: ID_PARTE_HASH = {hash_val}")
    if filas.empty:
        print(f"  No encontrado en fact_partes_diarios_full.")
        return
    _print_df(filas.T.rename(columns={filas.index[0]: "valor"}))

    # Buscar en control_obs si existe
    df_obs = _cargar_control_obs()
    if df_obs is not None:
        obs_filas = df_obs.loc[df_obs["ID_PARTE_HASH"] == hash_val]
        _sep("CONTROL OBS")
        if obs_filas.empty:
            print("  No presente en control_obs_app (probablemente no aprobado).")
        else:
            # Mostrar solo columnas de control de observaciones
            cols_ctrl = [c for c in obs_filas.columns if c in [
                "ID_PARTE_HASH", "VARIANTE_DECLARADA", "TOTAL_FALTANTES",
                "TOTAL_EXCEDENTES", "DETALLE_FALTANTES", "DETALLE_EXCEDENTES",
                "COD_EPEC_SUGERIDO", "DESCRIPCION_SUGERIDA", "HAMMING_DIST",
                "VALOR_USES_ORIGEN", "VALOR_USES_OBS", "DIFERENCIA_USES",
                "DIFERENCIA_USES_ABS", "DISCREPANCIA_CODIGO",
            ]]
            _print_df(obs_filas[cols_ctrl].T.rename(
                columns={obs_filas.index[0]: "valor"}
            ))

    # Buscar en staging para ver el input crudo
    _sep("STAGING (input crudo)")
    for contratista in config.LISTA_CONTRATISTAS:
        nombre_stage = f"staging_{contratista.lower()}"
        try:
            df_stage = io.read_table(nombre_stage, capa="stage")
            # Buscar por ID_EXTERNO del parte (que es parte del hash)
            id_ext = filas.iloc[0].get("ID_EXTERNO")
            if id_ext and not pd.isna(id_ext):
                stage_filas = df_stage.loc[df_stage["ID_EXTERNO"] == id_ext]
                if not stage_filas.empty:
                    print(f"\n  Encontrado en staging_{contratista}:")
                    _print_df(stage_filas.T.rename(
                        columns={stage_filas.index[0]: "valor"}
                    ))
        except FileNotFoundError:
            pass


def inspect_by_suministro(suministro: int, fecha: str | None = None) -> None:
    """Todos los partes de un suministro, opcionalmente filtrado por fecha."""
    config.ensure_layout()
    df_fact = _cargar_fact()

    mask = df_fact["SRV_CODIGO"] == suministro
    if fecha:
        fecha_dt = pd.Timestamp(fecha)
        mask = mask & (pd.to_datetime(df_fact["FECHA"]).dt.normalize() == fecha_dt)

    filas = df_fact.loc[mask].sort_values("FECHA", ascending=False)

    titulo = f"FACT: SRV_CODIGO = {suministro}"
    if fecha:
        titulo += f" | FECHA = {fecha}"
    _sep(titulo)
    print(f"  {len(filas)} parte(s) encontrado(s).\n")

    if filas.empty:
        return

    # Resumen compacto
    cols_resumen = [c for c in [
        "ID_PARTE_HASH", "FECHA", "SRV_CODIGO", "CODIGO_EPEC",
        "DESC_ESTADO", "DESC_TRAZA", "ORD_NRO", "es_pagable",
        "NRO_EQP_COLOCADO", "NRO_EQP_RETIRADO", "EMPRESA",
    ] if c in filas.columns]
    _print_df(filas[cols_resumen])

    # Si hay control_obs, mostrar discrepancias
    df_obs = _cargar_control_obs()
    if df_obs is not None:
        hashes = filas["ID_PARTE_HASH"].tolist()
        obs_filas = df_obs.loc[df_obs["ID_PARTE_HASH"].isin(hashes)]
        if not obs_filas.empty:
            _sep("CONTROL OBS para estos partes")
            cols_ctrl = [c for c in [
                "ID_PARTE_HASH", "DISCREPANCIA_CODIGO", "COD_EPEC_SUGERIDO",
                "VALOR_USES_ORIGEN", "VALOR_USES_OBS", "DIFERENCIA_USES",
            ] if c in obs_filas.columns]
            _print_df(obs_filas[cols_ctrl])


def inspect_by_ord_nro(ord_nro: int) -> None:
    """Todos los partes asociados a un ORD_NRO."""
    config.ensure_layout()
    df_fact = _cargar_fact()

    filas = df_fact.loc[df_fact["ORD_NRO"] == ord_nro].sort_values("FECHA", ascending=False)
    _sep(f"FACT: ORD_NRO = {ord_nro}")
    print(f"  {len(filas)} parte(s) encontrado(s).\n")

    if filas.empty:
        # Buscar en dim_ord directamente
        try:
            df_ord = io.read_table("dim_ord", capa="seed",
                                   columns=["ORD_NUMERO", "SRV_CODIGO", "TOR_CODIGO",
                                             "ORD_RESULTADO", "ORD_FECHA_FIN", "SEC_CODIGO_ORIGEN"])
            ord_filas = df_ord.loc[df_ord["ORD_NUMERO"] == ord_nro]
            if not ord_filas.empty:
                print("  No esta en la fact, pero SI existe en dim_ord:")
                _print_df(ord_filas)
            else:
                print("  Tampoco existe en dim_ord.")
        except FileNotFoundError:
            pass
        return

    cols_resumen = [c for c in [
        "ID_PARTE_HASH", "FECHA", "SRV_CODIGO", "CODIGO_EPEC",
        "DESC_ESTADO", "DESC_TRAZA", "ORD_NRO", "es_pagable", "EMPRESA",
    ] if c in filas.columns]
    _print_df(filas[cols_resumen])


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspecciona un parte individual a traves del pipeline completo."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--hash", type=str, help="ID_PARTE_HASH a inspeccionar")
    group.add_argument("--suministro", type=int, help="SRV_CODIGO (suministro)")
    group.add_argument("--ord-nro", type=int, help="ORD_NRO (numero de orden)")

    parser.add_argument("--fecha", type=str, default=None,
                        help="Fecha (YYYY-MM-DD) para filtrar junto con --suministro")

    args = parser.parse_args()

    if args.hash:
        inspect_by_hash(args.hash)
    elif args.suministro is not None:
        inspect_by_suministro(args.suministro, args.fecha)
    elif args.ord_nro is not None:
        inspect_by_ord_nro(args.ord_nro)


if __name__ == "__main__":
    main()
