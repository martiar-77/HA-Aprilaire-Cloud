"""Pure unit tests for setpoint encoding (no HA harness needed)."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "setpoints",
    pathlib.Path(__file__).parents[1] / "custom_components/aprilaire_cloud/setpoints.py",
)
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


@pytest.mark.parametrize(
    ("f", "c"), [(40, 4.44), (67, 19.44), (68, 20.0), (72, 22.22), (78, 25.56), (93, 33.89)]
)
def test_f_to_c(f, c):
    assert sp.f_to_c(f) == c


def test_round_trip_all_whole_f():
    for f in range(40, 94):
        assert sp.c_to_whole_f(sp.f_to_c(f)) == f


def test_snap_raw_ha_conversion():
    assert sp.snap_c((67 - 32) * 5 / 9) == 19.44  # 19.4444...
    assert sp.snap_c(19.5) == 19.44  # 67.1F
    assert sp.snap_c(22.2222222) == 22.22


def test_fills_companion():
    assert sp.resolve_setpoints(20.0, 25.56, heat_c=19.4444) == {"heat": 19.44, "cool": 25.56}
    assert sp.resolve_setpoints(20.0, 25.56, cool_c=26.1111) == {"heat": 20.0, "cool": 26.11}


def test_heat_pushes_cool():
    # heat 68->77F with cool 78F -> cool 80F
    assert sp.resolve_setpoints(20.0, 25.56, heat_c=25.0) == {"heat": 25.0, "cool": 26.67}


def test_cool_pushes_heat():
    # cool 78->69F with heat 68F -> heat 66F
    assert sp.resolve_setpoints(20.0, 25.56, cool_c=20.56) == {"heat": 18.89, "cool": 20.56}


def test_clamps_and_edges():
    assert sp.resolve_setpoints(20.0, 25.56, heat_c=40.0) == {"heat": 32.22, "cool": 33.89}  # 90/93
    assert sp.resolve_setpoints(20.0, 25.56, cool_c=0.0) == {"heat": 8.33, "cool": 10.0}  # 47/50
    assert sp.resolve_setpoints(20.0, 25.56, heat_c=-10.0)["heat"] == 4.44


def test_missing_companion_raises():
    with pytest.raises(ValueError):
        sp.resolve_setpoints(None, None, heat_c=20.0)
