
"""Finite-state queue-reactive continuous-time Markov chain research kernel.

A finite, capped two-queue model with reflecting boundaries for arrivals and
state-dependent queue depletion. This is a stylized liquidity model, not an
order matching engine or a calibrated market simulator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class QueueModel:
    """Two-sided queue CTMC; states (bid_depth, ask_depth), each in [0, cap]."""

    cap: int
    arrival: float
    cancellation: float
    execution: float
    imbalance_sensitivity: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.cap, bool) or not isinstance(self.cap, int) or self.cap < 1:
            raise ValueError("cap must be a positive integer")

        values = (
            self.arrival,
            self.cancellation,
            self.execution,
            self.imbalance_sensitivity,
        )

        if not all(np.isfinite(v) for v in values):
            raise ValueError("rates and sensitivity must be finite")

        if self.arrival <= 0 or self.cancellation < 0 or self.execution < 0:
            raise ValueError("invalid event rates")

        if not 0 <= self.imbalance_sensitivity <= 1:
            raise ValueError("imbalance_sensitivity must lie in [0, 1]")

    @property
    def states(self) -> list[tuple[int, int]]:
        return [
            (b, a)
            for b in range(self.cap + 1)
            for a in range(self.cap + 1)
        ]

    def generator(self) -> NDArray[np.float64]:
        """Row generator Q with nonnegative off-diagonals and Q1 = 0."""

        states = self.states
        index = {state: i for i, state in enumerate(states)}
        q = np.zeros((len(states), len(states)), dtype=float)

        for i, (b, a) in enumerate(states):
            imbalance = (b - a) / max(b + a, 1)

            arrivals = (
                self.arrival * (
                    1 - self.imbalance_sensitivity * imbalance
                ),
                self.arrival * (
                    1 + self.imbalance_sensitivity * imbalance
                ),
            )

            transitions = []

            if b < self.cap:
                transitions.append(((b + 1, a), arrivals[0]))

            if a < self.cap:
                transitions.append(((b, a + 1), arrivals[1]))

            if b > 0:
                transitions.append((
                    (b - 1, a),
                    self.cancellation * b + self.execution,
                ))

            if a > 0:
                transitions.append((
                    (b, a - 1),
                    self.cancellation * a + self.execution,
                ))

            for target, rate in transitions:
                q[i, index[target]] += rate

            q[i, i] = -sum(rate for _, rate in transitions)

        return q


def validate_generator(
    generator: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Validate the structural properties of a finite CTMC generator."""

    q = np.asarray(generator, dtype=float)

    if q.ndim != 2 or q.shape[0] != q.shape[1] or q.shape[0] < 2:
        raise ValueError("expected square generator of dimension at least two")

    if not np.all(np.isfinite(q)):
        raise ValueError("generator must contain finite values")

    scale = max(1.0, float(np.max(np.abs(q))))

    if np.max(np.abs(q.sum(axis=1))) > 1e-12 * scale:
        raise ValueError("invalid generator row sums")

    off = q.copy()
    np.fill_diagonal(off, 0.0)

    if np.any(off < 0) or np.any(np.diag(q) > 0):
        raise ValueError("invalid generator signs")

    return q


def stationary_distribution(
    generator: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Solve pi Q = 0 and sum(pi) = 1 for a unique stationary law."""

    q = validate_generator(generator)

    a = q.T.copy()
    a[-1, :] = 1.0

    rhs = np.zeros(len(q))
    rhs[-1] = 1.0

    try:
        pi = np.linalg.solve(a, rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "stationary distribution is not uniquely determined"
        ) from exc

    scale = max(1.0, float(np.max(np.abs(q))))

    if (
        np.min(pi) < -1e-10
        or np.max(np.abs(pi @ q)) > 1e-9 * scale
    ):
        raise ValueError("invalid stationary solution")

    pi = np.maximum(pi, 0.0)
    return pi / pi.sum()


def mean_first_passage(
    generator: NDArray[np.float64],
    targets: list[int],
) -> NDArray[np.float64]:
    """Expected hitting times obtained from -Q_TT h = 1."""

    q = validate_generator(generator)
    n = q.shape[0]

    if (
        not targets
        or any(
            not isinstance(i, int)
            or isinstance(i, bool)
            or i < 0
            or i >= n
            for i in targets
        )
    ):
        raise ValueError("invalid target states")

    target_set = set(targets)
    transient = [i for i in range(n) if i not in target_set]

    result = np.zeros(n)

    if transient:
        subgenerator = -q[np.ix_(transient, transient)]

        try:
            solution = np.linalg.solve(
                subgenerator,
                np.ones(len(transient)),
            )
        except np.linalg.LinAlgError as exc:
            raise ValueError(
                "some states may not reach the target set"
            ) from exc

        residual = subgenerator @ solution - 1.0

        if (
            np.any(solution < -1e-9)
            or np.max(np.abs(residual)) > 1e-8
        ):
            raise ValueError("invalid first-passage solution")

        result[transient] = np.maximum(solution, 0.0)

    return result


def spectral_gap(
    generator: NDArray[np.float64],
) -> float:
    """Return the asymptotic spectral decay gap of an ergodic finite CTMC."""

    q = validate_generator(generator)
    eigenvalues = np.linalg.eigvals(q)

    decay = np.sort(-eigenvalues.real)
    scale = max(1.0, float(np.max(np.abs(q))))

    if (
        abs(decay[0]) > 1e-9 * scale
        or decay[1] <= 1e-10 * scale
    ):
        raise ValueError("spectral gap is not resolved")

    return float(decay[1])
