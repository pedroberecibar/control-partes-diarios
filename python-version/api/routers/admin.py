"""
Router de administración — Reglas de códigos EPEC y mapeos de contratistas.

Acceso: solo rol 'admin' (validación por convenio; sin auth middleware activo aún).
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from api.core.auth import require_admin
from api.core.database import SessionLocal, get_db
from api.db.models.base_models import Contratista
from api.schemas.admin_schemas import (
    MapeoCodigoContratistaCreate,
    MapeoCodigoContratistaResponse,
    MapeoCodigoContratistaUpdate,
    MapeoItemDTO,
    ReglaCodEpecCreate,
    ReglaCodEpecResponse,
    ReglaCodEpecUpdate,
    SeedResultDTO,
)
from api.schemas.sugerencias_schemas import OpcionEpecDTO
from api.services.reglas_service import ReglaService

router = APIRouter()
log = logging.getLogger("api.routers.admin")


def _to_regla_response(regla, mapeos_map: dict) -> ReglaCodEpecResponse:
    mapeos_regla = mapeos_map.get(regla.cod_epec, [])
    return ReglaCodEpecResponse(
        id=regla.id,
        cod_epec=regla.cod_epec,
        descripcion=regla.descripcion,
        gabinete=regla.gabinete,
        subterraneo=regla.subterraneo,
        altura=regla.altura,
        aereo=regla.aereo,
        equipo_medicion_reemplazado=regla.equipo_medicion_reemplazado,
        acometida_realizada=regla.acometida_realizada,
        tapa_reemplazada=regla.tapa_reemplazada,
        equipo_medicion_instalado=regla.equipo_medicion_instalado,
        valor_uses=regla.valor_uses,
        activo=regla.activo,
        created_at=regla.created_at,
        updated_at=regla.updated_at,
        mapeos=[
            MapeoItemDTO(
                cod_contratista=m.cod_contratista,
                contratista_nombre=m.contratista.nombre if m.contratista else str(m.contratista_id),
                fase=m.fase,
            )
            for m in mapeos_regla
        ],
    )


# ──────────────────────────────────────────────
# Reglas
# ──────────────────────────────────────────────

@router.get("/reglas", response_model=list[ReglaCodEpecResponse], summary="Listar reglas de obs por código EPEC")
def listar_reglas(solo_activas: bool = False, db: Session = Depends(get_db)):
    svc = ReglaService(db)
    reglas = svc.listar_reglas(solo_activas=solo_activas)
    mapeos_map = svc.mapeos_agrupados()
    return [_to_regla_response(r, mapeos_map) for r in reglas]


@router.get(
    "/reglas/cod-epec-opciones",
    response_model=list[OpcionEpecDTO],
    summary="Opciones planas (cod_epec, descripcion, valor_uses) para selectores UI",
)
def listar_opciones_cod_epec(db: Session = Depends(get_db)):
    reglas = ReglaService(db).listar_reglas(solo_activas=True)
    return [
        OpcionEpecDTO(cod_epec=r.cod_epec, descripcion=r.descripcion, valor_uses=r.valor_uses)
        for r in reglas
    ]


@router.get("/reglas/{regla_id}", response_model=ReglaCodEpecResponse, summary="Detalle de una regla")
def obtener_regla(regla_id: int, db: Session = Depends(get_db)):
    svc = ReglaService(db)
    regla = svc.obtener_regla(regla_id)
    if regla is None:
        raise HTTPException(status_code=404, detail=f"Regla id={regla_id} no encontrada.")
    mapeos_map = {regla.cod_epec: svc.mapeos_por_cod_epec(regla.cod_epec)}
    return _to_regla_response(regla, mapeos_map)


@router.post("/reglas", response_model=ReglaCodEpecResponse, status_code=201, summary="Crear nueva regla")
def crear_regla(payload: ReglaCodEpecCreate, db: Session = Depends(get_db)):
    try:
        svc = ReglaService(db)
        regla = svc.crear_regla(payload)
        mapeos_map = {regla.cod_epec: svc.mapeos_por_cod_epec(regla.cod_epec)}
        return _to_regla_response(regla, mapeos_map)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/reglas/{regla_id}", response_model=ReglaCodEpecResponse, summary="Editar una regla")
def actualizar_regla(regla_id: int, payload: ReglaCodEpecUpdate, db: Session = Depends(get_db)):
    try:
        svc = ReglaService(db)
        regla = svc.actualizar_regla(regla_id, payload)
        mapeos_map = {regla.cod_epec: svc.mapeos_por_cod_epec(regla.cod_epec)}
        return _to_regla_response(regla, mapeos_map)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/reglas/{regla_id}", response_model=ReglaCodEpecResponse, summary="Desactivar una regla (soft delete)")
def desactivar_regla(regla_id: int, db: Session = Depends(get_db)):
    try:
        svc = ReglaService(db)
        regla = svc.desactivar_regla(regla_id)
        return _to_regla_response(regla, {})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────
# Mapeos contratista → cod_epec
# ──────────────────────────────────────────────

def _to_mapeo_response(m) -> MapeoCodigoContratistaResponse:
    return MapeoCodigoContratistaResponse(
        id=m.id,
        contratista_id=m.contratista_id,
        contratista_nombre=m.contratista.nombre if m.contratista else None,
        cod_contratista=m.cod_contratista,
        fase=m.fase,
        cod_epec=m.cod_epec,
        descripcion_codigo=m.descripcion_codigo,
        activo=m.activo,
        created_at=m.created_at,
    )


@router.get("/mapeo-codigos", response_model=list[MapeoCodigoContratistaResponse], summary="Listar mapeos")
def listar_mapeos(solo_activos: bool = False, db: Session = Depends(get_db)):
    return [_to_mapeo_response(m) for m in ReglaService(db).listar_mapeos(solo_activos=solo_activos)]


@router.post("/mapeo-codigos", response_model=MapeoCodigoContratistaResponse, status_code=201, summary="Crear mapeo")
def crear_mapeo(payload: MapeoCodigoContratistaCreate, db: Session = Depends(get_db)):
    try:
        return _to_mapeo_response(ReglaService(db).crear_mapeo(payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/mapeo-codigos/{mapeo_id}", response_model=MapeoCodigoContratistaResponse, summary="Editar mapeo")
def actualizar_mapeo(mapeo_id: int, payload: MapeoCodigoContratistaUpdate, db: Session = Depends(get_db)):
    try:
        return _to_mapeo_response(ReglaService(db).actualizar_mapeo(mapeo_id, payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/mapeo-codigos/{mapeo_id}", response_model=MapeoCodigoContratistaResponse, summary="Desactivar mapeo")
def desactivar_mapeo(mapeo_id: int, db: Session = Depends(get_db)):
    try:
        return _to_mapeo_response(ReglaService(db).desactivar_mapeo(mapeo_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ──────────────────────────────────────────────
# Contratistas (lookup)
# ──────────────────────────────────────────────

@router.get("/contratistas", summary="Listar contratistas activos")
def listar_contratistas(db: Session = Depends(get_db)):
    rows = db.query(Contratista).filter(Contratista.activo == True).order_by(Contratista.nombre).all()
    return [{"id": c.id, "nombre": c.nombre} for c in rows]


# ──────────────────────────────────────────────
# Seed inicial
# ──────────────────────────────────────────────

@router.post("/seed", response_model=SeedResultDTO, summary="Poblar tablas ORM desde literales y Parquet (idempotente)")
def seed_inicial(db: Session = Depends(get_db)):
    """Siembra reglas y mapeos si las tablas están vacías. Seguro de ejecutar múltiples veces."""
    resultado = ReglaService(db).seed_desde_literals()
    return SeedResultDTO(
        reglas_insertadas=resultado["reglas"],
        mapeos_insertados=resultado["mapeos"],
        mensaje=(
            "Seed completado."
            if resultado["reglas"] > 0 or resultado["mapeos"] > 0
            else "Las tablas ya tenían datos — nada fue modificado."
        ),
    )


# ──────────────────────────────────────────────
# Sync Oracle SIGEC → SQLite local (CE + PROTELEM)
# ──────────────────────────────────────────────

# Estado en memoria del último sync — se reinicia con el backend, suficiente
# para reflejar progreso/errores en la UI mientras corre el background task.
_sync_state: dict = {"running": False, "last_result": None}


def _ejecutar_sync_background(desde_fecha: str | None) -> None:
    """Wrapper para BackgroundTasks: maneja su propia sesión DB."""
    from api.services.oracle_sync_service import sincronizar_ordenativos_protelem

    _sync_state["running"] = True
    try:
        with SessionLocal() as db:
            metricas = sincronizar_ordenativos_protelem(db, desde_fecha=desde_fecha)
        _sync_state["last_result"] = metricas
    except Exception as e:
        log.exception("Sync background falló inesperadamente: %s", e)
        _sync_state["last_result"] = {
            "errores": [f"{type(e).__name__}: {str(e)[:300]}"],
        }
    finally:
        _sync_state["running"] = False


@router.post(
    "/sync-ordenativos-oracle",
    status_code=202,
    summary="Sincronizar ordenativos CE+PROTELEM desde Oracle SIGEC (admin)",
)
def disparar_sync_ordenativos(
    background_tasks: BackgroundTasks,
    desde_fecha: str | None = None,
    _admin = Depends(require_admin),
):
    """Dispara el sync en background.

    Args:
        desde_fecha: corte inferior en formato ``DD/MM/YYYY``. Si None, usa
            ``config.RESCATE_FECHA_INICIO_BOOTSTRAP`` (por default 31/05/2025).
    """
    if _sync_state["running"]:
        raise HTTPException(
            status_code=409,
            detail="Ya hay un sync en curso. Esperá que termine antes de disparar otro.",
        )
    background_tasks.add_task(_ejecutar_sync_background, desde_fecha)
    return {"mensaje": "Sync iniciado en background.", "desde_fecha": desde_fecha}


@router.get(
    "/sync-ordenativos-oracle/status",
    summary="Estado del sync de ordenativos Oracle (admin)",
)
def estado_sync_ordenativos(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Devuelve último timestamp de sync, counts de las 3 tablas, y resultado del último run."""
    from api.services.oracle_sync_service import obtener_estado_sync

    estado = obtener_estado_sync(db)
    estado["running"] = _sync_state["running"]
    estado["last_result"] = _sync_state["last_result"]
    return estado
