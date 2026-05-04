"""Etapa 2 — Adapter COOPLYF.

Portado de `pyspark-version/ingesta_adapter_COOPLYF (2).py`.

Lee los partes diarios de COOPLYF desde `data/input/cooplyf/` (CSV o Excel),
normaliza columnas (aliases múltiples → nombre canónico), parsea fechas de
forma robusta y genera un ID_Externo determinista por SHA256.

Cambios vs Fabric:
  - `mssparkutils.fs.ls` + copia a `/tmp` → `Path.iterdir()` directo.
  - `df.apply(lambda row: sha256(...), axis=1)` → versión vectorizada en
    `src.hashing.id_externo_cooplyf` (mismo output, ~100x más rápido).
  - Bitácora en `stage/_historial_procesados.parquet`.
  - `parsear_fechas_smart` se mantiene BYTE-A-BYTE (fix crítico: elegir entre
    ISO y europeo el formato que produzca menos NaT; en empate, europeo).
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import pandas as pd

from . import adapters_common as ac
from . import config
from . import hashing
from . import io_lakehouse as io

log = logging.getLogger(__name__)

CONTRATISTA = "COOPLYF"
TABLA_STAGING = "pd_cooplyf_aux"

# Mapeo de alias (el Excel/CSV puede traer nombres variados por contratista) →
# nombre canónico. Portado SIN cambios del MAPA_RENOMBRES del original.
MAPA_RENOMBRES: dict[str, str] = {
    # Código de tarea
    "Codigo": "codTiposManoObra", "código": "codTiposManoObra",
    "Código": "codTiposManoObra", "Tarea":  "codTiposManoObra",
    "codTiposManoObra": "codTiposManoObra",
    # Suministro
    "Suministro": "Suministro", "Suministros": "Suministro",
    "NIS": "Suministro", "Cuenta": "Suministro",
    "idSuministros": "Suministro",
    # Fecha
    "fecha": "Fecha", "FECHA": "Fecha",
    # Medidor colocado
    "Medidor Colocado": "medidorColocado", "MedidorColocado": "medidorColocado",
    "colocado": "medidorColocado", "nro_medidor_colocado": "medidorColocado",
    "nroMedidorColocado": "medidorColocado",
    # Medidor retirado
    "Medidor Retirado": "medidorRetirado", "MedidorRetirado": "medidorRetirado",
    "retirado": "medidorRetirado", "nro_medidor_retirado": "medidorRetirado",
    "nroMedidorRetirado": "medidorRetirado",
    # Tipo de trabajo
    "Tipo de trabajo": "TipoTrabajo", "TipoTrabajo": "TipoTrabajo",
    "codTiposTrabajos": "TipoTrabajo",
}

COLS_FINAL = [
    "ID_Externo", "Fecha", "Suministro",
    "medidorColocado", "medidorRetirado",
    "codTiposManoObra", "TipoTrabajo", "ORIGEN_ARCHIVO", "TRAZA_ADAPTER",
]

COLS_LIMPIAR_DECIMALES = [
    "Suministro", "codTiposManoObra", "medidorColocado", "medidorRetirado",
]


# =============================================================================
# Helpers (portados sin cambios salvo eliminación de Spark)
# =============================================================================

def _leer_archivo(path: Path) -> pd.DataFrame | None:
    """Lee CSV o Excel. Para CSV, intenta coma con UTF-8 y cae a punto-y-coma
    con Latin-1 si la primera lectura devuelve menos de 2 columnas."""
    nombre = path.name.lower()
    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(path, sep=",", dtype=str, encoding="utf-8")
            if df.shape[1] < 2:
                df = pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")
            return df
        return pd.read_excel(path, engine="openpyxl", dtype=str)
    except Exception as e:
        log.error("Error leyendo %s: %s", path.name, e)
        return None


def _limpiar_decimales_string(serie: pd.Series) -> pd.Series:
    """Convierte a string y elimina el `.0` espurio que agrega Pandas al
    leer columnas numéricas como objeto. Portado SIN cambios del original."""
    if serie is None:
        return serie
    return (
        serie.astype(str)
             .str.replace(r"\.0$", "", regex=True)
             .replace({"nan": None, "NaT": None, "<NA>": None, "": None, "None": None})
    )


def _parsear_fechas_smart(serie: pd.Series) -> pd.Series:
    """Parsea fechas intentando ambos formatos (ISO y europeo) y eligiendo
    el que produzca menos NaT.

    FIX CRÍTICO del original: un primer registro ambiguo (ej: 01/02/2025)
    hacía que pandas eligiera el parsing equivocado para toda la serie.
    Aquí intentamos ambos y elegimos el de menos NaT; en empate preferimos
    dayfirst=True (estándar Argentina).

    SE MANTIENE BYTE-A-BYTE — cualquier cambio aquí reintroduce el bug.
    """
    serie_str = serie.dropna().astype(str)
    if serie_str.empty:
        return pd.to_datetime(serie, errors="coerce")

    # Suprimimos el UserWarning de pandas cuando el formato no matchea con
    # dayfirst: es parte del comportamiento esperado de la heurística —
    # probamos ambos y elegimos el de menos NaT.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed_iso = pd.to_datetime(serie, dayfirst=False, errors="coerce")
        parsed_eu  = pd.to_datetime(serie, dayfirst=True,  errors="coerce")

    nat_iso = parsed_iso.isna().sum()
    nat_eu  = parsed_eu.isna().sum()

    return parsed_eu if nat_eu <= nat_iso else parsed_iso


# =============================================================================
# Procesamiento por archivo
# =============================================================================

def procesar_archivo(path: Path) -> tuple[pd.DataFrame | None, dict]:
    stats = {"leidos": 0, "guardados": 0}

    df = _leer_archivo(path)
    if df is None:
        return None, stats

    stats["leidos"] = len(df)

    # Normalización de columnas: trim + renombrado por MAPA_RENOMBRES
    df.columns = df.columns.str.strip()
    df = df.rename(columns=MAPA_RENOMBRES)
    df = df.loc[:, ~df.columns.duplicated()]

    # Asegurar que todas las columnas finales existan (aunque sea como NaN)
    for c in COLS_FINAL:
        if c not in df.columns:
            df[c] = None

    # Parseo de fechas — descarta filas de totales (no son partes reales),
    # pero conserva filas con fecha inválida marcándolas con TRAZA_ADAPTER.
    if "Fecha" in df.columns:
        df = df.loc[~df["Fecha"].astype(str).str.contains("Total", case=False, na=False)].copy()
        fechas = _parsear_fechas_smart(df["Fecha"])
        mask_fecha_invalida = fechas.isna()
        df["Fecha"] = fechas.dt.strftime("%Y-%m-%d")
        df.loc[mask_fecha_invalida, "TRAZA_ADAPTER"] = "Fecha Inválida"
        df.loc[mask_fecha_invalida, "Fecha"] = None

    # Limpieza de decimales espurios en columnas numérico-string
    for c in COLS_LIMPIAR_DECIMALES:
        if c in df.columns:
            df[c] = _limpiar_decimales_string(df[c])

    df["ORIGEN_ARCHIVO"] = path.name

    # ID_Externo determinista SHA256[:16] — versión vectorizada del apply original.
    # El contenido del string hasheado es EXACTAMENTE el mismo que el original:
    #   f"{nombre_archivo}|{Suministro}|{Fecha}|{medidorColocado}|{codTiposManoObra}"
    df["ID_Externo"] = hashing.id_externo_cooplyf(
        path.name,
        df["Suministro"],
        df["Fecha"],
        df["medidorColocado"],
        df["codTiposManoObra"],
    )

    df = df[COLS_FINAL]
    stats["guardados"] = len(df)
    return df, stats


# =============================================================================
# Entrypoint
# =============================================================================

def run(modo_reproceso: bool = False) -> dict:
    config.ensure_layout()
    log.info("--- Adapter %s (reproceso=%s) ---", CONTRATISTA, modo_reproceso)

    procesados = set() if modo_reproceso else ac.obtener_historial(CONTRATISTA)
    pendientes = ac.listar_archivos_nuevos(
        config.INPUT_COOPLYF, procesados, extensiones=(".xlsx", ".xls", ".csv")
    )
    log.info("Archivos pendientes: %d (ya en bitácora: %d)", len(pendientes), len(procesados))

    if not pendientes:
        return {"archivos_procesados": 0, "filas_guardadas": 0}

    lotes: list[pd.DataFrame] = []
    nombres_ok: list[str] = []
    total_leido = 0
    total_guardado = 0

    for path in pendientes:
        df_tmp, stats = procesar_archivo(path)
        total_leido    += stats["leidos"]
        total_guardado += stats["guardados"]
        log.info("  %-50s leidos=%-6d guardados=%d",
                 path.name[:50], stats["leidos"], stats["guardados"])
        if df_tmp is not None:
            lotes.append(df_tmp)
        nombres_ok.append(path.name)

    df_lote = pd.concat(lotes, ignore_index=True, sort=False) if lotes else pd.DataFrame()
    filas_guardadas = len(df_lote)

    modo_write = "overwrite" if modo_reproceso else "append"
    if filas_guardadas > 0:
        io.write_table(df_lote, TABLA_STAGING, capa="stage", mode=modo_write)
        log.info("Staging %s actualizado (mode=%s), filas=%d",
                 TABLA_STAGING, modo_write, filas_guardadas)

    ac.registrar_procesados(nombres_ok, CONTRATISTA)

    return {
        "archivos_procesados": len(nombres_ok),
        "filas_leidas":        total_leido,
        "filas_guardadas":     filas_guardadas,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
