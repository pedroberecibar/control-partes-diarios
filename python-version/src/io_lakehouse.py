"""Capa de IO que simula el Lakehouse Fabric con Parquet en disco.

Reemplaza `spark.table(...)`, `df.write.format("delta")...saveAsTable(...)`
y `DeltaTable.merge(...)` por operaciones sobre archivos Parquet.

Escritura atómica: se escribe a `<archivo>.parquet.tmp` y luego se hace
`os.replace` — en el mismo filesystem eso es atómico también en Windows,
así que un kill -9 no deja la tabla corrupta.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import config

Capa = Literal["input", "seed", "stage", "master", "dim", "gold"]
Mode = Literal["overwrite", "append"]


def _ruta(nombre: str, capa: Capa) -> Path:
    if capa not in config.CAPAS:
        raise ValueError(f"Capa desconocida: {capa!r}")
    return config.CAPAS[capa] / f"{nombre}.parquet"


def table_exists(nombre: str, capa: Capa) -> bool:
    return _ruta(nombre, capa).exists()


def read_table(
    nombre: str,
    capa: Capa,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Lee una tabla Parquet. Lanza FileNotFoundError si no existe.

    `columns` (opcional): proyecta solo esas columnas del Parquet — leer
    la subset desde disco es ~10x más eficiente en RAM y tiempo que cargar
    todo y filtrar después. Si una columna pedida no existe, se ignora
    silenciosamente (consistente con cómo el Core trabaja con seeds que
    pueden tener cols opcionales).
    """
    ruta = _ruta(nombre, capa)
    if not ruta.exists():
        raise FileNotFoundError(f"Tabla no encontrada: {ruta}")
    if columns is None:
        return pd.read_parquet(ruta)
    schema = pq.read_schema(ruta)
    cols_disponibles = [c for c in columns if c in schema.names]
    return pd.read_parquet(ruta, columns=cols_disponibles)


def write_table(
    df: pd.DataFrame,
    nombre: str,
    capa: Capa,
    mode: Mode = "overwrite",
) -> Path:
    """Escribe una tabla Parquet de forma atómica.

    mode="overwrite": pisa la tabla existente.
    mode="append":    concatena con la tabla existente (sin deduplicar).
    """
    ruta = _ruta(nombre, capa)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    if mode == "append" and ruta.exists():
        df = pd.concat([pd.read_parquet(ruta), df], ignore_index=True, sort=False)

    tmp = ruta.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False, compression="snappy")
    os.replace(tmp, ruta)
    return ruta


def write_table_chunked(
    chunks: Iterable[pd.DataFrame],
    nombre: str,
    capa: Capa,
) -> tuple[Path, int]:
    """Escribe un Parquet único a partir de un iterador de DataFrames.

    Útil para tablas grandes (ej. dim_ord ~5.7M filas): el lado Oracle
    fetchea por chunks (no satura el driver), pero acá unificamos los
    schemas y escribimos un único archivo.

    Schema promotion: `pd.read_sql(chunksize=...)` infiere dtypes por chunk,
    así que la misma columna puede salir `int64` en uno y `float64` en otro
    (típico cuando aparece un NaN). Usamos `pa.concat_tables(promote_options=
    'permissive')` para promover al tipo más amplio sin romper.

    Atomicidad: `<archivo>.parquet.tmp` + `os.replace`.

    Devuelve (ruta_final, total_filas_escritas).
    """
    ruta = _ruta(nombre, capa)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".parquet.tmp")

    arrow_tables: list[pa.Table] = []
    total = 0
    for chunk_df in chunks:
        if chunk_df is None or len(chunk_df) == 0:
            continue
        arrow_tables.append(pa.Table.from_pandas(chunk_df, preserve_index=False))
        total += len(chunk_df)

    if not arrow_tables:
        pd.DataFrame().to_parquet(tmp, index=False, compression="snappy")
    else:
        unified = pa.concat_tables(arrow_tables, promote_options="permissive")
        pq.write_table(unified, tmp, compression="snappy")

    os.replace(tmp, ruta)
    return ruta, total


def merge_table(
    df_new: pd.DataFrame,
    nombre: str,
    capa: Capa,
    key: str,
) -> Path:
    """Upsert sobre una tabla por clave única (semántica `whenMatchedUpdateAll`).

    - Si en `df_new` hay filas duplicadas por `key`, se conserva la **última**
      (matchea el "last wins" del MERGE Delta cuando el source tiene dups).
    - Si la fila ya existe en la tabla destino con la misma `key`, se pisa.
    - Si no existe, se inserta.
    """
    if key not in df_new.columns:
        raise KeyError(f"La clave {key!r} no está en df_new")

    # Dedup del source antes del merge: Spark `whenMatchedUpdateAll` con
    # source duplicado es undefined (algunas builds lanzan error). El `keep="last"`
    # garantiza determinismo y refleja la intención de "el último parte cargado gana".
    df_new = df_new.drop_duplicates(subset=[key], keep="last")

    ruta = _ruta(nombre, capa)
    if ruta.exists():
        df_old = pd.read_parquet(ruta)
        if key in df_old.columns:
            df_old = df_old.loc[~df_old[key].isin(df_new[key])]
        out = pd.concat([df_old, df_new], ignore_index=True, sort=False)
    else:
        out = df_new

    return write_table(out, nombre, capa, mode="overwrite")


def truncate_table(nombre: str, capa: Capa) -> None:
    """Vacía una tabla (equivalente a TRUNCATE TABLE).

    Se implementa escribiendo un DataFrame vacío con el mismo schema, en vez
    de borrar el archivo, para que lecturas posteriores no fallen con
    FileNotFoundError y se pueda preservar el schema.
    """
    ruta = _ruta(nombre, capa)
    if not ruta.exists():
        return
    df_vacio = pd.read_parquet(ruta).iloc[0:0]
    write_table(df_vacio, nombre, capa, mode="overwrite")
