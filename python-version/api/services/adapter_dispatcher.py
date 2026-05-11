"""Dispatch del adapter según contratista — extraído de `worker._ejecutar_adapter`.

Compartido entre el worker (procesamiento del lote) y el lote_service
(antiduplicidad por contenido normalizado, Capa 2). Centraliza la lógica
para que ambos consumidores parseen el archivo igual.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger("api.services.adapter_dispatcher")


def ejecutar_adapter(path: Path, nombre_contratista: str) -> pd.DataFrame | None:
    """Aplica el adapter del contratista y devuelve el DataFrame normalizado (df_aux)."""
    contratista_upper = nombre_contratista.upper()

    if contratista_upper == "CONECTAR":
        from src.etapa2_adapter_conectar import (
            obtener_codigos_habilitados,
            procesar_excel,
        )
        df_aux, _ = procesar_excel(path, obtener_codigos_habilitados())
        return df_aux

    if contratista_upper == "COOPLYF":
        from src.etapa2_adapter_cooplyf import procesar_archivo
        df_aux, _ = procesar_archivo(path)
        return df_aux

    log.warning(
        "Contratista '%s' sin adapter dedicado — fallback a read_excel directo.",
        nombre_contratista,
    )
    return pd.read_excel(path)
