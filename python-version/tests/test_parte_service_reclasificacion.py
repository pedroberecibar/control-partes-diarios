"""Tests de la reclasificación automática tras PATCH de ord_nro.

Cubre el cierre del TODO en parte_service.py L.317-318:
- traza=7 (Sin Orden Asociada) + ord_nro asignado → traza=19, estado=2.
- traza=20 (Múltiples Candidatos Oracle) + ord_nro asignado → traza=19, estado=2.
- Otras trazas → no se tocan id_traza/id_estado.
- Genera entradas en auditoria_cambios con motivo automático.
- No reclasifica si el auditor cambió id_traza/id_estado explícitamente en el mismo PATCH.
"""
from __future__ import annotations

from datetime import datetime
from unittest import mock

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def setup_parte(db):
    """Crea Contratista + UsuarioApp + Lote + Raw + Procesado para tests."""
    from api.db.models.base_models import Contratista, LoteArchivo, UsuarioApp
    from api.db.models.domain_models import ParteDiarioProcesado, ParteDiarioRaw

    contratista = Contratista(id=1, nombre="CONECTAR", activo=True)
    usuario     = UsuarioApp(id=1, username="auditor1", email="a@x.com", rol="auditor")
    db.add_all([contratista, usuario])
    db.flush()

    lote = LoteArchivo(
        id=1, nombre_archivo="t.xlsx", hash_archivo="h" * 64, ruta_archivo="/tmp/t.xlsx",
        contratista_id=1, estado="APROBADO", subido_por=1,
    )
    db.add(lote)
    db.flush()

    raw = ParteDiarioRaw(
        id=1, lote_id=1, fila_excel=1, id_parte_hash="hash-001",
        datos_crudos={"sumi": "104596"},
    )
    db.add(raw)
    db.flush()

    parte = ParteDiarioProcesado(
        id=1, raw_id=1, id_parte_hash="hash-001",
        lote_id=1, contratista_id=1,
        suministro="104596",
        fecha_ejecucion=datetime(2025, 10, 7),
        nro_medidor_retirado="7442142",
        nro_medidor_colocado="70072314",
        ord_nro=None,
        cod_epec=None,
        id_estado=3,   # Rechazado
        id_traza=7,    # Sin Orden Asociada
        version=1,
    )
    db.add(parte)
    db.commit()
    return {"db": db, "parte": parte, "usuario": usuario}


def _payload(version=1, **overrides):
    """Construye un ParteEditRequest válido con motivo y usuario_id."""
    from api.schemas.parte_schemas import ParteEditRequest
    base = {
        "motivo":      "test motivo de cambio",
        "usuario_id":  1,
        "version":     version,
    }
    base.update(overrides)
    return ParteEditRequest(**base)


def _editar(setup_parte, payload):
    """Invoca svc.editar_parte mockeando _to_detalle_dto (necesita dimensiones Parquet)."""
    from api.services.parte_service import ParteService
    svc = ParteService(setup_parte["db"])
    with mock.patch.object(ParteService, "_to_detalle_dto", return_value=None):
        with mock.patch.object(ParteService, "_poblar_obs_desde_pivot", return_value=None):
            return svc.editar_parte(setup_parte["parte"].id, payload)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestReclasificacionTraza7:

    def test_asignar_ord_nro_sobre_traza_7_reclasifica(self, setup_parte):
        from api.db.models.domain_models import AuditoriaCambio, ParteDiarioProcesado

        _editar(setup_parte, _payload(ord_nro=900001))

        parte = setup_parte["db"].query(ParteDiarioProcesado).filter_by(id=1).one()
        assert parte.ord_nro   == 900001
        assert parte.id_traza  == 19  # Rescatado por Oracle
        assert parte.id_estado == 2   # Revisión
        assert parte.fue_corregido is True

        # Verificar entradas de auditoría
        cambios = setup_parte["db"].query(AuditoriaCambio).filter_by(parte_procesado_id=1).all()
        campos = {c.campo_modificado for c in cambios}
        assert "ord_nro" in campos
        assert "id_traza" in campos
        assert "id_estado" in campos

        # La entrada de id_traza debe tener el motivo automático
        cambio_traza = next(c for c in cambios if c.campo_modificado == "id_traza")
        assert "Auto-reclasificación" in cambio_traza.motivo
        assert cambio_traza.valor_anterior == "7"
        assert cambio_traza.valor_nuevo == "19"


class TestReclasificacionTraza20:

    def test_asignar_ord_nro_sobre_traza_20_reclasifica(self, setup_parte):
        from api.db.models.domain_models import ParteDiarioProcesado

        # Cambiamos el parte a traza=20 (Múltiples Candidatos Oracle), estado=2
        parte = setup_parte["parte"]
        parte.id_traza  = 20
        parte.id_estado = 2
        setup_parte["db"].commit()

        _editar(setup_parte, _payload(ord_nro=900003))

        parte = setup_parte["db"].query(ParteDiarioProcesado).filter_by(id=1).one()
        assert parte.ord_nro   == 900003
        assert parte.id_traza  == 19
        assert parte.id_estado == 2  # ya estaba en 2, sigue en 2


class TestNoReclasificaTrazaQueNoEs7Ni20:

    def test_traza_1_no_se_reclasifica(self, setup_parte):
        from api.db.models.domain_models import ParteDiarioProcesado

        # Cambiamos el parte a traza=1 (Original OK) — el auditor solo está editando ord_nro
        parte = setup_parte["parte"]
        parte.id_traza  = 1
        parte.id_estado = 1
        setup_parte["db"].commit()

        _editar(setup_parte, _payload(ord_nro=555))

        parte = setup_parte["db"].query(ParteDiarioProcesado).filter_by(id=1).one()
        assert parte.ord_nro   == 555
        assert parte.id_traza  == 1   # SIN cambio
        assert parte.id_estado == 1   # SIN cambio


class TestRespetaCambioExplicitoDeAuditor:

    def test_si_payload_incluye_id_traza_no_aplica_auto(self, setup_parte):
        """Si el auditor cambia id_traza explícitamente, gana ese valor (no 19)."""
        from api.db.models.domain_models import ParteDiarioProcesado

        _editar(setup_parte, _payload(ord_nro=900001, id_traza=11))

        parte = setup_parte["db"].query(ParteDiarioProcesado).filter_by(id=1).one()
        assert parte.ord_nro  == 900001
        assert parte.id_traza == 11  # respeta lo que dijo el auditor


class TestSinOrdNroNoReclasifica:

    def test_editar_solo_suministro_no_reclasifica(self, setup_parte):
        """Si no se cambia ord_nro, traza=7 sigue intacto."""
        from api.db.models.domain_models import ParteDiarioProcesado

        _editar(setup_parte, _payload(suministro="999999"))

        parte = setup_parte["db"].query(ParteDiarioProcesado).filter_by(id=1).one()
        assert parte.suministro == "999999"
        assert parte.id_traza   == 7   # SIN cambio
        assert parte.id_estado  == 3   # SIN cambio
