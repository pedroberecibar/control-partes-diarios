"""
Servicio de Partes Diarios — Capa de lógica de negocio para consulta y edición.

Responsabilidad única (SRP):
- Lectura/listado/detalle de partes ya procesados.
- Edición manual con auditoría e Optimistic Locking.

La importación masiva desde el motor analítico vive en `ParteImportService`.

Separación de capas (DIP): el service traduce los IDs internos
(`id_traza`, `id_estado`, `usr_id`, `contratista_id`) a strings amigables
usando `dimensiones_service` y devuelve DTOs ya enriquecidos. El router
no conoce ni la base de datos ni los Parquet.
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session

from api.db.models.base_models import Contratista
from api.db.models.domain_models import ParteDiarioProcesado, ParteDiarioRaw, AuditoriaCambio
from api.schemas.parte_schemas import (
    ObservacionesAppDTO,
    ParteEditRequest,
    ParteImagenDTO,
    ParteListResponse,
    ParteResumenResponse,
    ParteVisorDTO,
    ParteDetalleResponse,
)
from api.services import dimensiones_service as dims

logger = logging.getLogger("api.services.parte")


class ParteService:
    """Servicio de consulta y edición de partes procesados."""

    # Campos editables y nombres legibles para la auditoría
    CAMPOS_EDITABLES = (
        "suministro",
        "nro_medidor_retirado",
        "nro_medidor_colocado",
        "ord_nro",
        "cod_epec",
        "id_estado",
        "id_traza",
    )

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Listado (B5 — Bandeja de Auditoría)
    # ------------------------------------------------------------------

    _SORT_COLS = {
        "id":         ParteDiarioProcesado.id,
        "fecha":      ParteDiarioProcesado.fecha_ejecucion,
        "suministro": ParteDiarioProcesado.suministro,
        "ord_nro":    ParteDiarioProcesado.ord_nro,
        "traza":      ParteDiarioProcesado.id_traza,
        "id_traza":   ParteDiarioProcesado.id_traza,
        "estado":     ParteDiarioProcesado.id_estado,
        "uses":       ParteDiarioProcesado.valor_uses_origen,
    }

    def listar_partes(
        self,
        skip: int = 0,
        limit: int = 50,
        id_estado: int | None = None,
        suministro: str | None = None,
        ord_nro: int | None = None,
        id_trazas: list[int] | None = None,
        id_estados: list[int] | None = None,
        contratista_ids: list[int] | None = None,
        search: str | None = None,
        sort_by: str = "id",
        sort_dir: str = "desc",
    ) -> ParteListResponse:
        """Lista partes procesados con filtros opcionales y paginación."""
        query = self.db.query(ParteDiarioProcesado)

        # Legacy single-value filters
        if id_estado is not None:
            query = query.filter(ParteDiarioProcesado.id_estado == id_estado)
        if suministro:
            query = query.filter(ParteDiarioProcesado.suministro == suministro)
        if ord_nro is not None:
            query = query.filter(ParteDiarioProcesado.ord_nro == ord_nro)

        # Multi-value filters
        if id_trazas:
            query = query.filter(ParteDiarioProcesado.id_traza.in_(id_trazas))
        if id_estados:
            query = query.filter(ParteDiarioProcesado.id_estado.in_(id_estados))
        if contratista_ids:
            query = query.filter(ParteDiarioProcesado.contratista_id.in_(contratista_ids))
        if search:
            term = f"%{search}%"
            query = query.filter(or_(
                ParteDiarioProcesado.suministro.ilike(term),
                cast(ParteDiarioProcesado.ord_nro, String).ilike(term),
                cast(ParteDiarioProcesado.id, String).ilike(term),
            ))

        # Sorting
        sort_col = self._SORT_COLS.get(sort_by, ParteDiarioProcesado.id)
        order_expr = sort_col.asc() if sort_dir == "asc" else sort_col.desc()

        total = query.count()
        items = (
            query.order_by(order_expr)
            .offset(skip)
            .limit(limit)
            .all()
        )

        # Pre-cargar contratistas e id_externo para evitar N+1
        contratistas_map = self._contratistas_por_id(items)
        id_externos_map = self._id_externos_por_raw_id(items)

        return ParteListResponse(
            total=total,
            items=[
                self._to_resumen_dto(
                    p,
                    contratistas_map.get(p.contratista_id),
                    id_externos_map.get(p.raw_id),
                )
                for p in items
            ],
        )

    # ------------------------------------------------------------------
    # Detalle (B6) y modal del visor
    # ------------------------------------------------------------------

    def obtener_parte(self, parte_id: int) -> ParteDiarioProcesado | None:
        """Obtiene la entidad ORM cruda. Para uso interno; el router consume DTOs."""
        return (
            self.db.query(ParteDiarioProcesado)
            .filter(ParteDiarioProcesado.id == parte_id)
            .first()
        )

    def obtener_detalle(self, parte_id: int) -> ParteDetalleResponse | None:
        """Detalle completo del parte con todas las dimensiones resueltas."""
        parte = self.obtener_parte(parte_id)
        if parte is None:
            return None
        return self._to_detalle_dto(parte)

    def obtener_visor(self, parte_id: int) -> ParteVisorDTO | None:
        """DTO compacto para el modal del visor (icono cámara en B5 + bloque en B6).

        Prioriza las imágenes y los campos esenciales (suministro, medidores,
        operario, observaciones). No incluye el `metricas_analitica` ni la auditoría.
        """
        parte = self.obtener_parte(parte_id)
        if parte is None:
            return None

        imagenes = sorted(parte.imagenes, key=lambda i: i.orden)

        return ParteVisorDTO(
            id=parte.id,
            id_parte_hash=parte.id_parte_hash,
            suministro=parte.suministro,
            fecha_ejecucion=parte.fecha_ejecucion,
            operario_nombre=dims.operario(parte.usr_id),
            nro_medidor_retirado=parte.nro_medidor_retirado,
            nro_medidor_colocado=parte.nro_medidor_colocado,
            imagenes=[
                ParteImagenDTO(orden=i.orden, url=i.url) for i in imagenes
            ],
            observaciones_app=ObservacionesAppDTO(
                gabinete=parte.obs_gabinete,
                subterraneo=parte.obs_subterraneo,
                altura=parte.obs_altura,
                aereo=parte.obs_aereo,
                equipo_medicion_reemplazado=parte.obs_equipo_medicion_reemplazado,
                acometida_realizada=parte.obs_acometida_realizada,
                tapa_reemplazada=parte.obs_tapa_reemplazada,
                equipo_medicion_instalado=parte.obs_equipo_medicion_instalado,
            ),
        )

    # ------------------------------------------------------------------
    # Edición — Optimistic Locking + auditoría
    # ------------------------------------------------------------------

    def editar_parte(self, parte_id: int, payload: ParteEditRequest) -> ParteDetalleResponse:
        """Edita un parte con Optimistic Locking y auditoría append-only.

        Política de NULL en payload: NULL = "no tocar este campo".
        Para limpiar un valor existente, usar el endpoint específico (no implementado).
        """
        parte = self.obtener_parte(parte_id)
        if not parte:
            raise ValueError(f"Parte con id={parte_id} no existe.")

        # Optimistic Locking
        if parte.version != payload.version:
            raise ValueError(
                f"Conflicto de versión: se esperaba version={payload.version} "
                f"pero el registro tiene version={parte.version}. "
                f"Otro usuario pudo haber editado este parte. Refresque y vuelva a intentar."
            )

        nueva_version = parte.version + 1
        cambios_realizados: list[str] = []

        for campo in self.CAMPOS_EDITABLES:
            nuevo_valor = getattr(payload, campo, None)
            if nuevo_valor is None:
                continue  # NULL = no tocar — política decidida en bug report 2026-04-28
            valor_anterior = getattr(parte, campo)
            if str(valor_anterior) == str(nuevo_valor):
                continue

            self.db.add(AuditoriaCambio(
                parte_procesado_id=parte_id,
                usuario_id=payload.usuario_id,
                campo_modificado=campo,
                valor_anterior=str(valor_anterior) if valor_anterior is not None else None,
                valor_nuevo=str(nuevo_valor),
                motivo=payload.motivo,
                version_resultante=nueva_version,
            ))
            setattr(parte, campo, nuevo_valor)
            cambios_realizados.append(campo)

        if not cambios_realizados:
            raise ValueError("No se detectaron cambios respecto a los valores actuales.")

        parte.version = nueva_version
        parte.fue_corregido = True

        # TODO: re-ejecutar reglas de negocio (recalcular USES, Hamming, cruces) cuando
        # se integre el motor analítico al flujo de edición.
        logger.info(
            "Parte id=%d editado: campos=%s, version=%d, usuario=%d",
            parte_id, cambios_realizados, nueva_version, payload.usuario_id,
        )

        self.db.commit()
        self.db.refresh(parte)
        return self._to_detalle_dto(parte)

    # ------------------------------------------------------------------
    # Mappers ORM → DTO (separación de capas: el frontend ve labels, no IDs)
    # ------------------------------------------------------------------

    def _to_resumen_dto(
        self,
        parte: ParteDiarioProcesado,
        contratista_nombre: str | None,
        id_externo: str | None = None,
    ) -> ParteResumenResponse:
        return ParteResumenResponse(
            id=parte.id,
            id_parte_hash=parte.id_parte_hash,
            suministro=parte.suministro,
            fecha_ejecucion=parte.fecha_ejecucion,
            ord_nro=parte.ord_nro,
            cod_epec=parte.cod_epec,
            id_estado=parte.id_estado,
            estado=dims.estado(parte.id_estado),
            id_traza=parte.id_traza,
            traza_calidad=dims.traza(parte.id_traza),
            contratista_id=parte.contratista_id,
            contratista=contratista_nombre,
            operario_nombre=dims.operario(parte.usr_id),
            id_externo=id_externo,
            valor_uses=parte.valor_uses_origen,
            cant_imagenes=len(parte.imagenes),
            fue_corregido=parte.fue_corregido,
            anulado=parte.anulado,
        )

    def _to_detalle_dto(self, parte: ParteDiarioProcesado) -> ParteDetalleResponse:
        contratista_nombre = self._contratistas_por_id([parte]).get(parte.contratista_id)
        imagenes = sorted(parte.imagenes, key=lambda i: i.orden)
        return ParteDetalleResponse(
            id=parte.id,
            raw_id=parte.raw_id,
            id_parte_hash=parte.id_parte_hash,
            lote_id=parte.lote_id,
            contratista=contratista_nombre,
            suministro=parte.suministro,
            fecha_ejecucion=parte.fecha_ejecucion,
            nro_medidor_retirado=parte.nro_medidor_retirado,
            nro_medidor_colocado=parte.nro_medidor_colocado,
            operario_nombre=dims.operario(parte.usr_id),
            ord_nro=parte.ord_nro,
            cod_epec=parte.cod_epec,
            id_estado=parte.id_estado,
            estado=dims.estado(parte.id_estado),
            id_traza=parte.id_traza,
            traza_calidad=dims.traza(parte.id_traza),
            cod_epec_sugerido=parte.cod_epec_sugerido,
            valor_uses_origen=parte.valor_uses_origen,
            valor_uses_obs=parte.valor_uses_obs,
            diferencia_uses=parte.diferencia_uses,
            tipo_discrepancia=parte.tipo_discrepancia,
            observaciones_app=ObservacionesAppDTO(
                gabinete=parte.obs_gabinete,
                subterraneo=parte.obs_subterraneo,
                altura=parte.obs_altura,
                aereo=parte.obs_aereo,
                equipo_medicion_reemplazado=parte.obs_equipo_medicion_reemplazado,
                acometida_realizada=parte.obs_acometida_realizada,
                tapa_reemplazada=parte.obs_tapa_reemplazada,
                equipo_medicion_instalado=parte.obs_equipo_medicion_instalado,
            ),
            imagenes=[ParteImagenDTO(orden=i.orden, url=i.url) for i in imagenes],
            version=parte.version,
            fue_corregido=parte.fue_corregido,
            anulado=parte.anulado,
            created_at=parte.created_at,
            updated_at=parte.updated_at,
        )

    def _contratistas_por_id(
        self, partes: Iterable[ParteDiarioProcesado]
    ) -> dict[int, str]:
        ids = {p.contratista_id for p in partes if p.contratista_id is not None}
        if not ids:
            return {}
        rows = (
            self.db.query(Contratista.id, Contratista.nombre)
            .filter(Contratista.id.in_(ids))
            .all()
        )
        return {row.id: row.nombre for row in rows}

    def _id_externos_por_raw_id(
        self, partes: Iterable[ParteDiarioProcesado]
    ) -> dict[int, str]:
        raw_ids = {p.raw_id for p in partes if p.raw_id is not None}
        if not raw_ids:
            return {}
        rows = (
            self.db.query(ParteDiarioRaw.id, ParteDiarioRaw.id_externo)
            .filter(ParteDiarioRaw.id.in_(raw_ids))
            .all()
        )
        return {row.id: row.id_externo for row in rows if row.id_externo}
