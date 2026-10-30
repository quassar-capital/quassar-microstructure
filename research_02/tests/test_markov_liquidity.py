
"""Analytical verification of Research 02 Markov liquidity methods."""

from __future__ import annotations

import numpy as np
import pytest

from research_02.python.liquidity_transitions import (
    first_passage_probability,
    liquidity_depletion_states,
    transient_distribution,
)
from research_02.python.state_dependent_book import (
    QueueModel,
    mean_first_passage,
    spectral_gap,
    stationary_distribution,
    validate_generator,
)


def test_queue_generator_and_stationary_law() -> None:
    model = QueueModel(
        cap=3,
        arrival=2.0,
        cancellation=0.5,
        execution=0.8,
        imbalance_sensitivity=0.4,
    )

    q = validate_generator(model.generator())
    pi = stationary_distribution(q)

    assert q.shape == (16, 16)
    np.testing.assert_allclose(q.sum(axis=1), 0.0, atol=1e-12)
    np.testing.assert_allclose(pi @ q, 0.0, atol=1e-10)
    assert np.all(pi > 0.0)
    assert pi.sum() == pytest.approx(1.0)


def test_two_state_analytical_reference() -> None:
    # Transition rates: state 0 -> 1 at 2, state 1 -> 0 at 3.
    q = np.array([[-2.0, 2.0], [3.0, -3.0]])

    np.testing.assert_allclose(
        stationary_distribution(q),
        [0.6, 0.4],
        atol=1e-12,
    )

    assert spectral_gap(q) == pytest.approx(5.0)

    np.testing.assert_allclose(
        mean_first_passage(q, [1]),
        [0.5, 0.0],
        atol=1e-12,
    )

    horizon = 0.7
    initial = [1.0, 0.0]

    expected_state_one = 0.4 * (1.0 - np.exp(-5.0 * horizon))

    np.testing.assert_allclose(
        transient_distribution(q, initial, horizon),
        [1.0 - expected_state_one, expected_state_one],
        atol=1e-11,
    )

    assert first_passage_probability(
        q, initial, [1], horizon
    ) == pytest.approx(
        1.0 - np.exp(-2.0 * horizon),
        abs=1e-11,
    )


def test_long_horizon_and_depletion_mapping() -> None:
    q = np.array([[-2.0, 2.0], [3.0, -3.0]])

    # A long horizon forces segmented uniformization.
    p = transient_distribution(q, [1.0, 0.0], 30.0)

    np.testing.assert_allclose(p, [0.6, 0.4], atol=1e-10)
    assert p.sum() == pytest.approx(1.0, abs=1e-10)

    assert liquidity_depletion_states(2, "bid") == (0, 1, 2)
    assert liquidity_depletion_states(2, "ask") == (0, 3, 6)
    assert liquidity_depletion_states(2, "both") == (0,)
    assert liquidity_depletion_states(2, "either") == (
        0, 1, 2, 3, 6
    )


def test_invalid_generator_is_rejected() -> None:
    invalid = np.array([[-2.0, 2.0], [-1.0, 1.0]])

    with pytest.raises(ValueError):
        validate_generator(invalid)

    with pytest.raises(ValueError):
        transient_distribution(invalid, [1.0, 0.0], 1.0)

    with pytest.raises(ValueError):
        first_passage_probability(
            np.array([[-2.0, 2.0], [3.0, -3.0]]),
            [1.0, 0.0],
            [2],
            1.0,
        )
