"""Tests para el enriquecimiento de VALOR_USES_ORIGEN en partes no-aprobados.

Cubre:
  - _enriquecer_uses (worker.py): lógica central del lookup cod_epec → USES
  - _validar_uses_coverage (parte_import_service.py): validaciones de runtime
  - _cod_epec_efectivo (parte_import_service.py): fallback sugerido para aprobados

Todos los tests son unitarios (sin I/O de archivos ni DB).
"""
from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------

@pytest.fixture
def df_reglas_simple() -> pd.DataFrame:
    """Tabla de reglas mínima con 3 códigos EPEC y sus valores USES."""
    return pd.DataFrame({
        "COD_EPEC":    [1,    1,    7,    7,    11],
        "DESCRIPCION": ["A1", "A2", "B1", "B2", "C1"],
        "VALOR_USES":  [1.0,  1.0,  2.5,  2.5,  0.5],
        # Obs columns (no usadas en el lookup de USES pero presentes en el df real)
        "GABINETE":    [1,    0,    1,    0,    0],
    })


@pytest.fixture
def df_no_aprobados() -> pd.DataFrame:
    """DataFrame simulando la salida de etapa3 para no-aprobados."""
    return pd.DataFrame({
        "ID_PARTE_HASH": ["hash-1", "hash-2", "hash-3", "hash-4"],
        "ID_ESTADO":     [2,        3,         3,         2],       # ninguno es 1 (Aprobado)
        "CODIGO_EPEC":   pd.array([1, 7, 99, None], dtype="Int64"), # 99 no existe en reglas
        "SUMINISTRO_RAW": ["S1", "S2", "S3", "S4"],
    })


# ---------------------------------------------------------------------------
# Tests de _enriquecer_uses
# ---------------------------------------------------------------------------

class TestEnriquecerUses:

    def _fn(self):
        from api.services.worker import _enriquecer_uses
        return _enriquecer_uses

    def test_llena_uses_cuando_codigo_existe(self, df_no_aprobados, df_reglas_simple):
        fn = self._fn()
        result = fn(df_no_aprobados.copy(), df_reglas_simple)

        # hash-1 tiene cod 1 → USES = 1.0
        row1 = result.loc[result["ID_PARTE_HASH"] == "hash-1"].iloc[0]
        assert row1["VALOR_USES_ORIGEN"] == pytest.approx(1.0)

        # hash-2 tiene cod 7 → USES = 2.5
        row2 = result.loc[result["ID_PARTE_HASH"] == "hash-2"].iloc[0]
        assert row2["VALOR_USES_ORIGEN"] == pytest.approx(2.5)

    def test_codigo_sin_regla_queda_nulo(self, df_no_aprobados, df_reglas_simple):
        fn = self._fn()
        result = fn(df_no_aprobados.copy(), df_reglas_simple)

        # hash-3 tiene cod 99 (no existe en reglas) → USES nulo
        row3 = result.loc[result["ID_PARTE_HASH"] == "hash-3"].iloc[0]
        assert pd.isna(row3["VALOR_USES_ORIGEN"])

    def test_codigo_epec_nulo_queda_uses_nulo(self, df_no_aprobados, df_reglas_simple):
        fn = self._fn()
        result = fn(df_no_aprobados.copy(), df_reglas_simple)

        # hash-4 tiene CODIGO_EPEC = None → USES nulo
        row4 = result.loc[result["ID_PARTE_HASH"] == "hash-4"].iloc[0]
        assert pd.isna(row4["VALOR_USES_ORIGEN"])

    def test_no_sobreescribe_valor_existente(self, df_reglas_simple):
        fn = self._fn()
        df = pd.DataFrame({
            "ID_PARTE_HASH":   ["hash-a"],
            "CODIGO_EPEC":     pd.array([1], dtype="Int64"),
            "VALOR_USES_ORIGEN": [99.0],  # ya tiene valor asignado por Etapa 4
        })
        result = fn(df, df_reglas_simple)
        assert result.loc[0, "VALOR_USES_ORIGEN"] == pytest.approx(99.0), \
            "No debe sobreescribir USES ya calculado por Etapa 4"

    def test_llena_nulos_pero_preserva_existentes(self, df_reglas_simple):
        fn = self._fn()
        df = pd.DataFrame({
            "ID_PARTE_HASH":     ["hash-a", "hash-b"],
            "CODIGO_EPEC":       pd.array([1, 7], dtype="Int64"),
            "VALOR_USES_ORIGEN": pd.array([99.0, None], dtype="Float64"),
        })
        result = fn(df, df_reglas_simple)
        assert result.loc[0, "VALOR_USES_ORIGEN"] == pytest.approx(99.0), "Preservado"
        assert result.loc[1, "VALOR_USES_ORIGEN"] == pytest.approx(2.5),  "Llenado"

    def test_sin_columna_codigo_epec_devuelve_df_intacto(self, df_reglas_simple):
        fn = self._fn()
        df = pd.DataFrame({"ID_PARTE_HASH": ["x"], "ID_ESTADO": [2]})
        result = fn(df, df_reglas_simple)
        assert "VALOR_USES_ORIGEN" not in result.columns
        assert len(result) == len(df)

    def test_reglas_vacias_devuelve_df_intacto(self, df_no_aprobados):
        fn = self._fn()
        df_reglas_vacio = pd.DataFrame(columns=["COD_EPEC", "VALOR_USES"])
        result = fn(df_no_aprobados.copy(), df_reglas_vacio)
        # Sin reglas no puede asignar USES, pero no debe fallar
        if "VALOR_USES_ORIGEN" in result.columns:
            assert result["VALOR_USES_ORIGEN"].isna().all()

    def test_multiples_variantes_mismo_codigo_no_duplica_filas(self, df_reglas_simple):
        """Cod 1 tiene 2 variantes (A1, A2). El resultado NO debe fan-out."""
        fn = self._fn()
        df = pd.DataFrame({
            "ID_PARTE_HASH": ["hash-a"],
            "CODIGO_EPEC":   pd.array([1], dtype="Int64"),
        })
        result = fn(df, df_reglas_simple)
        assert len(result) == 1, "No debe duplicar filas por variantes del mismo cod_epec"
        assert result.loc[0, "VALOR_USES_ORIGEN"] == pytest.approx(1.0)

    def test_columnas_temporales_limpiadas(self, df_no_aprobados, df_reglas_simple):
        fn = self._fn()
        result = fn(df_no_aprobados.copy(), df_reglas_simple)
        assert "_lkp_cod"  not in result.columns
        assert "_lkp_uses" not in result.columns


# ---------------------------------------------------------------------------
# Tests de _validar_uses_coverage (parte_import_service)
# ---------------------------------------------------------------------------

class TestValidarUsesCoverage:

    def _svc(self):
        from api.services.parte_import_service import ParteImportService
        # Instanciar con db=None — solo usamos métodos que no tocan la DB
        return ParteImportService.__new__(ParteImportService)

    def test_no_error_sin_columnas(self):
        svc = self._svc()
        df = pd.DataFrame({"ID_PARTE_HASH": ["h1"]})
        # No debe lanzar excepción
        svc._validar_uses_coverage(df, lote_id=1)

    def test_aprobado_sin_uses_registra_warning(self, caplog):
        import logging
        svc = self._svc()
        df = pd.DataFrame({
            "ID_ESTADO":       [1,   2],
            "CODIGO_EPEC":     pd.array([5, 7], dtype="Int64"),
            "VALOR_USES_ORIGEN": pd.array([None, 2.5], dtype="Float64"),
        })
        with caplog.at_level(logging.WARNING, logger="api.services.parte_import"):
            svc._validar_uses_coverage(df, lote_id=99)
        assert any("APROBADOS sin VALOR_USES_ORIGEN" in r.message for r in caplog.records)

    def test_aprobado_con_uses_no_registra_warning(self, caplog):
        import logging
        svc = self._svc()
        df = pd.DataFrame({
            "ID_ESTADO":       [1],
            "CODIGO_EPEC":     pd.array([5], dtype="Int64"),
            "VALOR_USES_ORIGEN": pd.array([1.5], dtype="Float64"),
        })
        with caplog.at_level(logging.WARNING, logger="api.services.parte_import"):
            svc._validar_uses_coverage(df, lote_id=1)
        assert not any("APROBADOS sin VALOR_USES_ORIGEN" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Tests de _cod_epec_efectivo (parte_import_service)
# ---------------------------------------------------------------------------

class TestCodEpecEfectivo:

    def _svc(self):
        from api.services.parte_import_service import ParteImportService
        return ParteImportService.__new__(ParteImportService)

    def _row(self, id_estado, codigo_epec, cod_epec_sugerido):
        return pd.Series({
            "ID_ESTADO":        id_estado,
            "CODIGO_EPEC":      codigo_epec,
            "COD_EPEC_SUGERIDO": cod_epec_sugerido,
        })

    def test_aprobado_con_epec_usa_original(self):
        svc = self._svc()
        row = self._row(id_estado=1, codigo_epec=7, cod_epec_sugerido=11)
        assert svc._cod_epec_efectivo(row) == 7

    def test_aprobado_sin_epec_usa_sugerido(self):
        svc = self._svc()
        row = self._row(id_estado=1, codigo_epec=None, cod_epec_sugerido=11)
        assert svc._cod_epec_efectivo(row) == 11

    def test_no_aprobado_sin_epec_queda_nulo(self):
        svc = self._svc()
        row = self._row(id_estado=2, codigo_epec=None, cod_epec_sugerido=11)
        assert svc._cod_epec_efectivo(row) is None

    def test_no_aprobado_con_epec_usa_original(self):
        svc = self._svc()
        row = self._row(id_estado=3, codigo_epec=5, cod_epec_sugerido=7)
        assert svc._cod_epec_efectivo(row) == 5

    def test_ambos_nulos_devuelve_none(self):
        svc = self._svc()
        row = self._row(id_estado=1, codigo_epec=None, cod_epec_sugerido=None)
        assert svc._cod_epec_efectivo(row) is None


# ---------------------------------------------------------------------------
# Test de integración: concat aprobados + no-aprobados → todos tienen USES
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tests de _resolver_uses (parte_import_service)
# ---------------------------------------------------------------------------

class TestResolverUses:

    def _fn(self):
        from api.services.parte_import_service import ParteImportService
        return ParteImportService._resolver_uses

    def test_usa_valor_pipeline_cuando_existe(self):
        fn = self._fn()
        lookup = {7: 2.5}
        # Pipeline ya tiene valor → lo preserva aunque haya lookup diferente
        assert fn(1.5, 7, lookup) == pytest.approx(1.5)

    def test_fallback_a_lookup_cuando_pipeline_es_none(self):
        fn = self._fn()
        lookup = {7: 2.5}
        assert fn(None, 7, lookup) == pytest.approx(2.5)

    def test_fallback_a_lookup_cuando_pipeline_es_nan(self):
        import math
        fn = self._fn()
        lookup = {7: 2.5}
        assert fn(float("nan"), 7, lookup) == pytest.approx(2.5)

    def test_none_cuando_cod_epec_no_en_lookup(self):
        fn = self._fn()
        lookup = {7: 2.5}
        assert fn(None, 99, lookup) is None

    def test_none_cuando_cod_epec_es_none(self):
        fn = self._fn()
        lookup = {7: 2.5}
        assert fn(None, None, lookup) is None

    def test_none_cuando_lookup_es_none(self):
        fn = self._fn()
        assert fn(None, 7, None) is None

    def test_none_cuando_lookup_vacio(self):
        fn = self._fn()
        assert fn(None, 7, {}) is None

    def test_pipeline_cero_no_se_confunde_con_none(self):
        fn = self._fn()
        lookup = {7: 2.5}
        # 0.0 es un valor válido (no debe caer al lookup)
        assert fn(0.0, 7, lookup) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test gap A: aprobado con CODIGO_EPEC null pero COD_EPEC_SUGERIDO no null
# ---------------------------------------------------------------------------

class TestGapAAprobadoSinCodigoOriginal:
    """Verifica que un aprobado cuyo CODIGO_EPEC era null pero COD_EPEC_SUGERIDO
    existe recibe USES correcto a través del lookup en _crear_procesados."""

    def test_resolver_uses_con_sugerido_como_cod_final(self):
        from api.services.parte_import_service import ParteImportService
        fn = ParteImportService._resolver_uses

        # Simula: VALOR_USES_ORIGEN null (Etapa 4 no encontró CODIGO_EPEC)
        # pero cod_epec_efectivo devolvió el sugerido (11)
        lookup = {11: 0.5, 7: 2.5}
        result = fn(None, 11, lookup)
        assert result == pytest.approx(0.5), \
            "Debe asignar USES usando el cod_epec_sugerido como fallback"

    def test_aprobado_con_codigo_null_obtiene_uses_via_lookup(self):
        """Simula el flujo completo para un aprobado con CODIGO_EPEC=null."""
        from api.services.parte_import_service import ParteImportService
        svc = ParteImportService.__new__(ParteImportService)

        row = pd.Series({
            "ID_ESTADO":         1,
            "CODIGO_EPEC":       None,
            "COD_EPEC_SUGERIDO": 11,
            "VALOR_USES_ORIGEN": None,  # Etapa 4 no asignó porque CODIGO_EPEC era null
        })

        cod_epec = svc._cod_epec_efectivo(row)
        assert cod_epec == 11, "Debe usar el sugerido"

        uses_lookup = {11: 0.5}
        valor_uses = svc._resolver_uses(row.get("VALOR_USES_ORIGEN"), cod_epec, uses_lookup)
        assert valor_uses == pytest.approx(0.5), "Debe obtener USES via lookup del sugerido"


class TestIntegracionConcatUses:
    """Simula la recombinación en _ejecutar_motor_analitico y verifica cobertura."""

    def test_no_aprobados_reciben_uses_tras_enriquecimiento(self, df_reglas_simple):
        from api.services.worker import _enriquecer_uses

        # Simular df_aprobados (ya procesados por Etapa 4 con USES)
        df_aprobados = pd.DataFrame({
            "ID_PARTE_HASH":     ["ap-1", "ap-2"],
            "ID_ESTADO":         [1, 1],
            "CODIGO_EPEC":       pd.array([1, 7], dtype="Int64"),
            "VALOR_USES_ORIGEN": [1.0, 2.5],
        })

        # Simular df_no_aprobados (vienen de etapa3, sin USES)
        df_no_aprobados = pd.DataFrame({
            "ID_PARTE_HASH": ["no-1", "no-2", "no-3"],
            "ID_ESTADO":     [2, 3, 3],
            "CODIGO_EPEC":   pd.array([1, 7, None], dtype="Int64"),
        })

        df_no_aprobados = _enriquecer_uses(df_no_aprobados, df_reglas_simple)
        df_completo = pd.concat([df_aprobados, df_no_aprobados], ignore_index=True, sort=False)

        # Todos los que tienen cod_epec deben tener USES
        con_epec = df_completo["CODIGO_EPEC"].notna()
        sin_uses = df_completo["VALOR_USES_ORIGEN"].isna()
        filas_faltantes = df_completo.loc[con_epec & sin_uses]

        assert len(filas_faltantes) == 0, (
            f"Partes con cod_epec pero sin USES tras enriquecimiento:\n{filas_faltantes}"
        )

    def test_sin_reglas_no_falla(self):
        from api.services.worker import _enriquecer_uses
        df = pd.DataFrame({
            "ID_PARTE_HASH": ["x"],
            "CODIGO_EPEC":   pd.array([5], dtype="Int64"),
        })
        result = _enriquecer_uses(df, None)
        assert len(result) == len(df)
