"""Tests del servicio oracle_sync_service con OracleReadOnly mockeado.

Cubre:
  - Sync básico: pobla las 3 tablas locales correctamente.
  - Re-sync: upsert refleja cambios de estado (ord_estado ABIERTO → CERRADO).
  - Oracle vacío: no falla.
  - Error en Q2: rollback completo (no quedan filas parciales).
  - Limpieza de URLs Firebase en fotos.
"""
from __future__ import annotations

from datetime import datetime
from unittest import mock

import pandas as pd
import pytest


# ── Helpers de mocking ───────────────────────────────────────────────────────

class _FakeOracle:
    """Mock de OracleReadOnly que devuelve DataFrames preconstruidos según el SQL."""

    def __init__(self, queries_map: dict[str, pd.DataFrame], raise_on_query: str | None = None):
        # queries_map: dict de prefijo → DataFrame. La primera coincidencia gana.
        self._map = queries_map
        self._raise_on = raise_on_query

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read_sql(self, query: str, params=None, chunksize=None):
        if self._raise_on and self._raise_on in query:
            raise RuntimeError(f"simulated Oracle error on: {self._raise_on}")
        for prefix, df in self._map.items():
            if prefix in query:
                return df.copy()
        # Si no matchea ningún prefijo, devolvemos vacío
        return pd.DataFrame()


def _patch_oracle(monkeypatch, queries_map, raise_on=None):
    fake = _FakeOracle(queries_map, raise_on_query=raise_on)
    monkeypatch.setattr(
        "api.services.oracle_sync_service.OracleReadOnly",
        lambda: fake,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def df_ord_basico():
    return pd.DataFrame([
        {
            "ORD_NUMERO": 900001, "SRV_CODIGO": 104596, "TOR_CODIGO": "CE",
            "SEC_CODIGO_ORIGEN": "PROTELEM",
            "ORD_FECHA_GENERACION": datetime(2025, 10, 6),
            "ORD_FECHA_INICIO":     datetime(2025, 10, 6),
            "ORD_FECHA_FIN":        datetime(2025, 10, 7),
            "ORD_ESTADO": "ABIERTO", "ORD_RESULTADO": "E",
            "USR_NUMERO_EJEC_ORD": 1234, "USR_NOMBRE": "JUAN PEREZ",
        },
        {
            "ORD_NUMERO": 900002, "SRV_CODIGO": 999999, "TOR_CODIGO": "CE",
            "SEC_CODIGO_ORIGEN": "PROTELEM",
            "ORD_FECHA_GENERACION": datetime(2025, 10, 5),
            "ORD_FECHA_INICIO":     datetime(2025, 10, 5),
            "ORD_FECHA_FIN":        None,
            "ORD_ESTADO": "ABIERTO", "ORD_RESULTADO": "E",
            "USR_NUMERO_EJEC_ORD": 5678, "USR_NOMBRE": "MARIA LOPEZ",
        },
    ])


@pytest.fixture
def df_fotos_basico():
    return pd.DataFrame([
        {"ORD_NUMERO": 900001, "TOB_CODIGO": "APP4OBS_80",
         "OBO_INFO_ADICIONAL": "/sd/path/x.jpg-https://firebasestorage.googleapis.com/foto1?alt:media&token:abc"},
        {"ORD_NUMERO": 900001, "TOB_CODIGO": "APP4OBS_81",
         "OBO_INFO_ADICIONAL": "https://firebasestorage.googleapis.com/foto2"},
    ])


@pytest.fixture
def df_eqp_basico():
    return pd.DataFrame([
        {"STE_NUMERO": "70072314", "SRV_CODIGO": "999999", "EQP_FECHA_INSTAL": datetime(2025, 8, 1)},
        {"STE_NUMERO": "7442142",  "SRV_CODIGO": "104596", "EQP_FECHA_INSTAL": datetime(2025, 5, 15)},
    ])


# ── Tests ────────────────────────────────────────────────────────────────────

class TestSincronizar:

    def test_sync_basico_puebla_3_tablas(self, db, monkeypatch, df_ord_basico, df_fotos_basico, df_eqp_basico):
        from api.services.oracle_sync_service import sincronizar_ordenativos_protelem
        from api.db.models.domain_models import (
            OrdenativoOracleEquipo, OrdenativoOracleFoto, OrdenativoOracleLocal,
        )

        _patch_oracle(monkeypatch, {
            "XXSIGEC.ORDENATIVOS":            df_ord_basico,
            "xxco_observaciones_ordenativ_v": df_fotos_basico,
            "XXSIGEC.EQUIPOS":                df_eqp_basico,
        })

        m = sincronizar_ordenativos_protelem(db)
        assert m["errores"] == []
        assert m["ordenativos_upserted"] == 2
        assert m["fotos_upserted"]       == 2
        assert m["equipos_upserted"]     == 2

        # Verificar contenido
        ords = db.query(OrdenativoOracleLocal).all()
        assert {o.ord_numero for o in ords} == {900001, 900002}
        ord1 = db.query(OrdenativoOracleLocal).filter_by(ord_numero=900001).one()
        assert ord1.usr_nombre == "JUAN PEREZ"
        assert ord1.srv_codigo == "104596"
        assert ord1.ord_estado == "ABIERTO"

        # Foto con limpieza de URL Firebase (`:` → `=`)
        foto1 = db.query(OrdenativoOracleFoto).filter_by(ord_numero=900001, posicion=1).one()
        assert foto1.url == "https://firebasestorage.googleapis.com/foto1?alt=media&token=abc"

        # Equipos guardados
        eqps = db.query(OrdenativoOracleEquipo).all()
        assert {(e.ste_numero, e.srv_codigo) for e in eqps} == {
            ("70072314", "999999"), ("7442142", "104596"),
        }

    def test_resync_actualiza_ord_estado(self, db, monkeypatch, df_ord_basico, df_fotos_basico, df_eqp_basico):
        from api.services.oracle_sync_service import sincronizar_ordenativos_protelem
        from api.db.models.domain_models import OrdenativoOracleLocal

        # Primer sync
        _patch_oracle(monkeypatch, {
            "XXSIGEC.ORDENATIVOS":            df_ord_basico,
            "xxco_observaciones_ordenativ_v": df_fotos_basico,
            "XXSIGEC.EQUIPOS":                df_eqp_basico,
        })
        sincronizar_ordenativos_protelem(db)
        ord1 = db.query(OrdenativoOracleLocal).filter_by(ord_numero=900001).one()
        assert ord1.ord_estado == "ABIERTO"

        # Segundo sync con ord_estado cambiado a CERRADO
        df_ord_v2 = df_ord_basico.copy()
        df_ord_v2.loc[df_ord_v2["ORD_NUMERO"] == 900001, "ORD_ESTADO"] = "CERRADO"
        _patch_oracle(monkeypatch, {
            "XXSIGEC.ORDENATIVOS":            df_ord_v2,
            "xxco_observaciones_ordenativ_v": df_fotos_basico,
            "XXSIGEC.EQUIPOS":                df_eqp_basico,
        })
        m = sincronizar_ordenativos_protelem(db)
        assert m["errores"] == []
        # El upsert NO duplica filas
        ords_count = db.query(OrdenativoOracleLocal).count()
        assert ords_count == 2
        # Pero refleja el nuevo estado
        db.expire_all()
        ord1 = db.query(OrdenativoOracleLocal).filter_by(ord_numero=900001).one()
        assert ord1.ord_estado == "CERRADO"

    def test_sync_oracle_vacio_no_falla(self, db, monkeypatch):
        from api.services.oracle_sync_service import sincronizar_ordenativos_protelem
        from api.db.models.domain_models import OrdenativoOracleLocal

        _patch_oracle(monkeypatch, {})  # todas las queries devuelven vacío

        m = sincronizar_ordenativos_protelem(db)
        assert m["errores"] == []
        assert m["ordenativos_upserted"] == 0
        assert db.query(OrdenativoOracleLocal).count() == 0

    def test_error_en_q2_hace_rollback(self, db, monkeypatch, df_ord_basico):
        from api.services.oracle_sync_service import sincronizar_ordenativos_protelem
        from api.db.models.domain_models import OrdenativoOracleLocal

        _patch_oracle(
            monkeypatch,
            {"XXSIGEC.ORDENATIVOS": df_ord_basico},
            raise_on="xxco_observaciones_ordenativ_v",   # falla en Q2
        )

        m = sincronizar_ordenativos_protelem(db)
        assert m["errores"], "Esperaba al menos un error registrado"
        # Rollback: ningún ordenativo debe haber quedado en local
        assert db.query(OrdenativoOracleLocal).count() == 0
