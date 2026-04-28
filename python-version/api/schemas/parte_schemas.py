"""
Schemas Pydantic para la entidad Parte Diario Procesado.

Los DTOs de respuesta exponen labels listos para mostrar (`traza_calidad: str`,
`estado: str`, `operario_nombre: str`, `contratista: str`) además de los IDs
originales para uso interno del frontend (filtros, edición, etc.). El service
los enriquece desde las dimensiones del motor analítico.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Sub-DTOs reutilizables
# ----------------------------------------------------------------------

class ObservacionesAppDTO(BaseModel):
    """Las 8 observaciones que el operario carga en la app móvil."""
    gabinete: bool
    subterraneo: bool
    altura: bool
    aereo: bool
    equipo_medicion_reemplazado: bool
    acometida_realizada: bool
    tapa_reemplazada: bool
    equipo_medicion_instalado: bool


class ParteImagenDTO(BaseModel):
    orden: int = Field(..., ge=1, le=5, description="Orden de visualización (1-5)")
    url: str


# ----------------------------------------------------------------------
# Response DTOs — listado, detalle, modal del visor
# ----------------------------------------------------------------------

class ParteResumenResponse(BaseModel):
    """Fila de la grilla B5 — incluye conteo de imágenes para el badge del icono cámara."""
    id: int
    id_parte_hash: str
    suministro: Optional[str] = None
    fecha_ejecucion: Optional[datetime] = None
    ord_nro: Optional[int] = None
    cod_epec: Optional[int] = None

    # Estado y traza: ID interno + label resuelto por el service
    id_estado: int
    estado: Optional[str] = None
    id_traza: int
    traza_calidad: Optional[str] = None

    contratista: Optional[str] = None
    cant_imagenes: int = 0
    fue_corregido: bool
    anulado: bool


class ParteListResponse(BaseModel):
    total: int
    items: list[ParteResumenResponse]


class ParteDetalleResponse(BaseModel):
    """Detalle completo del parte — usado por la pantalla B6."""
    id: int
    raw_id: int
    id_parte_hash: str
    lote_id: int
    contratista: Optional[str] = None

    # Datos del parte
    suministro: Optional[str] = None
    fecha_ejecucion: Optional[datetime] = None
    nro_medidor_retirado: Optional[str] = None
    nro_medidor_colocado: Optional[str] = None
    operario_nombre: Optional[str] = None

    # Cruces y resultados
    ord_nro: Optional[int] = None
    cod_epec: Optional[int] = None
    id_estado: int
    estado: Optional[str] = None
    id_traza: int
    traza_calidad: Optional[str] = None

    # Control de observaciones
    cod_epec_sugerido: Optional[int] = None
    valor_uses_origen: Optional[float] = None
    valor_uses_obs: Optional[float] = None
    diferencia_uses: Optional[float] = None
    tipo_discrepancia: Optional[str] = None
    observaciones_app: ObservacionesAppDTO

    # Imágenes (1-5 ordenadas)
    imagenes: list[ParteImagenDTO] = Field(default_factory=list)

    # Auditoría
    version: int
    fue_corregido: bool
    anulado: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ParteVisorDTO(BaseModel):
    """DTO compacto para el modal del visor (icono cámara en bandeja).

    Prioriza imágenes y los campos que muestra el panel de detalle del modal.
    No incluye `metricas_analitica` ni payloads pesados.
    """
    id: int
    id_parte_hash: str
    suministro: Optional[str] = None
    fecha_ejecucion: Optional[datetime] = None
    operario_nombre: Optional[str] = None
    nro_medidor_retirado: Optional[str] = None
    nro_medidor_colocado: Optional[str] = None
    imagenes: list[ParteImagenDTO] = Field(default_factory=list)
    observaciones_app: ObservacionesAppDTO


# ----------------------------------------------------------------------
# Request DTOs — edición manual
# ----------------------------------------------------------------------

class ParteEditRequest(BaseModel):
    """Edición manual de un parte por un auditor.

    Política de campos: `None` significa "no tocar este campo".
    Para limpiar un valor existente se requerirá un endpoint específico.
    """
    suministro: Optional[str] = None
    nro_medidor_retirado: Optional[str] = None
    nro_medidor_colocado: Optional[str] = None
    ord_nro: Optional[int] = None
    cod_epec: Optional[int] = None
    id_estado: Optional[int] = Field(None, ge=1, le=4, description="1:Aprobado, 2:Revisión, 3:Rechazado, 4:Fuera de Alcance")
    id_traza: Optional[int] = Field(None, ge=1, description="FK lógica → dim_traza_calidad_bi")

    # Auditoría obligatoria
    motivo: str = Field(..., min_length=5, description="Motivo obligatorio del cambio (mínimo 5 caracteres)")
    usuario_id: int = Field(..., description="ID del auditor que realiza el cambio")
    version: int = Field(..., description="Versión actual del registro (Optimistic Locking)")
