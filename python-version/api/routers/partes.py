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
from api.schemas.sugerencias_schemas import CandidatosEpecResponse
from api.services.parte_service import ParteService
from api.services.sugerencias_service import SugerenciasService

router = APIRouter()


@router.get("/", response_model=ParteListResponse, summary="Listar partes procesados")
def listar_partes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=5000),
    id_estado: int | None = Query(None),
    suministro: str | None = Query(None),
    ord_nro: int | None = Query(None),
    id_trazas: list[int] = Query(default=[]),
    id_estados: list[int] = Query(default=[]),
    contratista_ids: list[int] = Query(default=[]),
    lote_ids: list[int] = Query(default=[]),
    cod_epec_ids: list[int] = Query(default=[]),
    search: str | None = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """Lista los partes diarios procesados con filtros opcionales y paginación."""
    return ParteService(db).listar_partes(
        skip=skip, limit=limit,
        id_estado=id_estado, suministro=suministro, ord_nro=ord_nro,
        id_trazas=id_trazas or None,
        id_estados=id_estados or None,
        contratista_ids=contratista_ids or None,
        lote_ids=lote_ids or None,
        cod_epec_ids=cod_epec_ids or None,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/cod-epec/valores", response_model=list[int], summary="Distinct cod_epec presentes en la DB")
def listar_cod_epec_valores(db: Session = Depends(get_db)):
    """Devuelve los valores distintos de cod_epec ordenados ascendente."""
    return ParteService(db).listar_cod_epec_valores()


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


@router.get("/{parte_id}/candidatos-oracle", summary="Buscar ordenativos CE candidatos en la DB local")
def candidatos_oracle(parte_id: int, db: Session = Depends(get_db)):
    """Devuelve ordenativos CE candidatos consultando la DB local sincronizada
    desde Oracle SIGEC (CE + PROTELEM).

    Combina:
    - Búsqueda A: ordenativos del suministro declarado.
    - Búsqueda B: ordenativos del suministro al que están instalados los medidores.

    Si la DB local nunca fue sincronizada, devuelve ``aviso`` orientativo y lista vacía.
    """
    parte = ParteService(db).obtener_parte(parte_id)
    if parte is None:
        raise HTTPException(status_code=404, detail=f"Parte con id={parte_id} no encontrado.")

    from api.services.rescate_ordenativos_service import buscar_candidatos_local
    return buscar_candidatos_local(
        db,
        suministro=parte.suministro or "",
        nro_medidor_colocado=parte.nro_medidor_colocado,
        nro_medidor_retirado=parte.nro_medidor_retirado,
        fecha_ref=parte.fecha_ejecucion,
    )


@router.get(
    "/{parte_id}/codigos-epec-candidatos",
    response_model=CandidatosEpecResponse,
    summary="Sugiere cod_epec candidatos en base a las observaciones del operario",
)
def codigos_epec_candidatos(parte_id: int, db: Session = Depends(get_db)):
    try:
        return SugerenciasService(db).candidatos_para_parte(parte_id)
    except ValueError as e:
        msg = str(e)
        raise HTTPException(status_code=404 if "no existe" in msg else 400, detail=msg)


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
