"""Tests del SugerenciasService — distancia Hamming entre obs operario y reglas."""
from __future__ import annotations

from datetime import datetime

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def seed_basico(db):
    """Crea contratista + lote + raw + reglas EPEC mínimas para tests."""
    from api.db.models.base_models import Contratista, LoteArchivo, UsuarioApp
    from api.db.models.domain_models import ParteDiarioRaw, ReglaCodEpec

    contratista = Contratista(id=1, nombre="CONECTAR", activo=True)
    usuario = UsuarioApp(id=1, username="auditor1", email="a@x.com", rol="auditor")
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

    # Reglas representativas: cod 7 (gabinete), cod 11 (sin obs / fallback),
    # cod 14 (gabinete + altura), cod 20 (aereo + tapa).
    reglas = [
        ReglaCodEpec(cod_epec=7,  descripcion="Gabinete simple",
                     gabinete=True, valor_uses=2.5, activo=True),
        ReglaCodEpec(cod_epec=7,  descripcion="Gabinete con altura",
                     gabinete=True, altura=True, valor_uses=2.5, activo=True),
        ReglaCodEpec(cod_epec=11, descripcion="Sin obs",
                     valor_uses=0.01, activo=True),
        ReglaCodEpec(cod_epec=14, descripcion="Gabinete + Altura",
                     gabinete=True, altura=True, valor_uses=3.0, activo=True),
        ReglaCodEpec(cod_epec=20, descripcion="Aereo + Tapa",
                     aereo=True, tapa_reemplazada=True, valor_uses=4.0, activo=True),
    ]
    db.add_all(reglas)
    db.commit()
    return db


def _crear_parte(db, *, parte_id=10, id_estado=1, **obs):
    from api.db.models.domain_models import ParteDiarioProcesado
    parte = ParteDiarioProcesado(
        id=parte_id, raw_id=1, id_parte_hash=f"hash-{parte_id:03d}",
        lote_id=1, contratista_id=1,
        suministro="104596",
        fecha_ejecucion=datetime(2025, 10, 7),
        cod_epec=None,
        id_estado=id_estado,
        id_traza=1,
        version=1,
        obs_gabinete=obs.get("gabinete", False),
        obs_subterraneo=obs.get("subterraneo", False),
        obs_altura=obs.get("altura", False),
        obs_aereo=obs.get("aereo", False),
        obs_equipo_medicion_reemplazado=obs.get("equipo_medicion_reemplazado", False),
        obs_acometida_realizada=obs.get("acometida_realizada", False),
        obs_tapa_reemplazada=obs.get("tapa_reemplazada", False),
        obs_equipo_medicion_instalado=obs.get("equipo_medicion_instalado", False),
    )
    db.add(parte)
    db.commit()
    return parte


# ── Tests ─────────────────────────────────────────────────────────────────

def test_match_exacto_unico(seed_basico):
    """Parte con sólo gabinete=True → match exacto con cod 7 'Gabinete simple'."""
    from api.services.sugerencias_service import SugerenciasService

    _crear_parte(seed_basico, parte_id=10, gabinete=True)
    out = SugerenciasService(seed_basico).candidatos_para_parte(10)

    assert out.parte_id == 10
    assert out.sin_observaciones is False
    assert out.obs_parte == ["GABINETE"]
    assert len(out.match_exacto) == 1
    assert out.match_exacto[0].cod_epec == 7
    assert out.match_exacto[0].descripcion == "Gabinete simple"
    assert out.match_exacto[0].hamming == 0
    assert out.match_exacto[0].score == 8
    # Cercanos: top 3 con hamming>0, el resto descartado.
    assert len(out.cercanos) == 3
    for c in out.cercanos:
        assert c.hamming > 0


def test_sin_observaciones_devuelve_cod_11(seed_basico):
    """Parte con todas las obs en False → match_exacto contiene cod 11."""
    from api.services.sugerencias_service import SugerenciasService

    _crear_parte(seed_basico, parte_id=11)   # todas las obs por default = False
    out = SugerenciasService(seed_basico).candidatos_para_parte(11)

    assert out.sin_observaciones is True
    assert out.obs_parte == []
    assert len(out.match_exacto) == 1
    assert out.match_exacto[0].cod_epec == 11
    # cod 11 tiene hamming=0 (también es match exacto numérico).
    assert out.match_exacto[0].hamming == 0


def test_top_3_cercanos_ordenados_por_hamming_asc(seed_basico):
    """Empate por hamming → desempata por valor_uses desc."""
    from api.services.sugerencias_service import SugerenciasService

    # gabinete + altura → match exacto cod 14 (USES 3.0) y cod 7 'Gabinete con altura' (USES 2.5).
    # Cercanos por hamming asc.
    _crear_parte(seed_basico, parte_id=12, gabinete=True, altura=True)
    out = SugerenciasService(seed_basico).candidatos_para_parte(12)

    assert {c.cod_epec for c in out.match_exacto} == {7, 14}
    # Cercanos ordenados por (hamming asc, valor_uses desc, cod_epec asc).
    hammings = [c.hamming for c in out.cercanos]
    assert hammings == sorted(hammings)
    # En empates de hamming, valor_uses desc es el desempate.
    for a, b in zip(out.cercanos, out.cercanos[1:]):
        if a.hamming == b.hamming:
            assert a.valor_uses >= b.valor_uses


def test_parte_no_aprobado_devuelve_400(seed_basico):
    """id_estado != 1 → ValueError ('solo Aprobados')."""
    from api.services.sugerencias_service import SugerenciasService

    _crear_parte(seed_basico, parte_id=13, id_estado=2)
    with pytest.raises(ValueError, match="solo para partes Aprobados"):
        SugerenciasService(seed_basico).candidatos_para_parte(13)


def test_parte_no_existe_devuelve_404(seed_basico):
    """ID inexistente → ValueError 'no existe'."""
    from api.services.sugerencias_service import SugerenciasService

    with pytest.raises(ValueError, match="no existe"):
        SugerenciasService(seed_basico).candidatos_para_parte(99999)


def test_match_exacto_multiple_misma_cod_epec(seed_basico):
    """Cod 7 tiene dos descripciones; parte 'gabinete only' coincide con
    'Gabinete simple' exacto y la otra ('Gabinete con altura') va a cercanos."""
    from api.services.sugerencias_service import SugerenciasService

    _crear_parte(seed_basico, parte_id=14, gabinete=True)
    out = SugerenciasService(seed_basico).candidatos_para_parte(14)

    assert len(out.match_exacto) == 1
    assert out.match_exacto[0].cod_epec == 7
    assert out.match_exacto[0].descripcion == "Gabinete simple"

    descs_cercanos = {(c.cod_epec, c.descripcion) for c in out.cercanos}
    assert (7, "Gabinete con altura") in descs_cercanos


def test_campos_diferentes_correcto(seed_basico):
    """Parte con gabinete=True; regla cod 14 (gabinete+altura) → diferencia=ALTURA."""
    from api.services.sugerencias_service import SugerenciasService

    _crear_parte(seed_basico, parte_id=15, gabinete=True)
    out = SugerenciasService(seed_basico).candidatos_para_parte(15)

    cod14 = next(c for c in out.todas if c.cod_epec == 14)
    assert cod14.hamming == 1
    assert cod14.campos_diferentes == ["ALTURA"]
