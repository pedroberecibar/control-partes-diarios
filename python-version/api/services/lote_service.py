"""
Servicio de Lotes — Capa de lógica de negocio para la ingesta de archivos.
Principio SOLID: Single Responsibility — este servicio solo orquesta lotes.
"""
import logging
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.core.database import BASE_DIR, SessionLocal
from api.db.models.base_models import LoteArchivo, Contratista
from api.db.models.domain_models import ParteDiarioProcesado
from api.schemas.lote_schemas import LoteResponse, LoteListResponse
from api.services.adapter_dispatcher import ejecutar_adapter
from api.services.exceptions import (
    DuplicadoBytesError,
    DuplicadoContenidoError,
    OverlapWarning,
)
from api.services.hash_service import hash_bytes, hash_contenido_normalizado
from api.services.parte_dedup_helpers import contar_overlap_business_keys
from src.config import OVERLAP_WARNING_THRESHOLD

logger = logging.getLogger("api.services.lote")

_TRAZA_NOMBRES: dict[int, str] = {
    1:  "Original OK",
    2:  "Corregido Nro EQP Invertidos",
    3:  "Corregido Nro Medidor",
    4:  "Corregido Sumi",
    5:  "Corregido Sumi Nro EQP",
    6:  "No Corresponde TOR CE",
    7:  "Sin Orden Asociada",
    8:  "Error Sumi Sin Nro Medidor",
    9:  "Error Sumi Y Nro Medidor",
    10: "Informados con ORD-SUMI aprobado",
    11: "Otro Origen",
    12: "Corregido Medidor Vacio",
    13: "Informado - No Ejecutado",
    14: "Código de Tarea No Mapeado",
    15: "Fecha Inválida",
    16: "Duplicado Exacto en Archivo Origen",
    17: "Datos Clave Faltantes",
    18: "Registro Ya Procesado en Lote Anterior",
    19: "Rescatado por Oracle",
    20: "Múltiples Candidatos Oracle",
}

_ESTADO_NOMBRES: dict[int, str] = {
    1: "Aprobado",
    2: "Revisión",
    3: "Rechazado",
    4: "Fuera de Alcance",
}


# Carpeta de uploads — alineada con `BASE_DIR` (python-version/) ya usada en database.py.
# Los binarios se conservan indefinidamente para auditoría.
UPLOADS_DIR = Path(BASE_DIR) / "data" / "uploads"


class LoteService:
    """Servicio para operaciones sobre lotes de archivos."""

    def __init__(self, db: Session):
        self.db = db

    def listar_lotes(self, skip: int = 0, limit: int = 50) -> LoteListResponse:
        """Lista todos los lotes ordenados por fecha de subida descendente."""
        total = self.db.query(LoteArchivo).count()
        items = (
            self.db.query(LoteArchivo)
            .options(joinedload(LoteArchivo.contratista), joinedload(LoteArchivo.usuario))
            .order_by(LoteArchivo.fecha_subida.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        lote_ids = [i.id for i in items]
        # Single grouped query: counts per (lote_id, id_estado)
        counts_rows = (
            self.db.query(
                ParteDiarioProcesado.lote_id,
                ParteDiarioProcesado.id_estado,
                func.count(ParteDiarioProcesado.id).label("cnt"),
            )
            .filter(ParteDiarioProcesado.lote_id.in_(lote_ids))
            .group_by(ParteDiarioProcesado.lote_id, ParteDiarioProcesado.id_estado)
            .all()
        )
        # Build {lote_id: {id_estado: cnt}}
        counts: dict[int, dict[int, int]] = defaultdict(dict)
        for lote_id, id_estado, cnt in counts_rows:
            counts[lote_id][id_estado] = cnt

        def _build_response(lote: LoteArchivo) -> LoteResponse:
            c = counts.get(lote.id, {})
            n_aprobados    = c.get(1, 0)
            n_revision     = c.get(2, 0)
            n_rechazado    = c.get(3, 0)
            n_fuera_alcance = c.get(4, 0)
            total_filas    = sum(c.values())
            data = {
                "id": lote.id,
                "nombre_archivo": lote.nombre_archivo,
                "hash_archivo": lote.hash_archivo,
                "contratista_id": lote.contratista_id,
                "contratista_nombre": lote.contratista.nombre if lote.contratista else None,
                "estado": lote.estado,
                "subido_por": lote.subido_por,
                "usuario_nombre": lote.usuario.username if lote.usuario else None,
                "fecha_subida": lote.fecha_subida,
                "detalle_error": lote.detalle_error,
                "paso_actual": lote.paso_actual,
                "progreso_pct": lote.progreso_pct or 0,
                "total_filas": total_filas,
                "n_aprobados": n_aprobados,
                "n_revision": n_revision,
                "n_rechazado": n_rechazado,
                "n_fuera_alcance": n_fuera_alcance,
            }
            return LoteResponse.model_validate(data)

        return LoteListResponse(
            total=total,
            items=[_build_response(i) for i in items],
        )

    def obtener_lote(self, lote_id: int) -> LoteArchivo | None:
        """Obtiene un lote por su ID."""
        return self.db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()

    def crear_lote(
        self,
        nombre_archivo: str,
        contenido_bytes: bytes,
        contratista_id: int,
        subido_por: int,
        force: bool = False,
        mapeo_columnas: str | None = None,
    ) -> LoteArchivo:
        """Crea un nuevo lote aplicando antiduplicidad de tres capas.

        Capa 1 — `hash_archivo` (SHA256 de los bytes). El UNIQUE en DB cierra
                 race conditions: dos POSTs concurrentes con los mismos bytes
                 producen `IntegrityError` en uno de los dos.
        Capa 2 — `hash_contenido` (SHA256 del df_aux normalizado tras parsear
                 con el adapter). Detecta el caso "Excel re-guardado" (bytes
                 distintos pero contenido idéntico).
        Capa 3 — Overlap soft-warning: cuenta cuántas parejas (Suministro, Fecha)
                 del nuevo lote ya existen para el contratista. Si la fracción
                 supera `OVERLAP_WARNING_THRESHOLD`, levanta `OverlapWarning`
                 (HTTP 409 con `requires_force`) salvo que el caller pase
                 `force=True`.

        Excepciones:
            * `ValueError`         — contratista inexistente.
            * `DuplicadoBytesError` — Capa 1.
            * `DuplicadoContenidoError` — Capa 2.
            * `OverlapWarning`      — Capa 3 (sólo si `force=False`).
        """
        contratista = self.db.query(Contratista).filter(Contratista.id == contratista_id).first()
        if not contratista:
            raise ValueError(f"Contratista con id={contratista_id} no existe.")

        # ---------- Capa 1 — bytes ----------
        hash_arch = hash_bytes(contenido_bytes)
        ruta_archivo = self._persistir_binario(hash_arch, nombre_archivo, contenido_bytes)

        lote = LoteArchivo(
            nombre_archivo=nombre_archivo,
            hash_archivo=hash_arch,
            hash_contenido=None,  # Se completa tras Capa 2
            ruta_archivo=str(ruta_archivo),
            contratista_id=contratista_id,
            estado="RECIBIDO",
            subido_por=subido_por,
            paso_actual="RECIBIENDO",
            progreso_pct=0,
            mapeo_columnas=mapeo_columnas,
        )
        self.db.add(lote)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = (
                self.db.query(LoteArchivo)
                .filter(LoteArchivo.hash_archivo == hash_arch)
                .first()
            )
            existente_id = existente.id if existente else 0
            logger.warning(
                "Capa 1 — archivo duplicado por bytes (hash=%s...). Lote existente id=%d",
                hash_arch[:12], existente_id,
            )
            raise DuplicadoBytesError(existente_id)
        self.db.refresh(lote)

        # ---------- Capa 2 — contenido normalizado ----------
        mapeo_dict = None
        if mapeo_columnas:
            import json as _json
            try:
                mapeo_dict = _json.loads(mapeo_columnas)
            except Exception:
                pass
        try:
            df_aux = ejecutar_adapter(Path(ruta_archivo), contratista.nombre, mapeo_columnas=mapeo_dict)
        except Exception as e:
            # Si el adapter explota, dejamos pasar el lote (el worker volverá a
            # intentar y rechazará con detalle_error). Sin contenido parseable
            # no podemos calcular hash_contenido ni overlap.
            logger.warning("Capa 2 — adapter falló parseando %s: %s. Continuando sin hash_contenido.",
                           ruta_archivo, e)
            df_aux = None

        hash_cont: str | None = None
        if df_aux is not None and not df_aux.empty:
            hash_cont = hash_contenido_normalizado(df_aux)
            lote.hash_contenido = hash_cont
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                existente = (
                    self.db.query(LoteArchivo)
                    .filter(LoteArchivo.hash_contenido == hash_cont)
                    .first()
                )
                existente_id = existente.id if existente else 0
                logger.warning(
                    "Capa 2 — contenido duplicado (hash_contenido=%s...). Lote existente id=%d",
                    hash_cont[:12], existente_id,
                )
                self._rollback_lote(lote.id, ruta_archivo)
                raise DuplicadoContenidoError(existente_id)
            self.db.refresh(lote)

        # ---------- Capa 3 — overlap warning ----------
        if not force and df_aux is not None and not df_aux.empty:
            n_existentes, n_total = contar_overlap_business_keys(
                self.db, contratista_id, df_aux
            )
            if n_total > 0 and (n_existentes / n_total) > OVERLAP_WARNING_THRESHOLD:
                overlap_pct = n_existentes / n_total
                logger.info(
                    "Capa 3 — overlap %.0f%% (%d/%d) supera threshold para lote_id=%d, "
                    "se requiere force.",
                    overlap_pct * 100, n_existentes, n_total, lote.id,
                )
                self._rollback_lote(lote.id, ruta_archivo)
                raise OverlapWarning(overlap_pct, n_existentes, n_total)

        logger.info(
            "Lote creado: id=%d, archivo=%s, hash_bytes=%s..., hash_contenido=%s, ruta=%s",
            lote.id, nombre_archivo, hash_arch[:12],
            (hash_cont[:12] + "...") if hash_cont else "<none>",
            ruta_archivo,
        )
        return lote

    def _rollback_lote(self, lote_id: int, ruta_archivo: Path) -> None:
        """Elimina el registro `LoteArchivo` y el binario en disco.

        Llamado cuando una capa rechaza el lote después de que ya se persistió
        parcialmente. El binario solo se borra si no es referenciado por otro
        lote (caso edge: hash colisión imposible vía SHA256, pero defensivo).
        """
        lote = self.db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
        if lote is not None:
            self.db.delete(lote)
            self.db.commit()
        try:
            otros = (
                self.db.query(LoteArchivo)
                .filter(LoteArchivo.ruta_archivo == str(ruta_archivo))
                .count()
            )
            if otros == 0 and Path(ruta_archivo).exists():
                Path(ruta_archivo).unlink()
        except Exception as e:
            logger.warning("No se pudo limpiar binario %s tras rollback: %s", ruta_archivo, e)

    def actualizar_progreso(self, lote_id: int, paso: str, pct: int) -> None:
        """Actualiza `paso_actual` y `progreso_pct` con sesión propia.

        Usado por el worker en cada transición. Sesión propia para no enredar
        la transacción larga del worker (que puede hacer rollback masivo en
        caso de error del motor).
        """
        try:
            with SessionLocal() as session:
                lote = session.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
                if lote is None:
                    return
                lote.paso_actual = paso
                lote.progreso_pct = max(0, min(100, int(pct)))
                session.commit()
        except Exception as e:
            # En SQLite, esto puede fallar por "database is locked" si el worker
            # tiene una transacción abierta con flushes pendientes.
            # No es crítico: preferimos seguir procesando que fallar por un log de progreso.
            logger.warning("No se pudo actualizar progreso del lote %d (%s): %s", lote_id, paso, e)

    def actualizar_estado(self, lote_id: int, nuevo_estado: str, detalle_error: str | None = None) -> LoteArchivo:
        """Actualiza el estado de un lote (usado por el worker de procesamiento)."""
        lote = self.obtener_lote(lote_id)
        if not lote:
            raise ValueError(f"Lote con id={lote_id} no existe.")
        lote.estado = nuevo_estado
        if detalle_error:
            lote.detalle_error = detalle_error
        self.db.commit()
        self.db.refresh(lote)
        return lote

    def get_lote_dashboard(self, lote_id: int):
        """Calcula y devuelve el payload analítico completo de un lote para el dashboard de detalle."""
        from api.db.models.domain_models import ReglaCodEpec
        from api.schemas.lote_schemas import (
            LoteDashboardResponse, TrazaItem, EpecItem, DiscrepanciaItem, OperarioItem,
        )

        lote = self.db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
        if not lote:
            return None

        # 1. Distribución por id_estado
        estado_rows = (
            self.db.query(
                ParteDiarioProcesado.id_estado,
                func.count(ParteDiarioProcesado.id).label("cnt"),
            )
            .filter(ParteDiarioProcesado.lote_id == lote_id)
            .group_by(ParteDiarioProcesado.id_estado)
            .all()
        )
        estado_map = {r.id_estado: r.cnt for r in estado_rows}
        n_aprobados     = estado_map.get(1, 0)
        n_revision      = estado_map.get(2, 0)
        n_rechazado     = estado_map.get(3, 0)
        n_fuera_alcance = estado_map.get(4, 0)
        total           = sum(estado_map.values())
        base_ef         = total - n_fuera_alcance
        efectividad_pct = round(n_aprobados / base_ef * 100, 1) if base_ef > 0 else 0.0

        # 2. Aprobados directos (traza 1) vs. corregidos algorítmicamente
        aprobados_directo = (
            self.db.query(func.count(ParteDiarioProcesado.id))
            .filter(
                ParteDiarioProcesado.lote_id == lote_id,
                ParteDiarioProcesado.id_estado == 1,
                ParteDiarioProcesado.id_traza == 1,
            )
            .scalar() or 0
        )
        aprobados_corregidos = n_aprobados - aprobados_directo

        # 3. Distribución por traza
        traza_rows = (
            self.db.query(
                ParteDiarioProcesado.id_traza,
                ParteDiarioProcesado.id_estado,
                func.count(ParteDiarioProcesado.id).label("cnt"),
            )
            .filter(ParteDiarioProcesado.lote_id == lote_id)
            .group_by(ParteDiarioProcesado.id_traza, ParteDiarioProcesado.id_estado)
            .order_by(func.count(ParteDiarioProcesado.id).desc())
            .all()
        )
        distribucion_trazas = [
            TrazaItem(
                id_traza=r.id_traza,
                desc_traza=_TRAZA_NOMBRES.get(r.id_traza, f"Traza {r.id_traza}"),
                id_estado=r.id_estado,
                desc_estado=_ESTADO_NOMBRES.get(r.id_estado, f"Estado {r.id_estado}"),
                count=r.cnt,
                pct=round(r.cnt / total * 100, 1) if total > 0 else 0.0,
            )
            for r in traza_rows
        ]

        # 4. Distribución por cod_epec (solo aprobados)
        # Prefetch descripciones de reglas activas
        desc_rows = (
            self.db.query(ReglaCodEpec.cod_epec, ReglaCodEpec.descripcion)
            .filter(ReglaCodEpec.activo.is_(True))
            .order_by(ReglaCodEpec.cod_epec, ReglaCodEpec.id)
            .all()
        )
        epec_descs: dict[int, str] = {}
        for dr in desc_rows:
            if dr.cod_epec not in epec_descs:
                epec_descs[dr.cod_epec] = dr.descripcion

        epec_rows = (
            self.db.query(
                ParteDiarioProcesado.cod_epec,
                func.count(ParteDiarioProcesado.id).label("cnt"),
                func.coalesce(func.sum(ParteDiarioProcesado.valor_uses_origen), 0.0).label("total_uses"),
            )
            .filter(
                ParteDiarioProcesado.lote_id == lote_id,
                ParteDiarioProcesado.id_estado == 1,
            )
            .group_by(ParteDiarioProcesado.cod_epec)
            .order_by(func.coalesce(func.sum(ParteDiarioProcesado.valor_uses_origen), 0.0).desc())
            .all()
        )
        total_uses_aprobados = sum(float(r.total_uses or 0.0) for r in epec_rows)
        distribucion_epec = [
            EpecItem(
                cod_epec=r.cod_epec,
                desc_epec=epec_descs.get(r.cod_epec) if r.cod_epec is not None else None,
                count=r.cnt,
                total_uses=round(float(r.total_uses or 0.0), 4),
                pct_partes=round(r.cnt / n_aprobados * 100, 1) if n_aprobados > 0 else 0.0,
            )
            for r in epec_rows
        ]

        # 5. Distribución de discrepancias
        disc_rows = (
            self.db.query(
                ParteDiarioProcesado.tipo_discrepancia,
                func.count(ParteDiarioProcesado.id).label("cnt"),
                func.coalesce(func.sum(ParteDiarioProcesado.diferencia_uses), 0.0).label("delta_uses"),
            )
            .filter(
                ParteDiarioProcesado.lote_id == lote_id,
                ParteDiarioProcesado.tipo_discrepancia.isnot(None),
            )
            .group_by(ParteDiarioProcesado.tipo_discrepancia)
            .all()
        )
        total_controlados = sum(r.cnt for r in disc_rows)
        delta_sobrevaloracion = 0.0
        delta_subvaloracion   = 0.0
        distribucion_discrepancias = []
        for r in disc_rows:
            delta = round(float(r.delta_uses or 0.0), 4)
            distribucion_discrepancias.append(DiscrepanciaItem(
                tipo=r.tipo_discrepancia,
                count=r.cnt,
                pct=round(r.cnt / total_controlados * 100, 1) if total_controlados > 0 else 0.0,
                delta_uses=delta,
            ))
            if r.tipo_discrepancia == "Sobrevaloración":
                delta_sobrevaloracion = delta
            elif r.tipo_discrepancia == "Subvaloración":
                delta_subvaloracion = abs(delta)
        distribucion_discrepancias.sort(key=lambda x: x.count, reverse=True)

        # 6. Distribución por operario
        op_rows = (
            self.db.query(
                ParteDiarioProcesado.operario_excel,
                func.count(ParteDiarioProcesado.id).label("n_total"),
                func.sum(
                    case((ParteDiarioProcesado.id_estado == 1, 1), else_=0)
                ).label("n_aprobados"),
                func.coalesce(
                    func.sum(
                        case(
                            (ParteDiarioProcesado.id_estado == 1, ParteDiarioProcesado.valor_uses_origen),
                            else_=None,
                        )
                    ),
                    0.0,
                ).label("total_uses"),
            )
            .filter(
                ParteDiarioProcesado.lote_id == lote_id,
                ParteDiarioProcesado.operario_excel.isnot(None),
                ParteDiarioProcesado.operario_excel != "",
            )
            .group_by(ParteDiarioProcesado.operario_excel)
            .order_by(func.count(ParteDiarioProcesado.id).desc())
            .all()
        )
        por_operario = [
            OperarioItem(
                operario=r.operario_excel,
                n_total=r.n_total,
                n_aprobados=r.n_aprobados or 0,
                tasa_aprobacion=round((r.n_aprobados or 0) / r.n_total * 100, 1) if r.n_total > 0 else 0.0,
                total_uses=round(float(r.total_uses or 0.0), 4),
            )
            for r in op_rows
        ]

        return LoteDashboardResponse(
            lote_id=lote_id,
            total_registros=total,
            n_aprobados=n_aprobados,
            n_revision=n_revision,
            n_rechazado=n_rechazado,
            n_fuera_alcance=n_fuera_alcance,
            efectividad_pct=efectividad_pct,
            aprobados_directo=aprobados_directo,
            aprobados_corregidos=aprobados_corregidos,
            distribucion_trazas=distribucion_trazas,
            distribucion_epec=distribucion_epec,
            total_uses_aprobados=round(total_uses_aprobados, 4),
            total_controlados=total_controlados,
            distribucion_discrepancias=distribucion_discrepancias,
            delta_uses_sobrevaloracion=delta_sobrevaloracion,
            delta_uses_subvaloracion=delta_subvaloracion,
            por_operario=por_operario,
        )

    @staticmethod
    def _persistir_binario(hash_archivo: str, nombre_original: str, contenido: bytes) -> Path:
        """Guarda el binario en `data/uploads/<sha256><ext>`. Devuelve el path absoluto.

        Naming por hash: idempotente y libre de caracteres problemáticos. La extensión
        viene del archivo original para preservar la semántica al reabrir.
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        extension = Path(nombre_original).suffix or ".xlsx"
        ruta = UPLOADS_DIR / f"{hash_archivo}{extension}"
        # Si ya existe (reintento tras crash entre persistencia y commit), no re-escribir.
        if not ruta.exists():
            ruta.write_bytes(contenido)
        return ruta
