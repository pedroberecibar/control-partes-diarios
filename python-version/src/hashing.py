"""Helpers de hashing determinista.

Reproducen byte-a-byte el resultado de las expresiones PySpark:

  sha2(concat_ws("|", ORIGEN_ARCHIVO, Suministro_Final, to_date(Fecha),
                  coalesce(medidorColocado, "NULL"), codTiposManoObra), 256)

La estabilidad entre ejecuciones es clave: `ID_PARTE_HASH` es la llave del
MERGE de la fact table. Si el hash cambia entre runs, el MERGE deja de ser
idempotente y se generan duplicados.
"""

from __future__ import annotations

import hashlib

import pandas as pd


def _as_str_spark(serie: pd.Series) -> pd.Series:
    """Convierte a string al estilo `col.cast("string")` de Spark.

    - NaN/NaT/None → "" (Spark concat_ws omite nulos; reproducimos esto
      dejando el placeholder vacío en las columnas opcionales).
    - Fechas → ISO (`YYYY-MM-DD`) para igualar `to_date(col).cast("string")`.
    - Numéricos → sin decimales espurios si son enteros (1.0 → "1").
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie.dt.strftime("%Y-%m-%d").fillna("")

    if pd.api.types.is_float_dtype(serie):
        # Evita "1.0" → "1" donde Spark castearía long a string sin decimal
        out = serie.astype("object")
        mask_int = serie.notna() & (serie % 1 == 0)
        out.loc[mask_int] = serie.loc[mask_int].astype("Int64").astype("string")
        out.loc[~mask_int] = serie.loc[~mask_int].astype("string")
        return out.fillna("").astype("string")

    return serie.astype("string").fillna("")


def id_parte_hash(
    origen_archivo: pd.Series,
    srv_codigo:     pd.Series,
    fecha:          pd.Series,
    medidor_colocado: pd.Series,
    cod_tipos_mano_obra: pd.Series,
) -> pd.Series:
    """SHA256 hex (64 chars) sobre los 5 campos concatenados con '|'.

    `medidor_colocado` se coalesces a "NULL" cuando es NaN, replicando
    `coalesce(medidorColocado.cast("string"), lit("NULL"))` del script.
    Las demás columnas usan "" para nulos (Spark concat_ws las omite, pero
    al ser posiciones fijas entre separadores, "" produce la misma salida).
    """
    med_str = _as_str_spark(medidor_colocado).mask(medidor_colocado.isna(), "NULL")

    concat = (
        _as_str_spark(origen_archivo)     + "|" +
        _as_str_spark(srv_codigo)         + "|" +
        _as_str_spark(fecha)              + "|" +
        med_str                           + "|" +
        _as_str_spark(cod_tipos_mano_obra)
    )
    return concat.map(lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest())


def id_externo_cooplyf(
    nombre_archivo: str,
    suministro: pd.Series,
    fecha: pd.Series,
    medidor_colocado: pd.Series,
    cod_tipos_mano_obra: pd.Series,
) -> pd.Series:
    """SHA256[:16] para el ID_Externo determinista de COOPLYF.

    Replica la lambda fila-a-fila del adapter, pero vectorizada:

        f"{nombre_archivo}|{Suministro}|{Fecha}|{medidorColocado}|{codTiposManoObra}"

    Nota: el script original NO aplica coalesce → "NULL" en medidorColocado,
    solo usa row.get(...,'') que devuelve "" para NaN/None. Respetamos esa
    semántica (usar "" para todos los nulos).
    """
    concat = (
        nombre_archivo + "|" +
        suministro.fillna("").astype("string") + "|" +
        fecha.fillna("").astype("string") + "|" +
        medidor_colocado.fillna("").astype("string") + "|" +
        cod_tipos_mano_obra.fillna("").astype("string")
    )
    return concat.map(lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:16])
