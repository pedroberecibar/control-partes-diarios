"""
Router para la gestión de Partes Diarios Procesados.

Capa controlador: solo conoce HTTP y delega al `ParteService`. No accede a la DB
ni a los Parquet. Los DTOs vienen ya enriquecidos por el service.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.schemas.parte_schemas import (
    ParteDetalleResponse,
    ParteEditRequest,
    ParteListResponse,
    ParteVisorDTO,
)
from api.services.parte_service import ParteService

router = APIRouter()


@router.get("/", response_model=ParteListResponse, summary="Listar partes procesados")
def listar_partes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    id_estado: int | None = Query(None, description="Filtrar por estado (1:Aprobado, 2:Revisión, 3:Rechazado, 4:FueraAlcance)"),
    suministro: str | None = Query(None, description="Filtrar por suministro exacto"),
    ord_nro: int | None = Query(None, description="Filtrar por nro de ordenativo"),
    db: Session = Depends(get_db),
):
    """Lista los partes diarios procesados con filtros opcionales y paginación."""
    return ParteService(db).listar_partes(
        skip=skip, limit=limit, id_estado=id_estado,
        suministro=suministro, ord_nro=ord_nro,
    )


@router.get("/{parte_id}", response_model=ParteDetalleResponse, summary="Detalle de un parte")
def obtener_parte(parte_id: int, db: Session = Depends(get_db)):
    """Detalle completo de un parte procesado, con dimensiones resueltas."""
    detalle = ParteService(db).obtener_detalle(parte_id)
    if detalle is None:
        raise HTTPException(status_code=404, detail=f"Parte con id={parte_id} no encontrado.")
    return detalle


@router.get(
    "/{parte_id}/visor",
    response_model=ParteVisorDTO,
    summary="Datos del modal de visor de imágenes (icono cámara en bandeja)",
)
def obtener_visor(parte_id: int, db: Session = Depends(get_db)):
    """Devuelve imágenes + datos esenciales del parte para el modal del visor.

    Se llama al hacer click en el icono cámara de la bandeja (B5) o al abrir
    el bloque de imágenes en el detalle (B6).
    """
    visor = ParteService(db).obtener_visor(parte_id)
    if visor is None:
        raise HTTPException(status_code=404, detail=f"Parte con id={parte_id} no encontrado.")
    return visor


@router.patch("/{parte_id}", response_model=ParteDetalleResponse, summary="Editar un parte (auditoría)")
def editar_parte(
    parte_id: int,
    payload: ParteEditRequest,
    db: Session = Depends(get_db),
):
    """Edita manualmente un parte con Optimistic Locking y auditoría inmutable.

    - Devuelve `409 Conflict` si la versión del payload no coincide con la del registro.
    - Cada campo modificado genera una fila append-only en `auditoria_cambios`.
    """
    try:
        return ParteService(db).editar_parte(parte_id, payload)
    except ValueError as e:
        msg = str(e)
        if "Conflicto de versión" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
