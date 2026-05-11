"""Test E2E del endpoint POST /api/v1/lotes con flag `force`.

Verifica el flujo: subida normal → 409 OVERLAP_WARN → reintento con
`force=true` → 201. Usa TestClient + DB SQLite in-memory inyectada vía
override de `get_db`.
"""
from __future__ import annotations

import io
from datetime import datetime
from unittest import mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.core.database import Base, get_db
    import api.db.models.base_models   # noqa: F401
    import api.db.models.domain_models  # noqa: F401
    from api.main import app
    from api.services import lote_service as svc_mod
    from api.services import worker as worker_mod

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(svc_mod, "UPLOADS_DIR", tmp_path / "uploads")

    # Sembrar contratista + usuario.
    from api.db.models.base_models import Contratista, UsuarioApp
    s = SessionLocal()
    s.add(Contratista(id=1, nombre="CONECTAR", activo=True))
    s.add(UsuarioApp(id=1, username="op1", email="o@x.com", rol="operador"))
    s.commit()

    # Sembrar 6 procesados con SUMINISTRO 100..105 / fecha 2025-04-01.
    from api.db.models.base_models import LoteArchivo
    from api.db.models.domain_models import ParteDiarioProcesado, ParteDiarioRaw

    lote_prev = LoteArchivo(
        nombre_archivo="prev.xlsx", hash_archivo="z" * 64,
        ruta_archivo="/tmp/prev.xlsx", contratista_id=1,
        estado="APROBADO", subido_por=1,
    )
    s.add(lote_prev); s.flush()
    for i in range(6):
        raw = ParteDiarioRaw(lote_id=lote_prev.id, fila_excel=i, id_parte_hash=f"prev-{i}", datos_crudos={})
        s.add(raw); s.flush()
        s.add(ParteDiarioProcesado(
            raw_id=raw.id, id_parte_hash=f"prev-{i}",
            lote_id=lote_prev.id, contratista_id=1,
            suministro=str(100 + i),
            fecha_ejecucion=datetime(2025, 4, 1),
            id_estado=1, id_traza=1, version=1,
        ))
    s.commit(); s.close()

    # Mock del adapter — devuelve un df_aux con 60% overlap.
    df = pd.DataFrame({
        "ID_Externo":      [f"E{i}" for i in range(10)],
        "Fecha":           pd.to_datetime(["2025-04-01"] * 10),
        "Suministro":      [str(100 + i) for i in range(6)] + [str(200 + i) for i in range(4)],
        "medidorColocado": [f"M{i}" for i in range(10)],
        "medidorRetirado": [f"R{i}" for i in range(10)],
        "codTiposManoObra": ["07"] * 10,
    })
    monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: df)
    # No-op del worker para no engancharse con el motor.
    monkeypatch.setattr(worker_mod, "procesar_lote_en_background", lambda _id: None)

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_overlap_then_force(client):
    """Primer POST devuelve 409 OVERLAP_WARN; reintento con force=true devuelve 201."""
    files = {"archivo": ("nuevo.xlsx", io.BytesIO(b"bytes-nuevos"), "application/octet-stream")}
    params = {"contratista_id": 1, "subido_por": 1}

    r1 = client.post("/api/v1/lotes/", params=params, files=files)
    assert r1.status_code == 409, r1.text
    detail = r1.json()["detail"]
    assert detail["code"] == "OVERLAP_WARN"
    assert detail["n_existentes"] == 6
    assert detail["n_total"] == 10
    assert detail["requires_force"] is True

    # Reintento con force=true (mismos bytes).
    files = {"archivo": ("nuevo.xlsx", io.BytesIO(b"bytes-nuevos"), "application/octet-stream")}
    r2 = client.post("/api/v1/lotes/", params={**params, "force": "true"}, files=files)
    assert r2.status_code == 201, r2.text
    assert r2.json()["estado"] == "RECIBIDO"
    assert r2.json()["paso_actual"] == "RECIBIENDO"
    assert r2.json()["progreso_pct"] == 0


def test_dup_bytes_409(client):
    """Subir el mismo archivo dos veces (mismos bytes) devuelve 409 DUP_BYTES."""
    files = {"archivo": ("a.xlsx", io.BytesIO(b"contenido-A"), "application/octet-stream")}
    params = {"contratista_id": 1, "subido_por": 1, "force": "true"}
    r1 = client.post("/api/v1/lotes/", params=params, files=files)
    assert r1.status_code == 201

    files = {"archivo": ("renombrado.xlsx", io.BytesIO(b"contenido-A"), "application/octet-stream")}
    r2 = client.post("/api/v1/lotes/", params=params, files=files)
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "DUP_BYTES"
    assert r2.json()["detail"]["lote_existente_id"] > 0
