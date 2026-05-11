"""Etapa 3.1 + 3.2 — Dimensiones BI estáticas y `dim_archivo_bi`.

Portado de la Celda 2 de `pyspark-version/procesar_pd_gral_refactor (5).py`:

  - dim_empresa_bi          (literal)
  - dim_estado_bi           (literal)
  - dim_traza_calidad_bi    (literal — única fuente de verdad de IDs)
  - dim_usuarios_bi         (desde seed/usuarios_gral, dedup por USR_NUMERO)
  - dim_archivo_bi          (idempotente, IDs secuenciales por archivo nuevo)

Salida en `data/dim/`. Estos parquet son inputs del Core (Etapa 3.3) y de
Power BI.
"""

from __future__ import annotations

import logging

import pandas as pd

from . import config
from . import io_lakehouse as io

log = logging.getLogger(__name__)


# =============================================================================
# 3.1 — Dimensiones literales y dim_usuarios
# =============================================================================

# Datos literales copiados de procesar_pd_gral_refactor.py L.180-208.
# Mantener IDs estables: cualquier renumeración invalida la fact ya escrita.

_DATOS_DIM_EMPRESA: list[tuple[int, str]] = [
    (1, "CONECTAR"),
    (2, "COOPLYF"),
]

_DATOS_DIM_ESTADO: list[tuple[int, str]] = [
    (1, "Aprobado"),
    (2, "Revisión"),
    (3, "Rechazado"),
    (4, "Fuera de Alcance"),
]

_DATOS_DIM_TRAZA: list[tuple[int, str]] = [
    (1,  "Original OK"),
    (2,  "Corregido Nro EQP Invertidos"),
    (3,  "Corregido Nro Medidor"),
    (4,  "Corregido Sumi"),
    (5,  "Corregido Sumi Nro EQP"),
    (6,  "No Corresponde TOR CE"),
    (7,  "Sin Orden Asociada"),
    (8,  "Error Sumi Sin Nro Medidor"),
    (9,  "Error Sumi Y Nro Medidor"),
    (10, "Informados con ORD-SUMI aprobado"),
    (11, "Otro Origen"),
    (12, "Corregido Medidor Vacio"),
    (13, "Informado - No Ejecutado"),
    (14, "Código de Tarea No Mapeado"),
    (15, "Fecha Inválida"),
    (16, "Duplicado Exacto en Archivo Origen"),
    (17, "Datos Clave Faltantes"),
    (18, "Registro Ya Procesado en Lote Anterior"),
    (19, "Rescatado por Oracle"),
    (20, "Múltiples Candidatos Oracle"),
]


def generar_dim_empresa_bi() -> pd.DataFrame:
    df = pd.DataFrame(_DATOS_DIM_EMPRESA, columns=["ID_EMPRESA", "EMPRESA"]).astype(
        {"ID_EMPRESA": "int64", "EMPRESA": "string"}
    )
    io.write_table(df, "dim_empresa_bi", capa="dim", mode="overwrite")
    log.info("dim_empresa_bi: %d filas", len(df))
    return df


def generar_dim_estado_bi() -> pd.DataFrame:
    df = pd.DataFrame(_DATOS_DIM_ESTADO, columns=["ID_ESTADO", "DESC_ESTADO"]).astype(
        {"ID_ESTADO": "int64", "DESC_ESTADO": "string"}
    )
    io.write_table(df, "dim_estado_bi", capa="dim", mode="overwrite")
    log.info("dim_estado_bi: %d filas", len(df))
    return df


def generar_dim_traza_calidad_bi() -> pd.DataFrame:
    df = pd.DataFrame(_DATOS_DIM_TRAZA, columns=["ID_TRAZA", "DESC_TRAZA"]).astype(
        {"ID_TRAZA": "int64", "DESC_TRAZA": "string"}
    )
    io.write_table(df, "dim_traza_calidad_bi", capa="dim", mode="overwrite")
    log.info("dim_traza_calidad_bi: %d filas", len(df))
    return df


def generar_dim_usuarios_bi() -> pd.DataFrame:
    """Lee usuarios_gral (seed) y deja USR_NUMERO + USR_NOMBRE únicos.

    [FIX] dropDuplicates por USR_NUMERO (NO por ambas cols). Si un mismo
    USR_NUMERO tiene variaciones tipográficas en USR_NOMBRE, la versión
    "distinct sobre ambas" mete duplicados y rompe joins downstream.
    """
    df_full = io.read_table("usuarios_gral", capa="seed")
    cols_req = ["USR_NUMERO", "USR_NOMBRE"]
    faltantes = [c for c in cols_req if c not in df_full.columns]
    if faltantes:
        raise KeyError(
            f"Seed usuarios_gral no tiene columnas requeridas: {faltantes}. "
            f"Cols presentes: {list(df_full.columns)}"
        )

    df = (
        df_full[cols_req]
        .drop_duplicates(subset=["USR_NUMERO"])
        .reset_index(drop=True)
    )
    io.write_table(df, "dim_usuarios_bi", capa="dim", mode="overwrite")
    log.info("dim_usuarios_bi: %d filas (de %d en seed)", len(df), len(df_full))
    return df


# =============================================================================
# 3.2 — dim_archivo_bi (idempotente)
# =============================================================================

def actualizar_dim_archivo(nombres_nuevos: list[str]) -> dict[str, int]:
    """Asigna ID_ARCHIVO secuencial a cada nombre de archivo único.

    Comportamiento idempotente:
      - Archivos ya conocidos conservan su ID original.
      - Archivos nuevos reciben IDs `max_id + 1, max_id + 2, ...`
        (ordenados por nombre para determinismo).
      - Si no hay nuevos, NO reescribe la dimensión.

    Devuelve el mapa completo {nombre_archivo: ID_ARCHIVO} listo para
    usar como lookup en la fact.
    """
    if not nombres_nuevos:
        if io.table_exists("dim_archivo_bi", capa="dim"):
            df_existente = io.read_table("dim_archivo_bi", capa="dim")
            return dict(zip(df_existente["NOMBRE_ARCHIVO"], df_existente["ID_ARCHIVO"]))
        return {}

    if io.table_exists("dim_archivo_bi", capa="dim"):
        df_existente = io.read_table("dim_archivo_bi", capa="dim")
        max_id = int(df_existente["ID_ARCHIVO"].max()) if len(df_existente) else 0
        existentes = dict(zip(df_existente["NOMBRE_ARCHIVO"], df_existente["ID_ARCHIVO"]))
    else:
        max_id = 0
        existentes = {}

    nuevos = sorted({n for n in nombres_nuevos if n not in existentes})
    nuevos_con_id = {nombre: max_id + idx + 1 for idx, nombre in enumerate(nuevos)}

    mapa_completo = {**existentes, **nuevos_con_id}

    if nuevos_con_id:
        df_dim_nueva = pd.DataFrame(
            [(v, k) for k, v in mapa_completo.items()],
            columns=["ID_ARCHIVO", "NOMBRE_ARCHIVO"],
        ).astype({"ID_ARCHIVO": "int64", "NOMBRE_ARCHIVO": "string"})
        # Orden determinista por ID para que el archivo no varíe entre runs sin cambios.
        df_dim_nueva = df_dim_nueva.sort_values("ID_ARCHIVO").reset_index(drop=True)
        io.write_table(df_dim_nueva, "dim_archivo_bi", capa="dim", mode="overwrite")
        log.info("dim_archivo_bi actualizada: %d archivo(s) nuevo(s) registrado(s).",
                 len(nuevos_con_id))
    else:
        log.info("dim_archivo_bi sin cambios (todos los archivos ya estaban registrados).")

    return mapa_completo


def _gather_nombres_archivo_del_lote() -> list[str]:
    """Junta los ORIGEN_ARCHIVO únicos del staging actual (CONECTAR + COOPLYF)."""
    nombres: set[str] = set()
    for tabla in ("pd_conectar_aux", "pd_cooplyf_aux"):
        if not io.table_exists(tabla, capa="stage"):
            continue
        df = io.read_table(tabla, capa="stage")
        if "ORIGEN_ARCHIVO" not in df.columns:
            continue
        nombres.update(
            n for n in df["ORIGEN_ARCHIVO"].dropna().astype(str).unique() if n
        )
    return sorted(nombres)


# =============================================================================
# Entrypoint
# =============================================================================

def run() -> dict:
    """Ejecuta sub-tickets 3.1 + 3.2 en una sola corrida."""
    config.ensure_layout()

    df_emp   = generar_dim_empresa_bi()
    df_est   = generar_dim_estado_bi()
    df_traza = generar_dim_traza_calidad_bi()
    df_usr   = generar_dim_usuarios_bi()

    nombres_lote = _gather_nombres_archivo_del_lote()
    mapa = actualizar_dim_archivo(nombres_lote)

    return {
        "dim_empresa_bi":       len(df_emp),
        "dim_estado_bi":        len(df_est),
        "dim_traza_calidad_bi": len(df_traza),
        "dim_usuarios_bi":      len(df_usr),
        "dim_archivo_bi":       len(mapa),
        "archivos_en_lote":     len(nombres_lote),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run())
