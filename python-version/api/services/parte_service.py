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

# Pivot column → model field mapping (mirrors _OBS_MAPPING in parte_import_service).
_PIVOT_TO_OBS_FIELD: dict[str, str] = {
    "GABINETE":                     "obs_gabinete",
    "SUBTERRANEO":                  "obs_subterraneo",
    "ALTURA":                       "obs_altura",
    "AEREO":                        "obs_aereo",
    "EQUIPO_MEDICION_REEMPLAZADO":  "obs_equipo_medicion_reemplazado",
    "ACOMETIDA_REALIZADA":          "obs_acometida_realizada",
    "TAPA_REEMPLAZADA":             "obs_tapa_reemplazada",
    "EQUIPO_DE_MEDICION_INSTALADO": "obs_equipo_medicion_instalado",
}


def _norm_val(v) -> str:
    """Normalize a DB/payload value to a string for change-detection comparison.

    Strips trailing '.0' so that float 100.0 and int 100 compare equal.
    """
    if v is None:
        return ""
    s = str(v)
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        return s[:-2]
    return s


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
        lote_ids: list[int] | None = None,
        cod_epec_ids: list[int] | None = None,
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
        if lote_ids:
            query = query.filter(ParteDiarioProcesado.lote_id.in_(lote_ids))
        if cod_epec_ids:
            query = query.filter(ParteDiarioProcesado.cod_epec.in_(cod_epec_ids))
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

    def listar_cod_epec_valores(self) -> list[int]:
        rows = (
            self.db.query(ParteDiarioProcesado.cod_epec)
            .filter(ParteDiarioProcesado.cod_epec.isnot(None))
            .distinct()
            .order_by(ParteDiarioProcesado.cod_epec)
            .all()
        )
        return [r.cod_epec for r in rows]

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

        Fallback de imágenes: si el parte no tiene filas en `parte_imagenes` pero
        tiene `ord_nro`, consulta Oracle para obtener las fotos del ordenativo.
        """
        parte = self.obtener_parte(parte_id)
        if parte is None:
            return None

        if parte.imagenes:
            imagenes_dto = [
                ParteImagenDTO(orden=i.orden, url=i.url)
                for i in sorted(parte.imagenes, key=lambda i: i.orden)
            ]
        elif parte.ord_nro:
            imagenes_dto = self._fotos_oracle_visor(parte.ord_nro)
        else:
            imagenes_dto = []

        return ParteVisorDTO(
            id=parte.id,
            id_parte_hash=parte.id_parte_hash,
            suministro=parte.suministro,
            fecha_ejecucion=parte.fecha_ejecucion,
            operario_nombre=dims.operario(parte.usr_id),
            nro_medidor_retirado=parte.nro_medidor_retirado,
            nro_medidor_colocado=parte.nro_medidor_colocado,
            imagenes=imagenes_dto,
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

    def _fotos_oracle_visor(self, ord_nro: int) -> list[ParteImagenDTO]:
        """Fotos del ordenativo para el visor.

        Lee primero la DB local (`OrdenativoOracleFoto`, poblada por
        `oracle_sync_service`). Si no hay registros — porque el ORD_NRO precede
        la ventana de bootstrap o el sync nunca se corrió — cae a Oracle live.
        """
        local = self._fotos_locales(ord_nro)
        if local:
            return local
        try:
            from api.services.oracle_service import get_fotos_por_ord_numeros
            fotos_map = get_fotos_por_ord_numeros([ord_nro])
            fotos = fotos_map.get(ord_nro, {})
            return [
                ParteImagenDTO(orden=i, url=fotos[f"imagen_{i}"])
                for i in range(1, 6)
                if fotos.get(f"imagen_{i}")
            ]
        except Exception:
            logger.warning("Fallback Oracle live para visor falló (ord_nro=%s)", ord_nro)
            return []

    def _fotos_locales(self, ord_nro: int) -> list[ParteImagenDTO]:
        """Lee fotos del ordenativo desde la DB local sincronizada."""
        from api.db.models.domain_models import OrdenativoOracleFoto
        rows = (
            self.db.query(OrdenativoOracleFoto)
            .filter(OrdenativoOracleFoto.ord_numero == ord_nro)
            .all()
        )
        return [
            ParteImagenDTO(orden=r.posicion, url=r.url)
            for r in sorted(rows, key=lambda r: r.posicion)
            if r.url
        ]

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

        # Capturamos id_traza/id_estado ANTES del bucle para distinguir reclasificación
        # automática de cambios explícitos del auditor.
        id_traza_previo  = parte.id_traza
        id_estado_previo = parte.id_estado

        for campo in self.CAMPOS_EDITABLES:
            nuevo_valor = getattr(payload, campo, None)
            if nuevo_valor is None:
                continue  # NULL = no tocar — política decidida en bug report 2026-04-28
            valor_anterior = getattr(parte, campo)
            if _norm_val(valor_anterior) == _norm_val(nuevo_valor):
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

        # Si obs_* están vacías y hay ORD_NRO, poblar desde pivot (partes que llegaron
        # como "En Revisión" y no fueron procesados por Etapa 4 en el import original).
        obs_vacias = not any(
            getattr(parte, f) for f in _PIVOT_TO_OBS_FIELD.values()
        )
        if obs_vacias and parte.ord_nro:
            self._poblar_obs_desde_pivot(parte, parte.ord_nro)

        # Reclasificación automática: si el parte estaba en "Sin Orden Asociada" (7) o
        # "Múltiples Candidatos Oracle" (20) y el auditor le asignó un ord_nro,
        # pasar a "Rescatado por Oracle" (19) en estado Revisión (2). Solo aplica si
        # el auditor NO cambió id_traza explícitamente en este mismo payload.
        TRAZA_RESCATADO   = 19
        ESTADO_REVISION   = 2
        TRAZAS_RESCATABLES = (7, 20)
        if (
            "ord_nro" in cambios_realizados
            and id_traza_previo in TRAZAS_RESCATABLES
            and parte.id_traza in TRAZAS_RESCATABLES  # auditor no la cambió manualmente
            and parte.ord_nro is not None
        ):
            motivo_auto = "Auto-reclasificación tras asignación de ord_nro"
            if parte.id_traza != TRAZA_RESCATADO:
                self.db.add(AuditoriaCambio(
                    parte_procesado_id=parte_id,
                    usuario_id=payload.usuario_id,
                    campo_modificado="id_traza",
                    valor_anterior=str(parte.id_traza),
                    valor_nuevo=str(TRAZA_RESCATADO),
                    motivo=motivo_auto,
                    version_resultante=nueva_version,
                ))
                parte.id_traza = TRAZA_RESCATADO
                cambios_realizados.append("id_traza")
            if parte.id_estado != ESTADO_REVISION and id_estado_previo == parte.id_estado:
                self.db.add(AuditoriaCambio(
                    parte_procesado_id=parte_id,
                    usuario_id=payload.usuario_id,
                    campo_modificado="id_estado",
                    valor_anterior=str(parte.id_estado),
                    valor_nuevo=str(ESTADO_REVISION),
                    motivo=motivo_auto,
                    version_resultante=nueva_version,
                ))
                parte.id_estado = ESTADO_REVISION
                cambios_realizados.append("id_estado")

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

    def _poblar_obs_desde_pivot(self, parte: ParteDiarioProcesado, ord_nro: int) -> None:
        """Busca observaciones en pivot_resul_app_movil y las escribe en parte.obs_*.

        Solo se llama cuando obs_* están todos en False (partes procesados antes de
        Etapa 4 o partes en Revisión que no pasaron por el filtro Aprobado de E4).
        Falla silenciosa si el pivot no existe o no tiene el ORD_NRO.
        """
        try:
            import pandas as pd
            from src import io_lakehouse as io

            cols = ["ORD_NUMERO"] + list(_PIVOT_TO_OBS_FIELD.keys())
            df = io.read_table("pivot_resul_app_movil", capa="seed", columns=cols)
            match = df[df["ORD_NUMERO"] == ord_nro]
            if match.empty:
                logger.info("pivot_resul_app_movil: sin fila para ord_nro=%d", ord_nro)
                return
            row = match.iloc[0]
            for col_pivot, field in _PIVOT_TO_OBS_FIELD.items():
                val = row.get(col_pivot)
                setattr(parte, field, bool(val) if pd.notna(val) else False)
            logger.info("Obs pobladas desde pivot para ord_nro=%d", ord_nro)
        except Exception:
            logger.warning("_poblar_obs_desde_pivot falló (ord_nro=%s)", ord_nro, exc_info=True)

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
