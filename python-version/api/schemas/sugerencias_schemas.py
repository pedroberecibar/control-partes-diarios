"""DTOs de la subsección de sugerencias de cod_epec en DetallePartes."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CandidatoEpecDTO(BaseModel):
    cod_epec: int
    descripcion: str
    hamming: int = Field(..., ge=0, le=8)
    score: int = Field(..., ge=0, le=8)            # 8 - hamming
    valor_uses: float
    campos_diferentes: list[str]                   # ej: ["GABINETE", "ALTURA"]
    # Comparación del USES del candidato contra el USES del cod_epec declarado por el contratista.
    # None si el parte no tiene valor_uses_origen (no se puede determinar).
    valoracion: Optional[Literal["sobrevaluacion", "subvaluacion", "equivalente"]] = None


class CandidatosEpecResponse(BaseModel):
    parte_id: int
    sin_observaciones: bool
    obs_parte: list[str]                           # nombres de obs en True (informativo)
    match_exacto: list[CandidatoEpecDTO]           # hamming=0 (puede haber varios)
    cercanos: list[CandidatoEpecDTO]               # top 3 con hamming>0
    todas: list[CandidatoEpecDTO]                  # todas las reglas activas — preview Hamming sin round-trip


class OpcionEpecDTO(BaseModel):
    cod_epec: int
    descripcion: str
    valor_uses: float
