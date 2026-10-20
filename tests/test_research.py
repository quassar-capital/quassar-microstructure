
"""Numerical and structural tests for Quassar Microstructure research."""
import numpy as np
import pytest

from quassar_microstructure.research import (
    HawkesSpecification,
    branching_radius,
    impact_curve,
    time_rescaling,
)


def test_branching_radius_diagonal():
    matrix = np.diag([0.2, 0.7])
    assert branching_radius(matrix) == pytest.approx(0.7)


def test_stationary_mean_univariate():
    model = HawkesSpecification(
        baseline=(2.0,),
        excitation=((0.5,),),
        decay=1.0,
    )
    assert model.stationary
    np.testing.assert_allclose(model.stationary_mean_intensity(), [4.0])


def test_supercritical_model_rejected_for_stationary_mean():
    model = HawkesSpecification(
        baseline=(1.0,),
        excitation=((1.2,),),
        decay=1.0,
    )
    assert not model.stationary
    with pytest.raises(ValueError):
        model.stationary_mean_intensity()


def test_invalid_excitation_rejected():
    with pytest.raises(ValueError):
        HawkesSpecification(
            baseline=(1.0, 2.0),
            excitation=((0.1,),),
            decay=1.0,
        )


def test_poisson_time_rescaling():
    events = [0.5, 1.5, 2.0]
    increments = time_rescaling(
        events,
        baseline=2.0,
        excitation=0.0,
        decay=1.0,
    )
    np.testing.assert_allclose(increments, [1.0, 2.0, 1.0])


def test_rescaling_rejects_unsorted_events():
    with pytest.raises(ValueError):
        time_rescaling(
            [1.0, 0.5],
            baseline=1.0,
            excitation=0.2,
            decay=1.0,
        )


def test_signed_impact_is_odd():
    volumes = np.array([-100.0, -4.0, 0.0, 4.0, 100.0])
    impact = impact_curve(volumes, coefficient=0.01)
    np.testing.assert_allclose(impact, -impact[::-1])
    assert impact[2] == 0.0


def test_impact_rejects_invalid_exponent():
    with pytest.raises(ValueError):
        impact_curve([1.0], coefficient=0.01, exponent=1.5)
