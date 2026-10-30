
"""Transient probability and liquidity-depletion analysis for finite CTMCs.

Uniformization preserves stochastic structure and avoids eigendecomposition.
Absorbing target states yield finite-horizon first-passage probabilities.
All calculations are conditional on the supplied Markov generator; they
are not empirical forecasts or calibrated trading-risk estimates.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _generator(values: ArrayLike) -> NDArray[np.float64]:
    """Validate a finite continuous-time Markov generator."""

    q = np.asarray(values, dtype=np.float64)

    if q.ndim != 2 or q.shape[0] < 2 or q.shape[0] != q.shape[1]:
        raise ValueError("generator must be a square matrix of size >= 2")

    if not np.all(np.isfinite(q)):
        raise ValueError("generator must be finite")

    scale = max(1.0, float(np.max(np.abs(q))))
    off = q.copy()
    np.fill_diagonal(off, 0.0)

    if (
        np.any(off < 0.0)
        or np.any(np.diag(q) > 0.0)
        or np.max(np.abs(q.sum(axis=1))) > 1e-12 * scale
    ):
        raise ValueError("invalid continuous-time Markov generator")

    return q


def _distribution(
    initial: ArrayLike,
    dimension: int,
) -> NDArray[np.float64]:
    """Validate a probability distribution over the state space."""

    p = np.asarray(initial, dtype=np.float64)

    if p.shape != (dimension,) or not np.all(np.isfinite(p)):
        raise ValueError("invalid initial distribution")

    if np.any(p < 0.0) or not np.isclose(p.sum(), 1.0, atol=1e-12):
        raise ValueError("initial distribution must be nonnegative and sum to one")

    return p.copy()


def _targets(targets: Iterable[int], dimension: int) -> tuple[int, ...]:
    """Validate target indices without accepting duplicate states."""

    selected = tuple(targets)

    if (
        not selected
        or any(
            isinstance(i, bool)
            or not isinstance(i, (int, np.integer))
            or i < 0
            or i >= dimension
            for i in selected
        )
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("targets must be distinct valid state indices")

    return selected


def _uniformization_step(
    p: NDArray[np.float64],
    transition: NDArray[np.float64],
    mean: float,
    tolerance: float,
) -> NDArray[np.float64]:
    """Poisson-weighted stochastic propagation over one time interval.

    Each interval has mean <= 40, preventing underflow in the initial
    Poisson weight. The omitted Poisson tail bounds truncation error.
    """

    weight = math.exp(-mean)
    cumulative = weight
    current = p.copy()
    result = weight * current

    count = 0

    while max(0.0, 1.0 - cumulative) > tolerance:
        count += 1
        weight *= mean / count
        current = current @ transition
        result += weight * current
        cumulative += weight

        if count > 1000:
            raise ArithmeticError("Poisson uniformization did not converge")

    if not np.all(np.isfinite(result)):
        raise ArithmeticError("nonfinite transient distribution")

    if np.min(result) < -1e-12:
        raise ArithmeticError("negative transient probability")

    return np.maximum(result, 0.0)


def transient_distribution(
    generator: ArrayLike,
    initial: ArrayLike,
    horizon: float,
    tolerance: float = 1e-12,
) -> NDArray[np.float64]:
    """Compute p(0) exp(Q t) using stable, segmented uniformization.

    The total error is bounded by the sum of the Poisson truncation
    tolerances, apart from floating-point accumulation and input error.
    """

    q = _generator(generator)
    p = _distribution(initial, len(q))

    if not np.isfinite(horizon) or horizon < 0.0:
        raise ValueError("horizon must be finite and nonnegative")

    if not np.isfinite(tolerance) or not 0.0 < tolerance < 1e-6:
        raise ValueError("tolerance must lie strictly between zero and 1e-6")

    if horizon == 0.0:
        return p

    rate = float(np.max(-np.diag(q)))

    if rate == 0.0:
        return p

    expected_jumps = rate * horizon

    if not np.isfinite(expected_jumps):
        raise ValueError("rate-horizon product exceeds numeric range")

    segments = max(1, math.ceil(expected_jumps / 40.0))

    if segments > 100_000:
        raise ValueError("time horizon requires excessive uniformization steps")

    transition = np.eye(len(q)) + q / rate
    mean = expected_jumps / segments
    local_tolerance = tolerance / segments

    for _ in range(segments):
        p = _uniformization_step(
            p,
            transition,
            mean,
            local_tolerance,
        )

    return p


def absorbing_generator(
    generator: ArrayLike,
    targets: Iterable[int],
) -> NDArray[np.float64]:
    """Make selected states absorbing without changing other transitions."""

    q = _generator(generator)
    selected = _targets(targets, len(q))

    absorbed = q.copy()
    absorbed[list(selected), :] = 0.0

    return absorbed


def first_passage_probability(
    generator: ArrayLike,
    initial: ArrayLike,
    targets: Iterable[int],
    horizon: float,
    tolerance: float = 1e-12,
) -> float:
    """Probability of reaching the target set by the specified horizon."""

    q = _generator(generator)
    selected = _targets(targets, len(q))
    absorbed = absorbing_generator(q, selected)

    probabilities = transient_distribution(
        absorbed,
        initial,
        horizon,
        tolerance,
    )

    probability = float(np.sum(probabilities[list(selected)]))

    if probability < -1e-10 or probability > 1.0 + 1e-10:
        raise ArithmeticError("invalid first-passage probability")

    return min(1.0, max(0.0, probability))


def liquidity_depletion_states(
    cap: int,
    side: str = "either",
) -> tuple[int, ...]:
    """Identify depleted queue states in a lexicographically indexed book.

    State ordering must be (bid_depth, ask_depth), with ask_depth varying
    fastest, matching QueueModel.states in state_dependent_book.py.
    """

    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("cap must be a positive integer")

    if side not in {"bid", "ask", "either", "both"}:
        raise ValueError("side must be bid, ask, either, or both")

    selected = []

    for bid in range(cap + 1):
        for ask in range(cap + 1):
            depleted = {
                "bid": bid == 0,
                "ask": ask == 0,
                "either": bid == 0 or ask == 0,
                "both": bid == 0 and ask == 0,
            }

            if depleted[side]:
                selected.append(bid * (cap + 1) + ask)

    return tuple(selected)
