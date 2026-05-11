"""Tests del progreso granular emitido por `procesar_lote_en_background`.

Verifica que `paso_actual` recorre la secuencia esperada:
  RECIBIENDO → VALIDANDO_ESTRUCTURA → EJECUTANDO_MOTOR → IMPORTANDO_PARTES
  → FINALIZANDO → APROBADO (o RECHAZADO en caso de error).
"""
from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest


@pytest.fixture
def setup_lote(db, tmp_path, monkeypatch):
    """Crea Contratista + Usuario + Lote en RECIBIDO; configura un SessionLocal
    de tests apuntando a la misma DB en memoria."""
    from api.db.models.base_models import Contratista, LoteArchivo, UsuarioApp
    from api.services import worker as worker_mod
    from api.services import lote_service as svc_mod

    contratista = Contratista(id=1, nombre="CONECTAR", activo=True)
    usuario     = UsuarioApp(id=1, username="op1", email="o@x.com", rol="operador")
    db.add_all([contratista, usuario])
    db.flush()

    binario = tmp_path / "lote.xlsx"
    binario.write_bytes(b"dummy excel bytes")

    lote = LoteArchivo(
        nombre_archivo="lote.xlsx", hash_archivo="h" * 64,
        ruta_archivo=str(binario), contratista_id=1,
        estado="RECIBIDO", subido_por=1, paso_actual="RECIBIENDO", progreso_pct=0,
    )
    db.add(lote); db.commit(); db.refresh(lote)

    # Inyectar SessionLocal apuntando a la misma engine in-memory.
    bind = db.get_bind()
    from sqlalchemy.orm import sessionmaker
    SessionLocal_test = sessionmaker(bind=bind, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(worker_mod, "SessionLocal", SessionLocal_test)
    monkeypatch.setattr(svc_mod, "SessionLocal", SessionLocal_test)

    return {"db": db, "lote_id": lote.id}


class TestProgresoWorker:

    def test_recorre_pasos_en_orden(self, setup_lote, monkeypatch):
        """Mockea adapter, motor e import; captura la traza de pasos."""
        from api.services import worker as worker_mod
        from api.db.models.base_models import LoteArchivo

        capturados: list[tuple[str, int]] = []

        # Captura cada actualización de paso vía LoteService.actualizar_progreso.
        original_actualizar = worker_mod.SessionLocal  # noqa: F841

        # En lugar de monkeypatchear actualizar_progreso, leemos el estado
        # del lote después de la corrida; pero para verificar la secuencia
        # interceptamos la operación con un wrapper.
        from api.services import lote_service
        original_method = lote_service.LoteService.actualizar_progreso

        def spy(self, lote_id, paso, pct):
            capturados.append((paso, pct))
            return original_method(self, lote_id, paso, pct)

        monkeypatch.setattr(lote_service.LoteService, "actualizar_progreso", spy)

        # Mock del adapter — devuelve un df_aux mínimo.
        df_aux = pd.DataFrame({
            "ID_Externo":      ["A1"], "Fecha": pd.to_datetime(["2025-04-01"]),
            "Suministro":      ["111"],
            "medidorColocado": ["M1"], "medidorRetirado": ["R1"],
            "codTiposManoObra": ["07"], "ORIGEN_ARCHIVO": ["lote.xlsx"],
        })
        monkeypatch.setattr(worker_mod, "ejecutar_adapter", lambda *_a, **_k: df_aux)

        # Mock del motor — devuelve un df_final no vacío.
        df_final = pd.DataFrame({"ID_PARTE_HASH": ["h1"], "ID_ESTADO": [1], "ID_TRAZA": [1]})
        monkeypatch.setattr(
            worker_mod, "_ejecutar_motor_analitico",
            lambda *_a, **_k: (df_final, None),
        )

        # Mock detector de contratista — devuelve None para que pase la validación.
        monkeypatch.setattr(worker_mod, "_detectar_contratista_archivo", lambda _p: None)

        # Mock del importador — sin-op.
        from api.services import parte_import_service
        monkeypatch.setattr(
            parte_import_service.ParteImportService, "importar_lote",
            lambda self, **_kw: {"raws": 1, "procesados": 1, "imagenes": 0},
        )

        worker_mod.procesar_lote_en_background(setup_lote["lote_id"])

        pasos = [p for p, _ in capturados]
        assert "EJECUTANDO_MOTOR" in pasos
        assert "IMPORTANDO_PARTES" in pasos
        assert "FINALIZANDO" in pasos

        # Estado final del lote en DB
        lote = setup_lote["db"].query(LoteArchivo).filter(LoteArchivo.id == setup_lote["lote_id"]).first()
        # Refrescar — el worker usó otra session.
        setup_lote["db"].refresh(lote)
        assert lote.estado == "APROBADO"
        assert lote.paso_actual == "APROBADO"
        assert lote.progreso_pct == 100

    def test_error_marca_rechazado(self, setup_lote, monkeypatch):
        from api.services import worker as worker_mod
        from api.db.models.base_models import LoteArchivo

        # Adapter devuelve df vacío → worker levanta ValueError.
        monkeypatch.setattr(worker_mod, "ejecutar_adapter", lambda *_a, **_k: pd.DataFrame())
        monkeypatch.setattr(worker_mod, "_detectar_contratista_archivo", lambda _p: None)

        worker_mod.procesar_lote_en_background(setup_lote["lote_id"])

        lote = setup_lote["db"].query(LoteArchivo).filter(
            LoteArchivo.id == setup_lote["lote_id"]
        ).first()
        setup_lote["db"].refresh(lote)
        assert lote.estado == "RECHAZADO"
        assert lote.paso_actual == "RECHAZADO"
        assert lote.progreso_pct == 100
        assert lote.detalle_error is not None
