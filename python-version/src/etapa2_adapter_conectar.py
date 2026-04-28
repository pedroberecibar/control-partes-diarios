"""Etapa 2 — Adapter CONECTAR.

Portado de `pyspark-version/ingesta_adapter_CONECTAR (1).py`.

Lee los Excels de partes diarios de CONECTAR desde `data/input/conectar/`,
filtra por los códigos de contratista habilitados en `mapeo_codigos_master`
y deja el resultado en `data/stage/pd_conectar_aux.parquet`.

Cambios vs Fabric:
  - `mssparkutils.fs.ls` + copia a `/tmp` → `Path.iterdir()` directo.
  - Bitácora de procesados en `stage/_historial_procesados.parquet`.
  - `pd.concat` dentro del bucle (O(n²)) → acumulo en lista y un solo concat.
  - NO se llama a `spark.createDataFrame` ni se escribe Delta.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import adapters_common as ac
from . import config
from . import io_lakehouse as io

log = logging.getLogger(__name__)

CONTRATISTA = "CONECTAR"
TABLA_STAGING = "pd_conectar_aux"

# Mapeo exacto de columnas del Excel → schema canónico del staging.
# Portado sin cambios del MAPEO_COLUMNAS del script original.
MAPEO_COLUMNAS: dict[str, str] = {
    "ID":         "ID_Externo",
    "Fecha":      "Fecha",
    "Suministro": "Suministro",
    "Colocado":   "medidorColocado",
    "Retirado":   "medidorRetirado",
    "Codigo":     "codTiposManoObra",
}

COLS_TEXTO = [
    "ID_Externo", "Suministro", "medidorColocado", "medidorRetirado", "codTiposManoObra",
]


def obtener_codigos_habilitados() -> list[str]:
    """Lista de códigos de contratista válidos para CONECTAR.

    Se lee del maestro `mapeo_codigos_master` (generado en Fase 1).
    Si el maestro no existe todavía, devuelve lista vacía y se aborta.
    """
    if not io.table_exists("mapeo_codigos_master", capa="master"):
        log.error("Falta mapeo_codigos_master. Corré primero la Etapa 1.")
        return []
    df = io.read_table("mapeo_codigos_master", capa="master")
    df = df.loc[df["CONTRATISTA"] == CONTRATISTA, "COD_CONTRATISTA_INDIVIDUAL"]
    return [str(x) for x in df.dropna().unique()]


def procesar_excel(path: Path, codigos_validos: list[str]) -> tuple[pd.DataFrame | None, dict]:
    """Lee un Excel, aplica mapeo de columnas, filtra por códigos habilitados.

    Devuelve (df_filtrado_o_None, stats).
    """
    stats = {"total_leido": 0, "aprobados_ce": 0}
    try:
        df = pd.read_excel(path, header=2)
    except Exception as e:
        log.error("Error leyendo %s: %s", path.name, e)
        return None, stats

    # Seleccionar columnas presentes y renombrarlas
    cols_existentes = [c for c in MAPEO_COLUMNAS if c in df.columns]
    df = df[cols_existentes].rename(columns=MAPEO_COLUMNAS)

    # Normalización de texto — replica el tratamiento original
    for c in COLS_TEXTO:
        if c in df.columns:
            df[c] = df[c].astype(str).replace({"nan": None, "<NA>": None, "None": None})

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date

    stats["total_leido"] = len(df)

    # Filtro por códigos habilitados (igual que el script original)
    if "codTiposManoObra" in df.columns and codigos_validos:
        df_ce = df.loc[df["codTiposManoObra"].isin(codigos_validos)].copy()
        stats["aprobados_ce"] = len(df_ce)
    else:
        df_ce = pd.DataFrame()

    if df_ce.empty:
        return None, stats

    df_ce["ORIGEN_ARCHIVO"] = path.name
    df_ce["fecha_proceso"]  = datetime.now()
    return df_ce, stats


def run(modo_reproceso: bool = False) -> dict:
    """Procesa todos los Excels pendientes de CONECTAR."""
    config.ensure_layout()
    log.info("--- Adapter %s (reproceso=%s) ---", CONTRATISTA, modo_reproceso)

    codigos_validos = obtener_codigos_habilitados()
    if not codigos_validos:
        log.warning("Sin códigos habilitados para %s. Abortando.", CONTRATISTA)
        return {"archivos_procesados": 0, "filas_guardadas": 0}

    procesados = set() if modo_reproceso else ac.obtener_historial(CONTRATISTA)
    pendientes = ac.listar_archivos_nuevos(
        config.INPUT_CONECTAR, procesados, extensiones=(".xlsx", ".xls")
    )
    log.info("Archivos pendientes: %d (ya en bitácora: %d)", len(pendientes), len(procesados))

    if not pendientes:
        return {"archivos_procesados": 0, "filas_guardadas": 0}

    lotes: list[pd.DataFrame] = []
    nombres_ok: list[str] = []
    total_leido = 0
    total_aprobados = 0

    for path in pendientes:
        df_ce, stats = procesar_excel(path, codigos_validos)
        total_leido     += stats["total_leido"]
        total_aprobados += stats["aprobados_ce"]
        log.info("  %-50s leídos=%-6d aprobados_ce=%d",
                 path.name[:50], stats["total_leido"], stats["aprobados_ce"])
        if df_ce is not None:
            lotes.append(df_ce)
            nombres_ok.append(path.name)
        else:
            # Registramos igual como "ya procesado" para no volver a leerlo
            nombres_ok.append(path.name)

    df_lote = pd.concat(lotes, ignore_index=True, sort=False) if lotes else pd.DataFrame()
    filas_guardadas = len(df_lote)

    # Modo reproceso: pisa el staging. Modo incremental: appendea.
    modo_write = "overwrite" if modo_reproceso else "append"
    if filas_guardadas > 0:
        io.write_table(df_lote, TABLA_STAGING, capa="stage", mode=modo_write)
        log.info("Staging %s: %s (mode=%s), filas=%d",
                 TABLA_STAGING, TABLA_STAGING + ".parquet", modo_write, filas_guardadas)

    ac.registrar_procesados(nombres_ok, CONTRATISTA)

    return {
        "archivos_procesados": len(nombres_ok),
        "filas_leidas":        total_leido,
        "filas_aprobadas":     total_aprobados,
        "filas_guardadas":     filas_guardadas,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
