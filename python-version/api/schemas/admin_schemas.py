from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MapeoItemDTO(BaseModel):
    cod_contratista: str
    contratista_nombre: str
    fase: str


class ReglaCodEpecBase(BaseModel):
    cod_epec: int
    descripcion: str
    gabinete: bool = False
    subterraneo: bool = False
    altura: bool = False
    aereo: bool = False
    equipo_medicion_reemplazado: bool = False
    acometida_realizada: bool = False
    tapa_reemplazada: bool = False
    equipo_medicion_instalado: bool = False
    valor_uses: float = Field(..., gt=0)


class ReglaCodEpecCreate(ReglaCodEpecBase):
    pass


class ReglaCodEpecUpdate(BaseModel):
    descripcion: Optional[str] = None
    gabinete: Optional[bool] = None
    subterraneo: Optional[bool] = None
    altura: Optional[bool] = None
    aereo: Optional[bool] = None
    equipo_medicion_reemplazado: Optional[bool] = None
    acometida_realizada: Optional[bool] = None
    tapa_reemplazada: Optional[bool] = None
    equipo_medicion_instalado: Optional[bool] = None
    valor_uses: Optional[float] = Field(None, gt=0)
    activo: Optional[bool] = None


class ReglaCodEpecResponse(ReglaCodEpecBase):
    id: int
    activo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    mapeos: list[MapeoItemDTO] = []

    class Config:
        from_attributes = True


class MapeoCodigoContratistaBase(BaseModel):
    contratista_id: int
    cod_contratista: str
    fase: str
    cod_epec: int
    descripcion_codigo: Optional[str] = None


class MapeoCodigoContratistaCreate(MapeoCodigoContratistaBase):
    pass


class MapeoCodigoContratistaUpdate(BaseModel):
    cod_contratista: Optional[str] = None
    fase: Optional[str] = None
    cod_epec: Optional[int] = None
    descripcion_codigo: Optional[str] = None
    activo: Optional[bool] = None


class MapeoCodigoContratistaResponse(MapeoCodigoContratistaBase):
    id: int
    activo: bool
    contratista_nombre: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SeedResultDTO(BaseModel):
    reglas_insertadas: int
    mapeos_insertados: int
    mensaje: str
