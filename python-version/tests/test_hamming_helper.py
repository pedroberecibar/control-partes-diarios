"""Tests del helper `src.hamming` — paridad bit-exacta vs cálculo inline original."""
from __future__ import annotations

import numpy as np
import pytest

from src import config
from src import hamming as hamming_helper


# ---------------------------------------------------------------------------
# hamming_matrix
# ---------------------------------------------------------------------------

def test_hamming_matrix_shape_y_valores_conocidos():
    app = np.array([
        [1, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 0, 0],
    ], dtype="int8")
    regla = np.array([
        [1, 0, 1, 0, 0, 0, 0, 0],   # idéntico al app[0] → hamming(0)=0, hamming(1)=4
        [0, 0, 0, 0, 0, 0, 0, 0],   # vacío → hamming(0)=2, hamming(1)=2
        [1, 1, 1, 1, 1, 1, 1, 1],   # todos en 1 → hamming(0)=6, hamming(1)=6
    ], dtype="int8")

    out = hamming_helper.hamming_matrix(app, regla)

    assert out.shape == (2, 3)
    assert out.dtype == np.int16
    assert out[0, 0] == 0
    assert out[1, 0] == 4
    assert out[0, 1] == 2
    assert out[1, 1] == 2
    assert out[0, 2] == 6
    assert out[1, 2] == 6


def test_hamming_matrix_paridad_etapa4():
    """La fórmula del helper debe coincidir bit-a-bit con la inline en
    `etapa4_control_obs._calcular_hamming_global`."""
    rng = np.random.default_rng(seed=42)
    app_mat = rng.integers(0, 2, size=(5, 8), dtype=np.int8)
    regla_mat = rng.integers(0, 2, size=(10, 8), dtype=np.int8)

    inline = np.abs(app_mat[:, None, :] - regla_mat[None, :, :]).sum(axis=2)
    helper = hamming_helper.hamming_matrix(app_mat, regla_mat)

    assert np.array_equal(inline.astype("int16"), helper)


def test_hamming_matrix_inputs_extremos():
    app = np.zeros((1, 8), dtype="int8")
    regla = np.ones((1, 8), dtype="int8")
    assert hamming_helper.hamming_matrix(app, regla)[0, 0] == 8

    iguales = np.ones((1, 8), dtype="int8")
    assert hamming_helper.hamming_matrix(iguales, iguales)[0, 0] == 0


# ---------------------------------------------------------------------------
# campos_diferentes
# ---------------------------------------------------------------------------

def test_campos_diferentes_devuelve_labels_en_orden_obs_cols():
    # config.OBS_COLS[0] = ("GABINETE", "GABINETE")
    # config.OBS_COLS[2] = ("ALTURA", "ALTURA")
    app   = np.array([1, 0, 1, 0, 0, 0, 0, 0], dtype="int8")
    regla = np.array([0, 0, 1, 0, 0, 0, 0, 0], dtype="int8")  # difiere solo en GABINETE
    assert hamming_helper.campos_diferentes(app, regla) == ["GABINETE"]


def test_campos_diferentes_iguales():
    v = np.array([1, 1, 0, 0, 1, 0, 0, 1], dtype="int8")
    assert hamming_helper.campos_diferentes(v, v) == []


def test_campos_diferentes_todos_distintos():
    app = np.zeros(8, dtype="int8")
    regla = np.ones(8, dtype="int8")
    labels = hamming_helper.campos_diferentes(app, regla)
    esperado = [cr for _, cr in config.OBS_COLS]
    assert labels == esperado
