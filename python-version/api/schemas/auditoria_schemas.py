"""
Schemas Pydantic para la entidad Auditoría de Cambios.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AuditoriaResponse(BaseModel):
    """DTO de respuesta para un registro de auditoría."""
    id: int
    parte_procesado_id: int
    usuario_id: int
    usuario_nombre: Optional[str] = None
    campo_modificado: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    motivo: str
    fecha_cambio: datetime
    version_resultante: int

    model_config = {"from_attributes": True}


class AuditoriaListResponse(BaseModel):
    """DTO para listados de auditoría."""
    total: int
    items: list[AuditoriaResponse]
