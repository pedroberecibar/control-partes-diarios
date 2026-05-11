"""Excepciones de dominio para el servicio de Lotes.

Mapeadas a HTTP 409 con `code` discriminante en el router. El frontend usa
`code` para decidir si mostrar error duro (DUP_*) o modal de confirmación
(OVERLAP_WARN).
"""
from __future__ import annotations


class DuplicadoBytesError(Exception):
    """El archivo subido tiene los mismos bytes que un lote previo (Capa 1)."""

    code = "DUP_BYTES"

    def __init__(self, lote_existente_id: int, mensaje: str | None = None):
        self.lote_existente_id = lote_existente_id
        super().__init__(mensaje or f"Archivo idéntico ya subido (lote_id={lote_existente_id}).")


class DuplicadoContenidoError(Exception):
    """El contenido lógico (post-parse) coincide con un lote previo (Capa 2).

    Cubre el caso de Excel re-guardado: bytes distintos, mismas filas de negocio.
    """

    code = "DUP_CONTENT"

    def __init__(self, lote_existente_id: int, mensaje: str | None = None):
        self.lote_existente_id = lote_existente_id
        super().__init__(
            mensaje
            or f"El contenido del archivo coincide con un lote previo (lote_id={lote_existente_id})."
        )


class OverlapWarning(Exception):
    """Una fracción significativa de los partes ya fueron procesados (Capa 3).

    No es un error duro: el endpoint lo devuelve como 409 con `requires_force=True`.
    El usuario puede confirmar y reintentar con `?force=true`.
    """

    code = "OVERLAP_WARN"

    def __init__(self, overlap_pct: float, n_existentes: int, n_total: int):
        self.overlap_pct = overlap_pct
        self.n_existentes = n_existentes
        self.n_total = n_total
        super().__init__(
            f"{n_existentes}/{n_total} partes ({overlap_pct:.0%}) ya existen en lotes previos."
        )
