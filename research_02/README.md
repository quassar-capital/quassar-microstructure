
# Research 02 — State-Dependent Limit Order Book Dynamics

## Markov Generators, Spectral Analysis, and Liquidity Transitions

**Quassar Capital | Quantitative Market Microstructure Research**

## Research Objective

This research examines liquidity-state transitions through a finite-state, queue-reactive continuous-time Markov chain (CTMC). Bid and ask queue depths determine the system state, while state-dependent transition intensities govern queue replenishment and depletion.

The framework provides a reproducible mathematical environment for investigating stationary queue configurations, relaxation rates, mean first-passage times, and finite-horizon liquidity-depletion probabilities.

It is a stylized stochastic model, not a calibrated exchange simulator or a representation of live market conditions.

## Mathematical Framework

### State Space

For a maximum queue depth K, define the state space

S = {(b, a) : b, a in {0, ..., K}},

where b and a denote bid-side and ask-side queue depths.

The finite state space contains (K + 1)^2 configurations. States are indexed lexicographically, with ask depth varying fastest.

### Infinitesimal Generator

The CTMC is characterized by an infinitesimal generator Q.

For distinct states i and j, Q[i,j] represents a nonnegative transition intensity. Each diagonal entry satisfies

Q[i,i] = -sum(Q[i,j] for j != i).

Consequently, every generator row sums to zero.

Queue arrivals, cancellations, and executions determine admissible transitions. Arrival intensities respond to queue imbalance, while queue depletion depends on existing depth and model parameters.

The finite capacity restricts upward transitions at the queue boundary.

### Stationary Distribution

A stationary probability vector pi satisfies

pi Q = 0,
sum(pi) = 1.

The numerical implementation solves the corresponding constrained linear system and evaluates its residual.

A stationary solution describes long-run occupancy under the specified time-homogeneous generator. It does not independently establish empirical stationarity of observed market data.

### Spectral Diagnostics

The generator spectrum provides information about asymptotic relaxation.

For an ergodic finite-state CTMC, the spectral gap is determined by the nonzero eigenvalue whose real part lies closest to zero.

The implementation reports this real-part spectral gap. For nonnormal generators, the gap alone does not provide a universal finite-time mixing bound.

### Mean First-Passage Times

For a selected target set A, the expected time to first reach A satisfies a linear boundary-value problem.

For states outside A,

-Q_TT h = 1,

with h = 0 on A.

The implementation solves this system and verifies the linear residual.

Finite expected hitting times depend on the accessibility of the target set from the relevant states.

## Transient Probability Analysis

### Uniformization

Transient state probabilities are determined by

p(t) = p(0) exp(Qt).

The implementation uses uniformization, expressing the transition semigroup through a Poisson-weighted series of stochastic matrix powers.

Long horizons are partitioned into smaller intervals to control numerical underflow and Poisson truncation error.

This formulation avoids direct eigendecomposition for transient propagation.

### Absorbing-State Construction

A target set is made absorbing by replacing its generator rows with zeros.

The resulting absorbed CTMC retains the original transition intensities outside the target set.

The total absorbed-state probability at time t represents the probability of reaching the target set at least once by that horizon.

### Liquidity-Depletion Events

The model supports four target definitions:

- Bid depletion: bid queue depth equals zero.
- Ask depletion: ask queue depth equals zero.
- Either-side depletion: at least one queue depth equals zero.
- Joint depletion: both queue depths equal zero.

These are queue-state events under the model assumptions. They should not be interpreted directly as realized market crashes, execution failures, or observed exchange outages.

## Implementation

| Component | Responsibility |
| --- | --- |
| `python/state_dependent_book.py` | Generator construction, stationary distribution, spectral gap, and mean first-passage analysis |
| `python/liquidity_transitions.py` | Uniformization, absorbing-state dynamics, and finite-horizon depletion probabilities |
| `tests/test_markov_liquidity.py` | Analytical reference tests and structural validation |
| `.github/workflows/research-02-ci.yml` | Independent automated scientific validation, located at the repository root |

The numerical implementation uses Python and NumPy. This choice supports transparent inspection of the finite-state mathematical operators without introducing unnecessary implementation complexity.

## Reproducibility

From the repository root, install the scientific test dependencies:

```bash
python -m pip install numpy pytest
```

Execute the focused validation suite:

```bash
python -m pytest -q research_02/tests/test_markov_liquidity.py
```

The tests verify:

1. Generator consistency and stationary balance.
2. Analytical two-state stationary, spectral, and hitting-time references.
3. Transient probabilities and segmented long-horizon uniformization.
4. Liquidity-depletion indexing and invalid-generator rejection.

GitHub Actions executes the same scientific validation on the Research 02 branch and qualifying pull requests.

## Numerical Scope and Limitations

The current implementation uses dense NumPy matrices. Generator storage grows quadratically with the number of states, while dense spectral and linear-system operations can scale cubically in state-space dimension.

The framework is therefore intended for finite, computationally tractable queue capacities.

Model parameters are illustrative unless independently estimated from suitable point-in-time market data. No empirical calibration, predictive accuracy, live execution performance, or investment result is claimed.

The spectral gap is a model diagnostic, not a complete characterization of nonnormal transient amplification.

Rare-event analysis is represented through exact finite-state first-passage formulations and finite-horizon absorption probabilities. No large-deviation asymptotic estimator or importance-sampling acceleration is claimed.

## Relationship to Research 01

Research 01 investigates self-exciting order flow, Hawkes dynamics, impact behavior, and deterministic price-time priority matching.

Research 02 examines state-dependent queue dynamics through Markov generators and associated spectral and first-passage operators.

The two investigations are mathematically distinct and preserve independent research implementations.

## Scientific Integrity

Results are conditional on the specified stochastic model, state-space truncation, and numerical tolerances.

Reproducibility, explicit assumptions, analytical reference cases, and separation between mathematical model outputs and empirical market claims are fundamental requirements of this research.
