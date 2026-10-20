"""Statistical diagnostics; explicit assumptions and reproducible parameterization."""
from dataclasses import dataclass
import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class HawkesSpecification:
    """Exponential-kernel multivariate Hawkes model, alpha[target, source]."""
    baseline: tuple[float, ...]
    excitation: tuple[tuple[float, ...], ...]
    decay: float

    def __post_init__(self) -> None:
        mu = np.asarray(self.baseline, dtype=float)
        a = np.asarray(self.excitation, dtype=float)
        if mu.ndim != 1 or mu.size == 0 or not np.all(np.isfinite(mu)) or np.any(mu <= 0):
            raise ValueError("baseline must be finite and strictly positive")
        if a.shape != (mu.size, mu.size) or not np.all(np.isfinite(a)) or np.any(a < 0):
            raise ValueError("excitation must be finite, nonnegative and square")
        if not np.isfinite(self.decay) or self.decay <= 0:
            raise ValueError("decay must be positive and finite")

    @property
    def branching_matrix(self) -> np.ndarray:
        return np.asarray(self.excitation, dtype=float) / self.decay

    @property
    def stationary(self) -> bool:
        return branching_radius(self.branching_matrix) < 1.0

    def stationary_mean_intensity(self) -> np.ndarray:
        if not self.stationary:
            raise ValueError("stationary mean is not defined for non-subcritical model")
        return np.linalg.solve(np.eye(len(self.baseline)) - self.branching_matrix,
                               np.asarray(self.baseline))


def branching_radius(matrix: ArrayLike) -> float:
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or a.size == 0 or not np.all(np.isfinite(a)):
        raise ValueError("expected finite square matrix")
    return float(np.max(np.abs(np.linalg.eigvals(a))))


def time_rescaling(events: ArrayLike, baseline: float, excitation: float,
                   decay: float, end: float | None = None) -> np.ndarray:
    """Integrated conditional intensities between successive univariate events.

    Starts with empty prehistory at t=0. Returns one compensator increment per event.
    If end is supplied it is validated but does not append a censored terminal interval.
    """
    t = np.asarray(events, dtype=float)
    if t.ndim != 1 or not np.all(np.isfinite(t)) or np.any(t <= 0) or np.any(np.diff(t) <= 0):
        raise ValueError("events must be strictly increasing positive finite times")
    if not np.isfinite(baseline) or baseline <= 0 or not np.isfinite(excitation) or excitation < 0 or not np.isfinite(decay) or decay <= 0:
        raise ValueError("invalid Hawkes parameters")
    if end is not None and (not np.isfinite(end) or (t.size and end < t[-1])):
        raise ValueError("end precedes last event")
    result = np.empty(t.size)
    last = 0.0
    residual = 0.0
    for i, now in enumerate(t):
        delta = now - last
        result[i] = baseline * delta + residual * (-np.expm1(-decay * delta)) / decay
        residual = residual * np.exp(-decay * delta) + excitation
        last = now
    return result


def impact_curve(signed_volume: ArrayLike, coefficient: float, exponent: float = 0.5) -> np.ndarray:
    """Phenomenological signed power-law impact, not a calibrated execution model."""
    v = np.asarray(signed_volume, dtype=float)
    if not np.all(np.isfinite(v)) or not np.isfinite(coefficient) or coefficient < 0 or not np.isfinite(exponent) or not 0 < exponent <= 1:
        raise ValueError("invalid impact parameters or signed volumes")
    return coefficient * np.sign(v) * np.abs(v) ** exponent
