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
  - `header=2` fijo → detección automática (prueba rows 0-4, elige el de más matches).
  - Nombres exactos → aliases múltiples igual que el adapter COOPLYF.
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

# Aliases: cualquier variante del archivo real → nombre canónico.
# La clave del dict original (nombre en PySpark) se mantiene como primer alias.
MAPA_RENOMBRES: dict[str, str] = {
    # ID / Nro parte
    "ID": "ID_Externo", "Id": "ID_Externo", "id": "ID_Externo",
    "Nro": "ID_Externo", "N°": "ID_Externo", "Numero": "ID_Externo",
    "Nro Parte": "ID_Externo", "N° Parte": "ID_Externo",
    # Fecha
    "Fecha": "Fecha", "fecha": "Fecha", "FECHA": "Fecha",
    "Fecha Trabajo": "Fecha", "FechaTrabajo": "Fecha",
    # Suministro
    "Suministro": "Suministro", "Suministros": "Suministro",
    "NIS": "Suministro", "Cuenta": "Suministro",
    "N° Suministro": "Suministro", "Nro. Suministro": "Suministro",
    "idSuministros": "Suministro",
    # Medidor colocado
    "Colocado": "medidorColocado", "Medidor Colocado": "medidorColocado",
    "MedidorColocado": "medidorColocado", "medidorColocado": "medidorColocado",
    "Nro Medidor Colocado": "medidorColocado", "nroMedidorColocado": "medidorColocado",
    # Medidor retirado
    "Retirado": "medidorRetirado", "Medidor Retirado": "medidorRetirado",
    "MedidorRetirado": "medidorRetirado", "medidorRetirado": "medidorRetirado",
    "Nro Medidor Retirado": "medidorRetirado", "nroMedidorRetirado": "medidorRetirado",
    # Código de tarea
    "Codigo": "codTiposManoObra", "Código": "codTiposManoObra",
    "código": "codTiposManoObra", "codigo": "codTiposManoObra",
    "Tarea": "codTiposManoObra", "Cod Tarea": "codTiposManoObra",
    "Cod. Tarea": "codTiposManoObra", "codTiposManoObra": "codTiposManoObra",
    "Tipo": "codTiposManoObra",
}

# Columnas canónicas que deben existir en el output (se crean como None si faltan)
COLS_FINAL = [
    "ID_Externo", "Fecha", "Suministro",
    "medidorColocado", "medidorRetirado", "codTiposManoObra",
    "ORIGEN_ARCHIVO",
]

COLS_TEXTO = [
    "ID_Externo", "Suministro", "medidorColocado", "medidorRetirado", "codTiposManoObra",
]

# Filas de encabezado a intentar si el header=2 original no matchea
_HEADER_ROWS_CANDIDATOS = [2, 0, 1, 3, 4]



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


def _detectar_header(path: Path) -> pd.DataFrame | None:
    """Intenta varios header rows y devuelve el DataFrame con más columnas conocidas."""
    mejor_df: pd.DataFrame | None = None
    mejor_score = -1
    for h in _HEADER_ROWS_CANDIDATOS:
        try:
            df = pd.read_excel(path, header=h, dtype=str)
        except Exception:
            continue
        df.columns = df.columns.str.strip()
        score = sum(1 for c in df.columns if c in MAPA_RENOMBRES)
        if score > mejor_score:
            mejor_score = score
            mejor_df = df
    if mejor_df is not None:
        log.info("CONECTAR adapter — header detectado con score=%d cols=%s", mejor_score, list(mejor_df.columns)[:12])
    return mejor_df


def procesar_excel(path: Path, codigos_validos: list[str]) -> tuple[pd.DataFrame | None, dict]:
    """Lee un Excel con detección flexible de header y aliases de columnas.

    Devuelve (df_filtrado_o_None, stats).
    """
    stats = {"total_leido": 0, "aprobados_ce": 0}

    df = _detectar_header(path)
    if df is None:
        log.error("No se pudo leer %s con ningún header candidato.", path.name)
        return None, stats

    # Renombrar usando aliases
    df = df.rename(columns=MAPA_RENOMBRES)
    df = df.loc[:, ~df.columns.duplicated()]

    # Asegurar que todas las columnas canónicas existan
    for c in COLS_FINAL:
        if c not in df.columns:
            df[c] = None

    # Descartar filas de totales/encabezados residuales por fecha no parseable
    if "Fecha" in df.columns:
        df = df.loc[~df["Fecha"].astype(str).str.contains("Total|Fecha", case=False, na=False)]
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
        df = df.loc[df["Fecha"].notna()]

    # Normalización de texto
    for c in COLS_TEXTO:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .replace({"nan": None, "<NA>": None, "None": None, "": None})
            )

    stats["total_leido"] = len(df)

    # Normalización vectorizada de códigos CONECTAR:
    #   "COD 07G." → "07",  "COD 02P44CM5" → "02",  "7" → "07",  "07" → "07"
    if "codTiposManoObra" in df.columns:
        raw = df["codTiposManoObra"].astype(str).str.strip()
        # Extrae los primeros 1-2 dígitos que aparezcan en el valor (ignora prefijo "COD " y sufijos)
        extracted = raw.str.extract(r"(\d{1,2})", expand=False)
        # Donde se extrajo un número → zero-fill; donde no → mantener original
        df["codTiposManoObra"] = extracted.where(extracted.isna(), extracted.str.zfill(2)).where(
            extracted.notna(), raw
        )

    # Filtro por códigos habilitados
    if "codTiposManoObra" in df.columns and codigos_validos:
        codigos_en_archivo = df["codTiposManoObra"].dropna().unique().tolist()
        log.info("CONECTAR adapter — codigos normalizados en archivo: %s | codigos validos: %s",
                 codigos_en_archivo[:20], codigos_validos)
        df_ce = df.loc[df["codTiposManoObra"].isin(codigos_validos)].copy()
        stats["aprobados_ce"] = len(df_ce)
    else:
        log.warning("CONECTAR adapter — sin codTiposManoObra o codigos_validos vacío (total=%d).",
                    stats["total_leido"])
        df_ce = pd.DataFrame()

    if df_ce.empty:
        log.warning("CONECTAR adapter — df_ce vacío tras filtro (total_leido=%d, codigos=%s).",
                    stats["total_leido"], codigos_validos)
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
