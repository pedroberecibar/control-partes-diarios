"""Tests de rescate_ordenativos_service contra DB local poblada por fixtures.

Cubre:
  - buscar_candidatos_local: política de búsqueda A (suministro), B (medidor → suministro real).
  - rescatar_huerfanos_lote: clasificación 1/N/0 candidatos según tolerancia.
  - Edge cases: DB sin sync, dedup A+B, fechas lejanas, suministro vs medidor.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest


# ── Fixtures de datos ────────────────────────────────────────────────────────

@pytest.fixture
def fecha_parte():
    return datetime(2025, 10, 7)


@pytest.fixture
def db_con_sync(db, fecha_parte):
    """DB local con datos de prueba: 1 ordenativo CE para suministro 104596."""
    from api.db.models.domain_models import (
        OrdenativoOracleEquipo,
        OrdenativoOracleFoto,
        OrdenativoOracleLocal,
    )

    # Ordenativo CE con fecha 1 día antes del parte (debe ser candidato cercano)
    db.add(OrdenativoOracleLocal(
        ord_numero=900001,
        srv_codigo="104596",
        tor_codigo="CE",
        sec_codigo_origen="PROTELEM",
        ord_fecha_inicio=fecha_parte - timedelta(days=1),
        ord_fecha_fin=fecha_parte,
        ord_estado="CERRADO",
        usr_nombre="JUAN PEREZ",
    ))
    # Otro ordenativo CE para el mismo suministro pero a 30 días (NO debe ser cercano)
    db.add(OrdenativoOracleLocal(
        ord_numero=900002,
        srv_codigo="104596",
        tor_codigo="CE",
        sec_codigo_origen="PROTELEM",
        ord_fecha_inicio=fecha_parte - timedelta(days=30),
        ord_estado="CERRADO",
    ))
    # Ordenativo CE para OTRO suministro (encontrable por medidor)
    db.add(OrdenativoOracleLocal(
        ord_numero=900003,
        srv_codigo="999999",
        tor_codigo="CE",
        sec_codigo_origen="PROTELEM",
        ord_fecha_inicio=fecha_parte - timedelta(days=2),
        ord_estado="ABIERTO",
    ))
    # Equipo: medidor 70072314 → suministro 999999
    db.add(OrdenativoOracleEquipo(
        ste_numero="70072314",
        srv_codigo="999999",
        eqp_fecha_instal=fecha_parte - timedelta(days=60),
    ))
    # Foto del primer ordenativo
    db.add(OrdenativoOracleFoto(
        ord_numero=900001, posicion=1,
        url="https://firebasestorage.googleapis.com/v0/foto1.jpg",
    ))
    db.commit()
    return db


# ── Tests buscar_candidatos_local ────────────────────────────────────────────

class TestBuscarCandidatosLocal:

    def test_db_sin_sync_devuelve_aviso(self, db, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        res = buscar_candidatos_local(db, "104596", None, None, fecha_parte)
        assert res["candidatos"] == []
        assert res["aviso"] is not None
        assert "sincronizada" in res["aviso"].lower()

    def test_search_a_por_suministro(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        res = buscar_candidatos_local(db_con_sync, "104596", None, None, fecha_parte)
        # Encuentra los 2 ordenativos del suministro 104596
        ord_nums = sorted(c["ord_numero"] for c in res["candidatos"])
        assert ord_nums == [900001, 900002]
        # El más cercano (1 día) primero
        assert res["candidatos"][0]["ord_numero"] == 900001
        assert res["candidatos"][0]["dias_diferencia"] == 1
        # Origenes correctos
        assert "A" in res["candidatos"][0]["origenes"]

    def test_search_b_por_medidor_colocado(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        # Sin suministro, solo medidor → encuentra el ord 900003 vía equipo
        res = buscar_candidatos_local(db_con_sync, None, "70072314", None, fecha_parte)
        assert len(res["candidatos"]) == 1
        assert res["candidatos"][0]["ord_numero"] == 900003
        assert "B_colocado" in res["candidatos"][0]["origenes"]

    def test_dedup_entre_a_y_b(self, db_con_sync, fecha_parte):
        """Si suministro coincide y el medidor también lleva al mismo SRV, dedup por ord_numero."""
        from api.db.models.domain_models import OrdenativoOracleEquipo
        # Agregamos un equipo: medidor 12345 → suministro 104596 (mismo del search A)
        db_con_sync.add(OrdenativoOracleEquipo(ste_numero="12345", srv_codigo="104596"))
        db_con_sync.commit()
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        res = buscar_candidatos_local(db_con_sync, "104596", "12345", None, fecha_parte)
        # No debe duplicar 900001 ni 900002
        ord_nums = sorted(c["ord_numero"] for c in res["candidatos"])
        assert ord_nums == [900001, 900002]
        # El primer candidato debe tener AMBOS origenes
        cand_900001 = next(c for c in res["candidatos"] if c["ord_numero"] == 900001)
        assert set(cand_900001["origenes"]) == {"A", "B_colocado"}

    def test_fotos_se_cargan(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        res = buscar_candidatos_local(db_con_sync, "104596", None, None, fecha_parte)
        cand = next(c for c in res["candidatos"] if c["ord_numero"] == 900001)
        assert cand["fotos"]["imagen_1"] == "https://firebasestorage.googleapis.com/v0/foto1.jpg"
        assert cand["fotos"]["imagen_2"] is None

    def test_sin_match(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        res = buscar_candidatos_local(db_con_sync, "777777", None, None, fecha_parte)
        assert res["candidatos"] == []
        assert res["aviso"] is None

    def test_med_retirado_distinto_del_colocado_no_duplica_busqueda(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import buscar_candidatos_local
        # mismo medidor en ambos lados → solo se busca una vez
        res = buscar_candidatos_local(db_con_sync, None, "70072314", "70072314", fecha_parte)
        assert len(res["candidatos"]) == 1
        assert res["candidatos"][0]["origenes"] == ["B_colocado"]


# ── Tests rescatar_huerfanos_lote (política de clasificación) ────────────────

class TestRescatarHuerfanosLote:

    def test_lote_vacio(self, db_con_sync):
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        assert rescatar_huerfanos_lote(db_con_sync, [], dias_tolerancia=7) == {}

    def test_un_candidato_cercano_se_clasifica_como_rescate_unico(self, db_con_sync, fecha_parte):
        """Cuando el ordenativo lejano (30d) está fuera de tolerancia, queda 1 solo dentro → rescate único."""
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        huerfanos = [{
            "id_parte_hash":    "hash-001",
            "suministro":       "104596",
            "medidor_colocado": None,
            "medidor_retirado": None,
            "fecha_ref":        fecha_parte,
        }]
        out = rescatar_huerfanos_lote(db_con_sync, huerfanos, dias_tolerancia=7)
        assert out["hash-001"]["clasificacion"] == "rescate_unico"
        assert out["hash-001"]["ord_nro_asignado"] == 900001

    def test_n_candidatos_cercanos_se_clasifica_como_ambiguo(self, db_con_sync, fecha_parte):
        """Si la tolerancia incluye los 2 ordenativos del mismo suministro → ambiguo."""
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        huerfanos = [{
            "id_parte_hash":    "hash-001",
            "suministro":       "104596",
            "medidor_colocado": None,
            "medidor_retirado": None,
            "fecha_ref":        fecha_parte,
        }]
        out = rescatar_huerfanos_lote(db_con_sync, huerfanos, dias_tolerancia=60)
        assert out["hash-001"]["clasificacion"] == "ambiguo_multiple"
        assert out["hash-001"]["ord_nro_asignado"] is None

    def test_sin_candidatos_se_clasifica_como_sin_match(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        huerfanos = [{
            "id_parte_hash":    "hash-001",
            "suministro":       "777777",
            "medidor_colocado": None,
            "medidor_retirado": None,
            "fecha_ref":        fecha_parte,
        }]
        out = rescatar_huerfanos_lote(db_con_sync, huerfanos, dias_tolerancia=7)
        assert out["hash-001"]["clasificacion"] == "sin_match"
        assert out["hash-001"]["ord_nro_asignado"] is None

    def test_db_sin_sync_devuelve_dict_vacio(self, db, fecha_parte):
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        huerfanos = [{
            "id_parte_hash":    "h1",
            "suministro":       "104596",
            "medidor_colocado": None,
            "medidor_retirado": None,
            "fecha_ref":        fecha_parte,
        }]
        # DB nunca sincronizada → skip silencioso
        assert rescatar_huerfanos_lote(db, huerfanos, dias_tolerancia=7) == {}

    def test_mix_de_clasificaciones(self, db_con_sync, fecha_parte):
        from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
        huerfanos = [
            {"id_parte_hash": "h_unico",   "suministro": "104596", "medidor_colocado": None, "medidor_retirado": None, "fecha_ref": fecha_parte},
            {"id_parte_hash": "h_sin",     "suministro": "777777", "medidor_colocado": None, "medidor_retirado": None, "fecha_ref": fecha_parte},
            {"id_parte_hash": "h_med",     "suministro": None,     "medidor_colocado": "70072314", "medidor_retirado": None, "fecha_ref": fecha_parte},
        ]
        out = rescatar_huerfanos_lote(db_con_sync, huerfanos, dias_tolerancia=7)
        assert out["h_unico"]["clasificacion"] == "rescate_unico"
        assert out["h_unico"]["ord_nro_asignado"] == 900001
        assert out["h_sin"]["clasificacion"] == "sin_match"
        assert out["h_med"]["clasificacion"] == "rescate_unico"
        assert out["h_med"]["ord_nro_asignado"] == 900003
