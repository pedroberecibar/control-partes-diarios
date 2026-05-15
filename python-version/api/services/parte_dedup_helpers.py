"""Helpers de deduplicación de partes — compartidos entre lote_service (Capa 3,
overlap warning al subir un lote) y parte_import_service (rescate cross-lote
post-motor).

Dos funciones:
  * `contar_hashes_existentes`  — cuenta cuántos `ID_PARTE_HASH` (post-motor)
                                  de una lista ya existen en la BD. Reusable
                                  desde el rescate cross-lote (chunked-IN).
  * `contar_overlap_business_keys` — pre-procesamiento: dado un `df_aux`
                                  recién parseado, cuenta cuántas parejas
                                  `(Suministro, Fecha)` ya existen en
                                  `partes_diarios_procesados` para ese
                                  contratista. Usada por la Capa 3 al subir.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from api.db.models.domain_models import ParteDiarioProcesado

_CHUNK_SIZE = 900  # Límite seguro de SQLite para `IN (...)`


def contar_hashes_existentes(
    db: Session,
    hashes: Iterable[str],
    lote_id_excluir: int | None = None,
) -> set[str]:
    """Devuelve el subconjunto de hashes que ya existen en `partes_diarios_procesados`.

    Implementación con chunked-IN para no superar los 999 placeholders de SQLite.

    Si `lote_id_excluir` se provee, se ignoran las filas de ese lote — útil al
    reprocesar un lote para que sus propios hashes viejos no aparezcan como
    duplicados históricos (W-5 self-overlap).
    """
    todos = [h for h in hashes if h]
    if not todos:
        return set()

    existentes: set[str] = set()
    for i in range(0, len(todos), _CHUNK_SIZE):
        chunk = todos[i : i + _CHUNK_SIZE]
        query = (
            db.query(ParteDiarioProcesado.id_parte_hash)
            .filter(ParteDiarioProcesado.id_parte_hash.in_(chunk))
        )
        if lote_id_excluir is not None:
            query = query.filter(ParteDiarioProcesado.lote_id != lote_id_excluir)
        rows = query.all()
        existentes.update(r[0] for r in rows)
    return existentes


def _norm_suministro(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().lower()
    if s in ("", "nan", "none", "<na>"):
        return None
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _norm_fecha(val) -> str | None:
    if val is None:
        return None
    try:
        ts = pd.to_datetime(val, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return None


def contar_overlap_business_keys(
    db: Session,
    contratista_id: int,
    df_aux: pd.DataFrame,
) -> tuple[int, int]:
    """Calcula cuántas parejas `(Suministro, Fecha)` del df_aux ya existen
    en `partes_diarios_procesados` para el contratista dado.

    Devuelve `(n_existentes, n_total)` con `n_total = filas únicas con clave válida`.
    """
    if df_aux is None or df_aux.empty:
        return 0, 0
    if "Suministro" not in df_aux.columns or "Fecha" not in df_aux.columns:
        return 0, 0

    sumi_norm = df_aux["Suministro"].map(_norm_suministro)
    fecha_norm = df_aux["Fecha"].map(_norm_fecha)
    claves_nuevas = {
        (s, f) for s, f in zip(sumi_norm, fecha_norm)
        if s is not None and f is not None
    }
    n_total = len(claves_nuevas)
    if n_total == 0:
        return 0, 0

    rows = (
        db.query(
            ParteDiarioProcesado.suministro,
            ParteDiarioProcesado.fecha_ejecucion,
        )
        .filter(ParteDiarioProcesado.contratista_id == contratista_id)
        .all()
    )
    claves_existentes = {
        (_norm_suministro(s), _norm_fecha(f))
        for s, f in rows
    }
    n_existentes = len(claves_nuevas & claves_existentes)
    return n_existentes, n_total
