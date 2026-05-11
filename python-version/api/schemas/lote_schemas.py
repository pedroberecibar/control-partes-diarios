"""
Schemas Pydantic para la entidad Lote de Archivos.
Definen la validación estricta de los DTOs de entrada y salida.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


# --- Request DTOs ---

class LoteCreateRequest(BaseModel):
    """DTO para crear un nuevo lote (subida de archivo)."""
    contratista_id: int = Field(..., description="ID de la contratista (FK)")
    subido_por: int = Field(..., description="ID del usuario que sube el archivo")


# --- Response DTOs ---

class ContratistaResponse(BaseModel):
    id: int
    nombre: str
    activo: bool

    model_config = {"from_attributes": True}


class LoteResponse(BaseModel):
    """DTO de respuesta con el detalle de un lote."""
    id: int
    nombre_archivo: str
    hash_archivo: str
    contratista_id: int
    contratista_nombre: Optional[str] = None
    estado: str
    subido_por: int
    usuario_nombre: Optional[str] = None
    fecha_subida: datetime
    detalle_error: Optional[str] = None
    paso_actual: Optional[str] = None
    progreso_pct: int = 0
    total_filas: int = 0
    n_aprobados: int = 0
    n_revision: int = 0
    n_rechazado: int = 0
    n_fuera_alcance: int = 0

    model_config = {"from_attributes": True}


class LoteListResponse(BaseModel):
    """DTO para listados de lotes con paginación."""
    total: int
    items: list[LoteResponse]


# --- Preview de columnas (sin persistencia) ---

class CampoCanonicoDTO(BaseModel):
    nombre: str
    requerido: bool
    descripcion: str


class PreviewColumnasResponse(BaseModel):
    """Respuesta del endpoint preview-columnas."""
    columnas_detectadas: list[str]
    fila_header: int
    mapeo_sugerido: dict[str, str]    # {col_excel: campo_canonico}
    campos_canonicos: list[CampoCanonicoDTO]


# --- Dashboard por Lote ---

class TrazaItem(BaseModel):
    id_traza: int
    desc_traza: str
    id_estado: int
    desc_estado: str
    count: int
    pct: float


class EpecItem(BaseModel):
    cod_epec: Optional[int]
    desc_epec: Optional[str] = None
    count: int
    total_uses: float
    pct_partes: float


class DiscrepanciaItem(BaseModel):
    tipo: str
    count: int
    pct: float
    delta_uses: float


class OperarioItem(BaseModel):
    operario: str
    n_total: int
    n_aprobados: int
    tasa_aprobacion: float
    total_uses: float


class LoteDashboardResponse(BaseModel):
    lote_id: int
    total_registros: int
    n_aprobados: int
    n_revision: int
    n_rechazado: int
    n_fuera_alcance: int
    efectividad_pct: float
    aprobados_directo: int
    aprobados_corregidos: int
    distribucion_trazas: list[TrazaItem]
    distribucion_epec: list[EpecItem]
    total_uses_aprobados: float
    total_controlados: int
    distribucion_discrepancias: list[DiscrepanciaItem]
    delta_uses_sobrevaloracion: float
    delta_uses_subvaloracion: float
    por_operario: list[OperarioItem]
