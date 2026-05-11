"""Hashing utilities para antiduplicidad de lotes.

Dos hashes distintos:
  * `hash_bytes`  — SHA256 sobre los bytes crudos del archivo subido.
                    Capa 1 de antiduplicidad (UNIQUE en DB).
  * `hash_contenido_normalizado` — SHA256 sobre el `df_aux` ya parseado por
                    el adapter, normalizado a una representación canónica
                    determinística. Capa 2: detecta el caso "Excel re-guardado
                    (bytes distintos, contenido idéntico)".
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

# Columnas canónicas que devuelve el adapter (ver `etapa2_adapter_conectar.COLS_FINAL`
# y `etapa2_adapter_cooplyf`). Las columnas volátiles (`ORIGEN_ARCHIVO`,
# `fecha_proceso`, `TRAZA_ADAPTER`) se descartan: cambian por upload aunque
# el contenido de negocio sea idéntico.
COLS_CONTENIDO = [
    "ID_Externo",
    "Fecha",
    "Suministro",
    "medidorColocado",
    "medidorRetirado",
    "codTiposManoObra",
]


def hash_bytes(contenido: bytes) -> str:
    """SHA256 hex de los bytes crudos. Determinístico y libre de side effects."""
    return hashlib.sha256(contenido).hexdigest()


def hash_contenido_normalizado(df_aux: pd.DataFrame) -> str:
    """SHA256 hex sobre la representación canónica del df_aux.

    Normalización determinística:
      1. Restringir a `COLS_CONTENIDO` (las que faltan se rellenan vacías).
      2. Strings: strip + lower; NaN → "".
      3. Fechas: ISO `YYYY-MM-DD` sin tiempo.
      4. Sort por `(ID_Externo, Suministro, Fecha)` con `mergesort` para estabilidad.
      5. Serializar como CSV (LF terminator) y hashear los bytes UTF-8.

    Dos `df_aux` con las mismas filas en distinto orden producen el mismo hash.
    Cambiar cualquier celda de las columnas-clave produce un hash distinto.
    """
    if df_aux is None or df_aux.empty:
        return hashlib.sha256(b"").hexdigest()

    df = df_aux.copy()

    for col in COLS_CONTENIDO:
        if col not in df.columns:
            df[col] = ""
    df = df[COLS_CONTENIDO]

    if "Fecha" in df.columns:
        fechas = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Fecha"] = fechas.dt.strftime("%Y-%m-%d").fillna("")

    for col in ("ID_Externo", "Suministro", "medidorColocado", "medidorRetirado", "codTiposManoObra"):
        s = df[col]
        s = s.where(~s.isna(), "")
        df[col] = s.astype(str).str.strip().str.lower().replace({"nan": "", "none": "", "<na>": ""})

    df = df.sort_values(
        by=["ID_Externo", "Suministro", "Fecha"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)

    payload = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
