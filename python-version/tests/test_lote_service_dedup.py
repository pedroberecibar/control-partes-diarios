"""Tests para la antiduplicidad de tres capas en `LoteService.crear_lote`.

Capa 1: bytes idénticos → DuplicadoBytesError.
Capa 2: bytes distintos / contenido idéntico → DuplicadoContenidoError (mock adapter).
Capa 3: overlap > threshold → OverlapWarning, salvo `force=True`.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest


@pytest.fixture
def setup_base(db, tmp_path, monkeypatch):
    """Contratista + Usuario + UPLOADS_DIR temporal para no contaminar `data/uploads/`."""
    from api.db.models.base_models import Contratista, UsuarioApp
    from api.services import lote_service as svc_mod

    contratista = Contratista(id=1, nombre="CONECTAR", activo=True)
    usuario     = UsuarioApp(id=1, username="op1", email="o@x.com", rol="operador")
    db.add_all([contratista, usuario])
    db.commit()

    monkeypatch.setattr(svc_mod, "UPLOADS_DIR", tmp_path / "uploads")
    return db


def _df_demo() -> pd.DataFrame:
    """df_aux mock — formato de salida del adapter CONECTAR."""
    return pd.DataFrame({
        "ID_Externo":      ["A1", "A2", "A3"],
        "Fecha":           pd.to_datetime(["2025-04-01", "2025-04-01", "2025-04-02"]),
        "Suministro":      ["111", "222", "333"],
        "medidorColocado": ["M1", "M2", "M3"],
        "medidorRetirado": ["R1", "R2", "R3"],
        "codTiposManoObra": ["07", "07", "02"],
        "ORIGEN_ARCHIVO":  ["foo.xlsx"] * 3,
    })


class TestCapa1Bytes:

    def test_bytes_identicos_rechazado(self, setup_base, monkeypatch):
        from api.services.lote_service import LoteService
        from api.services.exceptions import DuplicadoBytesError
        from api.services import lote_service as svc_mod

        # Adapter mockeado para evitar que parsee Excel real.
        monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: None)

        svc = LoteService(setup_base)
        contenido = b"contenido binario de prueba"
        svc.crear_lote("a.xlsx", contenido, contratista_id=1, subido_por=1)

        with pytest.raises(DuplicadoBytesError) as exc:
            svc.crear_lote("b.xlsx", contenido, contratista_id=1, subido_por=1)
        assert exc.value.lote_existente_id > 0


class TestCapa2Contenido:

    def test_bytes_distintos_contenido_identico_rechazado(self, setup_base, monkeypatch):
        from api.services.lote_service import LoteService
        from api.services.exceptions import DuplicadoContenidoError
        from api.services import lote_service as svc_mod

        monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: _df_demo())

        svc = LoteService(setup_base)
        svc.crear_lote("a.xlsx", b"bytes-A", contratista_id=1, subido_por=1)
        with pytest.raises(DuplicadoContenidoError) as exc:
            svc.crear_lote("b.xlsx", b"bytes-B", contratista_id=1, subido_por=1)
        assert exc.value.lote_existente_id > 0

    def test_contenido_distinto_pasa(self, setup_base, monkeypatch):
        from api.services.lote_service import LoteService
        from api.services import lote_service as svc_mod

        df1 = _df_demo()
        df2 = _df_demo()
        df2.loc[0, "Suministro"] = "999"  # cambio en columna-clave

        secuencia = iter([df1, df2])
        monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: next(secuencia))

        svc = LoteService(setup_base)
        svc.crear_lote("a.xlsx", b"bytes-A", contratista_id=1, subido_por=1)
        # Segundo lote con bytes y contenido distintos → debe aceptarse.
        lote2 = svc.crear_lote("b.xlsx", b"bytes-B", contratista_id=1, subido_por=1)
        assert lote2.id > 0


class TestCapa3Overlap:

    def _seed_procesados(self, db, n: int, contratista_id: int = 1):
        """Inserta `n` partes procesados con SUMINISTRO 1..n y FECHA 2025-04-01."""
        from api.db.models.base_models import LoteArchivo
        from api.db.models.domain_models import ParteDiarioProcesado, ParteDiarioRaw

        lote = LoteArchivo(
            nombre_archivo="prev.xlsx", hash_archivo="z" * 64,
            ruta_archivo="/tmp/prev.xlsx", contratista_id=contratista_id,
            estado="APROBADO", subido_por=1,
        )
        db.add(lote); db.flush()
        for i in range(n):
            raw = ParteDiarioRaw(lote_id=lote.id, fila_excel=i, id_parte_hash=f"prev-{i}", datos_crudos={})
            db.add(raw); db.flush()
            db.add(ParteDiarioProcesado(
                raw_id=raw.id, id_parte_hash=f"prev-{i}",
                lote_id=lote.id, contratista_id=contratista_id,
                suministro=str(100 + i),
                fecha_ejecucion=datetime(2025, 4, 1),
                nro_medidor_colocado=f"M{i}",
                nro_medidor_retirado=f"R{i}",
                id_estado=1, id_traza=1, version=1,
            ))
        db.commit()

    def test_overlap_supera_threshold_levanta_warning(self, setup_base, monkeypatch):
        from api.services.lote_service import LoteService
        from api.services.exceptions import OverlapWarning
        from api.services import lote_service as svc_mod

        # Sembrar 6 procesados con SUMINISTRO 100..105
        self._seed_procesados(setup_base, n=6)

        # df_aux con 10 filas, 6 overlap (100..105) + 4 nuevas (200..203)
        df = pd.DataFrame({
            "ID_Externo":      [f"E{i}" for i in range(10)],
            "Fecha":           pd.to_datetime(["2025-04-01"] * 10),
            "Suministro":      [str(100 + i) for i in range(6)] + [str(200 + i) for i in range(4)],
            "medidorColocado": [f"M{i}" for i in range(10)],
            "medidorRetirado": [f"R{i}" for i in range(10)],
            "codTiposManoObra": ["07"] * 10,
        })
        monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: df)

        svc = LoteService(setup_base)
        with pytest.raises(OverlapWarning) as exc:
            svc.crear_lote("nuevo.xlsx", b"bytes-X", contratista_id=1, subido_por=1)
        assert exc.value.n_existentes == 6
        assert exc.value.n_total == 10
        assert exc.value.overlap_pct == 0.6

    def test_force_skipea_overlap(self, setup_base, monkeypatch):
        from api.services.lote_service import LoteService
        from api.services import lote_service as svc_mod

        self._seed_procesados(setup_base, n=6)
        df = pd.DataFrame({
            "ID_Externo":      [f"E{i}" for i in range(10)],
            "Fecha":           pd.to_datetime(["2025-04-01"] * 10),
            "Suministro":      [str(100 + i) for i in range(6)] + [str(200 + i) for i in range(4)],
            "medidorColocado": [f"M{i}" for i in range(10)],
            "medidorRetirado": [f"R{i}" for i in range(10)],
            "codTiposManoObra": ["07"] * 10,
        })
        monkeypatch.setattr(svc_mod, "ejecutar_adapter", lambda *_a, **_k: df)

        svc = LoteService(setup_base)
        lote = svc.crear_lote(
            "nuevo.xlsx", b"bytes-X",
            contratista_id=1, subido_por=1, force=True,
        )
        assert lote.id > 0
        assert lote.estado == "RECIBIDO"
