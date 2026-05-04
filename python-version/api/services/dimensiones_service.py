"""Servicio de Dimensiones BI — traducción de FKs lógicas a labels para los DTOs.

Las dimensiones (`dim_traza_calidad_bi`, `dim_estado_bi`, `dim_empresa_bi`,
`dim_usuarios_bi`) viven hoy como Parquet en `data/dim/` (única fuente de verdad
del motor analítico). El service las cachea en memoria al primer uso para que
el resto de la API pueda responder strings amigables sin acoplarse al storage.

Principio aplicado: la capa de servicios traduce identificadores internos
(int FK lógicas) en valores de presentación (strings). Ni el router ni el
frontend conocen los Parquet ni los IDs internos.

Nota sobre cache: usamos `functools.lru_cache` a nivel módulo. Para reload
manual (si el motor regenera las dims), llamar a `dimensiones_service.reload()`.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from src import io_lakehouse as io

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _traza_map() -> dict[int, str]:
    df = io.read_table("dim_traza_calidad_bi", capa="dim")
    return {int(k): str(v) for k, v in df.set_index("ID_TRAZA")["DESC_TRAZA"].items()}


@lru_cache(maxsize=1)
def _estado_map() -> dict[int, str]:
    df = io.read_table("dim_estado_bi", capa="dim")
    return {int(k): str(v) for k, v in df.set_index("ID_ESTADO")["DESC_ESTADO"].items()}


@lru_cache(maxsize=1)
def _empresa_map() -> dict[int, str]:
    df = io.read_table("dim_empresa_bi", capa="dim")
    return {int(k): str(v) for k, v in df.set_index("ID_EMPRESA")["EMPRESA"].items()}


@lru_cache(maxsize=1)
def _usuarios_map() -> dict[int, str]:
    df = io.read_table("dim_usuarios_bi", capa="dim")
    return {int(k): str(v) for k, v in df.set_index("USR_NUMERO")["USR_NOMBRE"].items()}


def traza(id_traza: int | None) -> str | None:
    if id_traza is None:
        return None
    return _traza_map().get(int(id_traza))


def estado(id_estado: int | None) -> str | None:
    if id_estado is None:
        return None
    return _estado_map().get(int(id_estado))


def empresa(id_empresa: int | None) -> str | None:
    if id_empresa is None:
        return None
    return _empresa_map().get(int(id_empresa))


def operario(usr_id: int | None) -> str | None:
    if usr_id is None:
        return None
    return _usuarios_map().get(int(usr_id))


def reload() -> None:
    """Invalida los caches. Llamar si el motor regenera las dimensiones."""
    _traza_map.cache_clear()
    _estado_map.cache_clear()
    _empresa_map.cache_clear()
    _usuarios_map.cache_clear()
    log.info("Dimensiones BI: cache invalidado.")
