"""Utilidades compartidas por los adapters de la Etapa 2.

Sustituye a la bitácora que en Fabric estaba implícita en
`fact_partes_diarios_full.ORIGEN_ARCHIVO` (CONECTAR) y en
`spark.sql("SELECT DISTINCT ORIGEN_ARCHIVO FROM ...")` (COOPLYF).

En local usamos una tabla dedicada en `stage/_historial_procesados.parquet`
para que los adapters puedan funcionar sin depender de la fact table aún.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import io_lakehouse as io

log = logging.getLogger(__name__)

BITACORA_NAME = "_historial_procesados"
BITACORA_COLS = ["ORIGEN_ARCHIVO", "CONTRATISTA", "FECHA_PROCESO"]


def obtener_historial(contratista: str) -> set[str]:
    """Devuelve el set de nombres de archivo ya procesados para esta contratista."""
    if not io.table_exists(BITACORA_NAME, capa="stage"):
        return set()
    df = io.read_table(BITACORA_NAME, capa="stage")
    if df.empty:
        return set()
    return set(df.loc[df["CONTRATISTA"] == contratista, "ORIGEN_ARCHIVO"])


def registrar_procesados(nombres: list[str], contratista: str) -> None:
    """Agrega nombres a la bitácora (idempotente: si ya están, no duplica)."""
    if not nombres:
        return
    df_nuevos = pd.DataFrame({
        "ORIGEN_ARCHIVO": nombres,
        "CONTRATISTA":    contratista,
        "FECHA_PROCESO":  datetime.now(),
    })

    if io.table_exists(BITACORA_NAME, capa="stage"):
        df_hist = io.read_table(BITACORA_NAME, capa="stage")
        ya = set(df_hist.loc[df_hist["CONTRATISTA"] == contratista, "ORIGEN_ARCHIVO"])
        df_nuevos = df_nuevos.loc[~df_nuevos["ORIGEN_ARCHIVO"].isin(ya)]
        if df_nuevos.empty:
            return
        df_out = pd.concat([df_hist, df_nuevos], ignore_index=True, sort=False)
    else:
        df_out = df_nuevos

    io.write_table(df_out[BITACORA_COLS], BITACORA_NAME, capa="stage", mode="overwrite")


def listar_archivos_nuevos(
    carpeta: Path,
    procesados: set[str],
    extensiones: tuple[str, ...] = (".xlsx", ".xls"),
) -> list[Path]:
    """Escanea `carpeta` y devuelve los archivos con extensión válida
    que no estén ya en `procesados` y no sean lock files (`~...`)."""
    if not carpeta.exists():
        log.warning("Carpeta no existe: %s", carpeta)
        return []
    return sorted(
        p for p in carpeta.iterdir()
        if p.is_file()
        and p.suffix.lower() in extensiones
        and not p.name.startswith("~")
        and p.name not in procesados
    )
