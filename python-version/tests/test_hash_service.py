"""Tests para `api.services.hash_service` — antiduplicidad por contenido."""
from __future__ import annotations

import pandas as pd
import pytest

from api.services.hash_service import (
    COLS_CONTENIDO,
    hash_bytes,
    hash_contenido_normalizado,
)


def _df_demo(extra: dict | None = None) -> pd.DataFrame:
    base = {
        "ID_Externo":      ["A1", "A2", "A3"],
        "Fecha":           ["2025-04-01", "2025-04-01", "2025-04-02"],
        "Suministro":      ["111", "222", "333"],
        "medidorColocado": ["M1", "M2", "M3"],
        "medidorRetirado": ["R1", "R2", "R3"],
        "codTiposManoObra": ["07", "07", "02"],
    }
    if extra:
        base.update(extra)
    return pd.DataFrame(base)


class TestHashBytes:

    def test_idempotente(self):
        b = b"hola mundo"
        assert hash_bytes(b) == hash_bytes(b)

    def test_distintos_bytes_distinto_hash(self):
        assert hash_bytes(b"abc") != hash_bytes(b"abd")


class TestHashContenidoNormalizado:

    def test_invariante_orden_filas(self):
        df_a = _df_demo()
        df_b = df_a.iloc[::-1].reset_index(drop=True)
        assert hash_contenido_normalizado(df_a) == hash_contenido_normalizado(df_b)

    def test_invariante_columnas_volatiles(self):
        """Agregar columnas volátiles (ORIGEN_ARCHIVO, fecha_proceso) no debe cambiar el hash."""
        df_a = _df_demo()
        df_b = _df_demo(extra={
            "ORIGEN_ARCHIVO": ["foo.xlsx"] * 3,
            "fecha_proceso":  pd.to_datetime(["2026-05-08"] * 3),
            "TRAZA_ADAPTER":  [None, None, None],
        })
        assert hash_contenido_normalizado(df_a) == hash_contenido_normalizado(df_b)

    def test_invariante_strings_normalizados(self):
        df_a = _df_demo()
        df_b = _df_demo()
        df_b["Suministro"] = df_b["Suministro"].str.upper()  # case insensitive
        df_b["medidorColocado"] = "  " + df_b["medidorColocado"] + " "  # whitespace
        assert hash_contenido_normalizado(df_a) == hash_contenido_normalizado(df_b)

    def test_sensible_a_cambio_clave(self):
        df_a = _df_demo()
        df_b = _df_demo()
        df_b.loc[0, "Suministro"] = "999"
        assert hash_contenido_normalizado(df_a) != hash_contenido_normalizado(df_b)

    def test_df_vacio(self):
        df_vacio = pd.DataFrame()
        # No revienta y devuelve hash de bytes vacíos.
        h = hash_contenido_normalizado(df_vacio)
        assert isinstance(h, str) and len(h) == 64

    def test_columnas_faltantes_se_completan(self):
        """Si el adapter devuelve un df sin alguna columna canónica, se rellena vacía."""
        df = pd.DataFrame({"ID_Externo": ["A1"], "Fecha": ["2025-04-01"]})
        h = hash_contenido_normalizado(df)
        assert isinstance(h, str) and len(h) == 64
