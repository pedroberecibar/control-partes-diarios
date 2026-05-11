"""Servicio de sugerencias de cod_epec para single-parte (auditoría).

Calcula la distancia Hamming entre las 8 obs cargadas por el operario y las
reglas activas. Devuelve match exacto + top 3 cercanos + lista plana de todas
las reglas (para que el dropdown del UI calcule el preview de Hamming sin un
segundo round-trip).

Comparte el helper `src.hamming` con `etapa4_control_obs._calcular_hamming_global`
para evitar drift numérico entre el motor batch y la API.
"""
from __future__ import annotations

import logging

import numpy as np
from sqlalchemy.orm import Session

from api.db.models.domain_models import ParteDiarioProcesado
from api.schemas.sugerencias_schemas import (
    CandidatoEpecDTO,
    CandidatosEpecResponse,
)
from api.services.reglas_service import _OBS_FIELDS, ReglaService
from src import config
from src import hamming as hamming_helper

log = logging.getLogger("api.services.sugerencias")


class SugerenciasService:
    """Sugiere cod_epec candidatos por similitud de observaciones."""

    def __init__(self, db: Session):
        self.db = db
        self._regla_service = ReglaService(db)

    def candidatos_para_parte(self, parte_id: int) -> CandidatosEpecResponse:
        parte = self.db.get(ParteDiarioProcesado, parte_id)
        if parte is None:
            raise ValueError(f"Parte id={parte_id} no existe.")
        if parte.id_estado != 1:
            raise ValueError("Sugerencias disponibles solo para partes Aprobados.")

        # Vector 1×8 de obs del operario en orden config.OBS_COLS.
        # Usamos _OBS_FIELDS (orm_field, col_reglas) porque el lower-case
        # del nombre canónico no coincide con el ORM en EQUIPO_DE_MEDICION_INSTALADO.
        obs_vec = np.array(
            [int(getattr(parte, f"obs_{orm_field}", False)) for orm_field, _ in _OBS_FIELDS],
            dtype="int8",
        )

        df_reglas = self._regla_service.cargar_reglas_como_dataframe()
        cols_obs = [cr for _, cr in config.OBS_COLS]
        regla_mat = df_reglas[cols_obs].fillna(0).to_numpy(dtype="int8")

        dists = hamming_helper.hamming_matrix(obs_vec[None, :], regla_mat)[0]   # shape (M,)
        sin_obs = bool(obs_vec.sum() == 0)

        todas: list[CandidatoEpecDTO] = [
            CandidatoEpecDTO(
                cod_epec=int(row.COD_EPEC),
                descripcion=str(row.DESCRIPCION),
                hamming=int(dists[i]),
                score=8 - int(dists[i]),
                valor_uses=float(row.VALOR_USES),
                campos_diferentes=hamming_helper.campos_diferentes(obs_vec, regla_mat[i]),
            )
            for i, row in enumerate(df_reglas.itertuples(index=False))
        ]

        match_exacto = [c for c in todas if c.hamming == 0]
        cercanos = sorted(
            (c for c in todas if c.hamming > 0),
            key=lambda c: (c.hamming, -c.valor_uses, c.cod_epec),
        )[:3]

        # Caso "sin obs": etapa4 asigna cod 11 con USES=0.0100. Replicamos la
        # convención priorizando esa regla en match_exacto.
        if sin_obs:
            cod_11 = [c for c in todas if c.cod_epec == 11]
            if cod_11:
                match_exacto = cod_11

        obs_parte = [cr for i, (_, cr) in enumerate(config.OBS_COLS) if obs_vec[i] == 1]

        return CandidatosEpecResponse(
            parte_id=parte_id,
            sin_observaciones=sin_obs,
            obs_parte=obs_parte,
            match_exacto=match_exacto,
            cercanos=cercanos,
            todas=todas,
        )
