"""Detecta columnas del Excel/CSV sin persistir — usado por el endpoint preview-columnas.

Lee el archivo con varios header candidatos, elige el mejor y devuelve:
- columnas detectadas
- mapeo sugerido (col_excel → campo_canónico) usando MAPA_RENOMBRES del adapter
- lista de campos canónicos del sistema con su metadata
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger("api.services.columnas_preview")

# Campos canónicos del sistema — orden mostrado en la UI de mapeo.
CAMPOS_CANONICOS: list[dict[str, Any]] = [
    {"nombre": "Fecha",            "requerido": True,  "descripcion": "Fecha del trabajo"},
    {"nombre": "Suministro",       "requerido": True,  "descripcion": "Número de suministro eléctrico"},
    {"nombre": "codTiposManoObra", "requerido": True,  "descripcion": "Código de tarea/obra"},
    {"nombre": "medidorColocado",  "requerido": False, "descripcion": "Número de medidor instalado"},
    {"nombre": "medidorRetirado",  "requerido": False, "descripcion": "Número de medidor retirado"},
    {"nombre": "ID_Externo",       "requerido": False, "descripcion": "Identificador externo (referencia contratista)"},
    {"nombre": "Operario",         "requerido": False, "descripcion": "Nombre del operario"},
]

_HEADER_CANDIDATOS = [2, 0, 1, 3, 4]


def detectar_columnas(path: Path, contratista_nombre: str) -> dict[str, Any]:
    """Detecta columnas del archivo y sugiere mapeo hacia campos canónicos.

    Returns:
        {
            "columnas_detectadas": [...],
            "fila_header": int,
            "mapeo_sugerido": {"col_excel": "campo_canonico", ...},
            "campos_canonicos": [{nombre, requerido, descripcion}, ...]
        }
    """
    alias_to_canonico = _get_alias_map(contratista_nombre)

    mejor_df: pd.DataFrame | None = None
    mejor_score = -1
    mejor_header = 0

    nombre = path.name.lower()
    is_csv = nombre.endswith(".csv")

    for h in _HEADER_CANDIDATOS:
        df = _intentar_leer(path, h, is_csv)
        if df is None:
            continue
        cols = [str(c).strip() for c in df.columns]
        score = sum(1 for c in cols if c in alias_to_canonico)
        if score > mejor_score:
            mejor_score = score
            mejor_df = df
            mejor_header = h

    if mejor_df is None:
        log.warning("detectar_columnas — no pudo leer %s", path.name)
        return {
            "columnas_detectadas": [],
            "fila_header": 0,
            "mapeo_sugerido": {},
            "campos_canonicos": CAMPOS_CANONICOS,
        }

    columnas = [
        str(c).strip()
        for c in mejor_df.columns
        if str(c).strip() and not str(c).startswith("Unnamed")
    ]

    mapeo_sugerido: dict[str, str] = {}
    for col in columnas:
        canonico = alias_to_canonico.get(col)
        if canonico:
            mapeo_sugerido[col] = canonico

    log.info(
        "detectar_columnas — %s header=%d score=%d cols=%d mapeadas=%d",
        contratista_nombre, mejor_header, mejor_score, len(columnas), len(mapeo_sugerido),
    )

    return {
        "columnas_detectadas": columnas,
        "fila_header": mejor_header,
        "mapeo_sugerido": mapeo_sugerido,
        "campos_canonicos": CAMPOS_CANONICOS,
    }


def _intentar_leer(path: Path, header: int, is_csv: bool) -> pd.DataFrame | None:
    try:
        if is_csv:
            df = pd.read_csv(path, header=header, nrows=3, dtype=str, encoding="utf-8")
            if df.shape[1] < 2:
                df = pd.read_csv(path, header=header, nrows=3, dtype=str, encoding="latin-1", sep=";")
        else:
            df = pd.read_excel(path, header=header, nrows=3, dtype=str)
        return df if df.shape[1] >= 2 else None
    except Exception:
        return None


def _get_alias_map(contratista_nombre: str) -> dict[str, str]:
    nombre = contratista_nombre.upper()
    if nombre == "CONECTAR":
        from src.etapa2_adapter_conectar import MAPA_RENOMBRES
        return MAPA_RENOMBRES
    if nombre == "COOPLYF":
        from src.etapa2_adapter_cooplyf import MAPA_RENOMBRES
        return MAPA_RENOMBRES
    return {}
