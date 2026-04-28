"""
Router para la gestión de Lotes de Archivos.
Controlador HTTP — delega toda la lógica al LoteService.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from api.services.worker import procesar_lote_en_background
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.schemas.lote_schemas import LoteResponse, LoteListResponse
from api.services.lote_service import LoteService

router = APIRouter()


@router.get("/", response_model=LoteListResponse, summary="Listar lotes")
def listar_lotes(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(50, ge=1, le=200, description="Cantidad máxima de resultados"),
    db: Session = Depends(get_db),
):
    """Devuelve todos los lotes de archivos subidos, ordenados por fecha descendente."""
    service = LoteService(db)
    return service.listar_lotes(skip=skip, limit=limit)


@router.get("/{lote_id}", response_model=LoteResponse, summary="Detalle de un lote")
def obtener_lote(lote_id: int, db: Session = Depends(get_db)):
    """Devuelve el detalle de un lote específico por su ID."""
    service = LoteService(db)
    lote = service.obtener_lote(lote_id)
    if not lote:
        raise HTTPException(status_code=404, detail=f"Lote con id={lote_id} no encontrado.")
    return LoteResponse.model_validate(lote)


@router.post("/", response_model=LoteResponse, status_code=201, summary="Subir un nuevo lote")
async def crear_lote(
    background_tasks: BackgroundTasks,
    contratista_id: int = Query(..., description="ID de la contratista"),
    subido_por: int = Query(..., description="ID del usuario que sube"),
    archivo: UploadFile = File(..., description="Archivo Excel (.xlsx / .xls / .csv)"),
    db: Session = Depends(get_db),
):
    """Sube un archivo Excel y crea un registro de lote con estado RECIBIDO.
    
    El archivo se valida por hash SHA256 para evitar duplicados.
    En un futuro, este endpoint disparará el procesamiento asíncrono (worker).
    """
    contenido = await archivo.read()

    service = LoteService(db)
    try:
        lote = service.crear_lote(
            nombre_archivo=archivo.filename or "sin_nombre.xlsx",
            contenido_bytes=contenido,
            contratista_id=contratista_id,
            subido_por=subido_por,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Lanzar procesamiento en background
    background_tasks.add_task(procesar_lote_en_background, lote.id)

    return LoteResponse.model_validate(lote)


@router.patch("/{lote_id}/estado", response_model=LoteResponse, summary="Actualizar estado del lote")
def actualizar_estado_lote(
    lote_id: int,
    nuevo_estado: str = Query(..., description="Nuevo estado (PROCESANDO, COMPLETADO, ERROR, etc.)"),
    detalle_error: str | None = Query(None, description="Detalle del error si aplica"),
    db: Session = Depends(get_db),
):
    """Actualiza el estado de un lote. Usado internamente por el worker de procesamiento."""
    service = LoteService(db)
    try:
        lote = service.actualizar_estado(lote_id, nuevo_estado, detalle_error)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return LoteResponse.model_validate(lote)
