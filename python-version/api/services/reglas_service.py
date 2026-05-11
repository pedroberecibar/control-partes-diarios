"""
Servicio de administración de reglas de códigos EPEC.

Fuente de verdad: tablas ORM `reglas_cod_epec` y `mapeo_codigos_contratista`.
Expone CRUD + exportación a DataFrame (formato que consume Etapa 4).
"""
from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.orm import Session

from api.db.models.base_models import Contratista
from api.db.models.domain_models import MapeoCodigoContratista, ReglaCodEpec
from api.schemas.admin_schemas import (
    MapeoCodigoContratistaCreate,
    MapeoCodigoContratistaUpdate,
    ReglaCodEpecCreate,
    ReglaCodEpecUpdate,
)
from src import config, io_lakehouse as io

log = logging.getLogger("api.services.reglas")

# Orden canónico de obs columns — debe coincidir con config.OBS_COLS.
_OBS_FIELDS: list[tuple[str, str]] = [
    ("gabinete",                    "GABINETE"),
    ("subterraneo",                 "SUBTERRANEO"),
    ("altura",                      "ALTURA"),
    ("aereo",                       "AEREO"),
    ("equipo_medicion_reemplazado", "EQUIPO_MEDICION_REEMPLAZADO"),
    ("acometida_realizada",         "ACOMETIDA_REALIZADA"),
    ("tapa_reemplazada",            "TAPA_REEMPLAZADA"),
    ("equipo_medicion_instalado",   "EQUIPO_DE_MEDICION_INSTALADO"),
]


class ReglaService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Listado de reglas con mapeos adjuntos
    # ------------------------------------------------------------------

    def listar_reglas(self, solo_activas: bool = False) -> list[ReglaCodEpec]:
        q = self.db.query(ReglaCodEpec)
        if solo_activas:
            q = q.filter(ReglaCodEpec.activo == True)
        reglas = q.order_by(ReglaCodEpec.cod_epec, ReglaCodEpec.descripcion).all()
        return reglas

    def obtener_regla(self, regla_id: int) -> ReglaCodEpec | None:
        return self.db.query(ReglaCodEpec).filter(ReglaCodEpec.id == regla_id).first()

    def mapeos_por_cod_epec(self, cod_epec: int) -> list[MapeoCodigoContratista]:
        return (
            self.db.query(MapeoCodigoContratista)
            .filter(MapeoCodigoContratista.cod_epec == cod_epec,
                    MapeoCodigoContratista.activo == True)
            .all()
        )

    def mapeos_agrupados(self) -> dict[int, list[MapeoCodigoContratista]]:
        """Devuelve {cod_epec: [mapeos]} para todos los codigos activos."""
        mapeos = (
            self.db.query(MapeoCodigoContratista)
            .filter(MapeoCodigoContratista.activo == True)
            .all()
        )
        result: dict[int, list] = {}
        for m in mapeos:
            result.setdefault(m.cod_epec, []).append(m)
        return result

    def mapeo_codigos_epec_por_contratista(self) -> dict[str, set[int]]:
        """Devuelve {contratista.nombre.upper(): {cod_epec, ...}} para mapeos activos.

        Dict vacío si no hay mapeos configurados (el motor interpretará: sin restricción).
        """
        rows = (
            self.db.query(MapeoCodigoContratista.cod_epec, Contratista.nombre)
            .join(Contratista, MapeoCodigoContratista.contratista_id == Contratista.id)
            .filter(MapeoCodigoContratista.activo == True)
            .all()
        )
        result: dict[str, set[int]] = {}
        for cod_epec, nombre in rows:
            result.setdefault(nombre.upper(), set()).add(int(cod_epec))
        return result

    # ------------------------------------------------------------------
    # CRUD Reglas
    # ------------------------------------------------------------------

    def crear_regla(self, payload: ReglaCodEpecCreate) -> ReglaCodEpec:
        self._validar_descripcion_unica(payload.cod_epec, payload.descripcion)
        self._advertir_valor_uses(payload.cod_epec, payload.valor_uses)
        regla = ReglaCodEpec(**payload.model_dump())
        self.db.add(regla)
        self.db.commit()
        self.db.refresh(regla)
        log.info("Regla creada: cod_epec=%d, desc=%s", regla.cod_epec, regla.descripcion)
        return regla

    def actualizar_regla(self, regla_id: int, payload: ReglaCodEpecUpdate) -> ReglaCodEpec:
        regla = self.obtener_regla(regla_id)
        if regla is None:
            raise ValueError(f"Regla id={regla_id} no existe.")

        cambios = payload.model_dump(exclude_none=True)
        if "descripcion" in cambios and cambios["descripcion"] != regla.descripcion:
            self._validar_descripcion_unica(regla.cod_epec, cambios["descripcion"], excluir_id=regla_id)
        if "valor_uses" in cambios:
            self._advertir_valor_uses(regla.cod_epec, cambios["valor_uses"], excluir_id=regla_id)

        for campo, valor in cambios.items():
            setattr(regla, campo, valor)

        self.db.commit()
        self.db.refresh(regla)
        log.info("Regla id=%d actualizada: %s", regla_id, list(cambios.keys()))
        return regla

    def desactivar_regla(self, regla_id: int) -> ReglaCodEpec:
        regla = self.obtener_regla(regla_id)
        if regla is None:
            raise ValueError(f"Regla id={regla_id} no existe.")
        regla.activo = False
        self.db.commit()
        self.db.refresh(regla)
        log.info("Regla id=%d desactivada.", regla_id)
        return regla

    # ------------------------------------------------------------------
    # CRUD Mapeos
    # ------------------------------------------------------------------

    def listar_mapeos(self, solo_activos: bool = False) -> list[MapeoCodigoContratista]:
        q = self.db.query(MapeoCodigoContratista)
        if solo_activos:
            q = q.filter(MapeoCodigoContratista.activo == True)
        return q.order_by(MapeoCodigoContratista.cod_epec, MapeoCodigoContratista.cod_contratista).all()

    def crear_mapeo(self, payload: MapeoCodigoContratistaCreate) -> MapeoCodigoContratista:
        mapeo = MapeoCodigoContratista(**payload.model_dump())
        self.db.add(mapeo)
        self.db.commit()
        self.db.refresh(mapeo)
        return mapeo

    def actualizar_mapeo(self, mapeo_id: int, payload: MapeoCodigoContratistaUpdate) -> MapeoCodigoContratista:
        mapeo = self.db.query(MapeoCodigoContratista).filter(MapeoCodigoContratista.id == mapeo_id).first()
        if mapeo is None:
            raise ValueError(f"Mapeo id={mapeo_id} no existe.")
        for campo, valor in payload.model_dump(exclude_none=True).items():
            setattr(mapeo, campo, valor)
        self.db.commit()
        self.db.refresh(mapeo)
        return mapeo

    def desactivar_mapeo(self, mapeo_id: int) -> MapeoCodigoContratista:
        mapeo = self.db.query(MapeoCodigoContratista).filter(MapeoCodigoContratista.id == mapeo_id).first()
        if mapeo is None:
            raise ValueError(f"Mapeo id={mapeo_id} no existe.")
        mapeo.activo = False
        self.db.commit()
        self.db.refresh(mapeo)
        return mapeo

    # ------------------------------------------------------------------
    # Exportación a DataFrame — formato exacto que espera Etapa 4
    # ------------------------------------------------------------------

    def cargar_reglas_como_dataframe(self) -> pd.DataFrame:
        """Exporta reglas activas al formato esperado por etapa4_control_obs.

        El orden de columnas de observación DEBE coincidir con config.OBS_COLS.
        """
        reglas = self.listar_reglas(solo_activas=True)
        if not reglas:
            log.warning("cargar_reglas_como_dataframe — tabla vacía, usando fallback Parquet.")
            return io.read_table("reglas_cod_obs_app", capa="master")

        rows = []
        for r in reglas:
            row = {
                "COD_EPEC":    r.cod_epec,
                "DESCRIPCION": r.descripcion,
                "VALOR_USES":  r.valor_uses,
            }
            for orm_field, col_name in _OBS_FIELDS:
                row[col_name] = int(getattr(r, orm_field))
            rows.append(row)

        col_order = (
            ["COD_EPEC", "DESCRIPCION"]
            + [col for _, col in _OBS_FIELDS]
            + ["VALOR_USES"]
        )
        return pd.DataFrame(rows, columns=col_order)

    # ------------------------------------------------------------------
    # Seed inicial desde literales y Parquet
    # ------------------------------------------------------------------

    def seed_desde_literals(self) -> dict[str, int]:
        """Pobla las tablas ORM si están vacías.

        - Reglas: desde los literales hardcodeados en etapa1_maestros.
        - Mapeos: desde master/mapeo_codigos_master.parquet.

        Es idempotente: no toca la DB si ya tiene datos.
        """
        n_reglas = self._seed_reglas()
        n_mapeos = self._seed_mapeos()
        return {"reglas": n_reglas, "mapeos": n_mapeos}

    def _seed_reglas(self) -> int:
        if self.db.query(ReglaCodEpec).count() > 0:
            log.info("seed_reglas — tabla ya tiene datos, saltando.")
            return 0

        from src.etapa1_maestros import _COLS_REGLAS, _DATOS_REGLAS

        n = 0
        for fila in _DATOS_REGLAS:
            d = dict(zip(_COLS_REGLAS, fila))
            self.db.add(ReglaCodEpec(
                cod_epec=int(d["COD_EPEC"]),
                descripcion=str(d["DESCRIPCION"]),
                gabinete=bool(d["GABINETE"]),
                subterraneo=bool(d["SUBTERRANEO"]),
                altura=bool(d["ALTURA"]),
                aereo=bool(d["AEREO"]),
                equipo_medicion_reemplazado=bool(d["EQUIPO_MEDICION_REEMPLAZADO"]),
                acometida_realizada=bool(d["ACOMETIDA_REALIZADA"]),
                tapa_reemplazada=bool(d["TAPA_REEMPLAZADA"]),
                equipo_medicion_instalado=bool(d["EQUIPO_DE_MEDICION_INSTALADO"]),
                valor_uses=float(d["VALOR_USES"]),
            ))
            n += 1

        self.db.commit()
        log.info("seed_reglas — %d reglas insertadas.", n)
        return n

    def _seed_mapeos(self) -> int:
        if self.db.query(MapeoCodigoContratista).count() > 0:
            log.info("seed_mapeos — tabla ya tiene datos, saltando.")
            return 0

        if not io.table_exists("mapeo_codigos_master", capa="master"):
            log.warning("seed_mapeos — Parquet no existe; corré primero etapa1_maestros.")
            return 0

        df = io.read_table("mapeo_codigos_master", capa="master")

        # Mapa nombre_contratista → id
        contratistas = {c.nombre.upper(): c.id for c in self.db.query(Contratista).all()}

        n = 0
        for _, row in df.iterrows():
            nombre = str(row.get("CONTRATISTA", "")).upper()
            cid = contratistas.get(nombre)
            if cid is None:
                log.warning("seed_mapeos — contratista '%s' no encontrado en DB, fila saltada.", nombre)
                continue

            cod_epec_raw = row.get("COD_EPEC")
            try:
                cod_epec = int(cod_epec_raw)
            except (TypeError, ValueError):
                continue

            self.db.add(MapeoCodigoContratista(
                contratista_id=cid,
                cod_contratista=str(row.get("COD_CONTRATISTA_INDIVIDUAL", "")).strip(),
                fase=str(row.get("FASE", "")).strip(),
                cod_epec=cod_epec,
                descripcion_codigo=str(row.get("DESCRIPCION_CODIGO", "")) or None,
            ))
            n += 1

        self.db.commit()
        log.info("seed_mapeos — %d mapeos insertados.", n)
        return n

    # ------------------------------------------------------------------
    # Validaciones privadas
    # ------------------------------------------------------------------

    def _validar_descripcion_unica(
        self, cod_epec: int, descripcion: str, excluir_id: int | None = None
    ) -> None:
        q = (
            self.db.query(ReglaCodEpec)
            .filter(ReglaCodEpec.cod_epec == cod_epec,
                    ReglaCodEpec.descripcion == descripcion,
                    ReglaCodEpec.activo == True)
        )
        if excluir_id is not None:
            q = q.filter(ReglaCodEpec.id != excluir_id)
        if q.first() is not None:
            raise ValueError(
                f"Ya existe una regla activa para cod_epec={cod_epec} "
                f"con descripción '{descripcion}'."
            )

    def _advertir_valor_uses(
        self, cod_epec: int, valor_uses: float, excluir_id: int | None = None
    ) -> None:
        """Loguea warning si el VALOR_USES difiere de otras variantes del mismo código."""
        q = (
            self.db.query(ReglaCodEpec.valor_uses)
            .filter(ReglaCodEpec.cod_epec == cod_epec,
                    ReglaCodEpec.activo == True)
        )
        if excluir_id is not None:
            q = q.filter(ReglaCodEpec.id != excluir_id)
        valores_existentes = {row[0] for row in q.all()}
        if valores_existentes and valor_uses not in valores_existentes:
            log.warning(
                "ADVERTENCIA: cod_epec=%d ya tiene variantes con VALOR_USES=%s. "
                "El nuevo valor %.4f diverge — Etapa 4 usará drop_duplicates() "
                "y tomará solo uno por código.",
                cod_epec, valores_existentes, valor_uses,
            )
