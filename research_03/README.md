
# Research 03 — Latency-Constrained Price Discovery and Formal Analysis of Executable Liquidity in Fragmented Markets

**Quassar Capital | Quantitative Market Microstructure Research**

## Research Objective

This research investigates how message transmission delays, venue processing schedules, and participant-specific information availability constrain executable liquidity in fragmented limit order markets.

The central distinction is between liquidity represented by a resting order and liquidity that a participant can actually execute against under a specified sequence of messages, cancellations, and market-data deliveries.

The framework combines deterministic price-time priority matching, explicit communication lifecycles, and finite enumeration of candidate execution policies. It provides a reproducible environment for analyzing execution races, venue-specific liquidity, and the consequences of delayed access to market information.

The implementation is a stylized, deterministic research model. It is not a calibrated exchange simulator, a model of optimal routing, or evidence of realized execution performance.

## Mathematical Framework

### Fragmented Venue Structure

Let V be a finite set of trading venues. Each venue v in V maintains an independent continuous limit order book with integer-valued prices and quantities.

An order is represented by its venue, owner, side, limit price, initial quantity, and remaining quantity. Matching follows price priority and then resting-order arrival priority.

For an incoming buy order, eligible resting sell orders have prices no greater than the incoming limit. For an incoming sell order, eligible resting buy orders have prices no less than the incoming limit.

Executions occur at resting-order prices. The model uses a deterministic venue processing order, with explicit priority and message-identifier tie-breaking.

Order identifiers are interpreted within their respective venues. Independent venue books do not share a consolidated execution queue.

### Order Conservation

For every accepted order i, the accounting identity is

q_initial(i) = q_remaining(i) + q_executed(i) + q_canceled(i).

All quantities are nonnegative integers.

The venue kernel verifies this identity after each processed message. Invalid submissions and unauthorized or infeasible cancellations are recorded as rejected messages.

This identity establishes internal quantity conservation for accepted orders. It does not establish completeness with respect to all exchange-specific order states or message types.

### Message Transmission and Processing

For each participant dispatch m, define three timestamps:

- t_send(m): message transmission time.
- t_receive(m): message receipt at the destination venue.
- t_process(m): venue processing time.

The admissible lifecycle satisfies

0 <= t_send(m) <= t_receive(m) <= t_process(m).

These timestamps are supplied explicitly. The implementation does not estimate network latency, infer physical routing paths, or simulate stochastic communication delays.

Venue execution is determined by processing order rather than the chronological order in which messages are supplied to the replay interface.

### Participant-Specific Information

A market-data observation o has a publication time, delivery time, originating venue, and intended participant.

Its lifecycle satisfies

0 <= t_publish(o) <= t_deliver(o).

A dispatch requiring observation o is admissible only when the observation was delivered to the sending participant no later than the dispatch time:

t_deliver(o) <= t_send(m).

This constraint prevents a candidate action from citing information that was not yet delivered to its owner.

Observations are exogenous metadata. Their economic contents are not generated from the simulated book, and the framework does not independently verify that a participant's decisions are functions only of its complete historical information set.

Consequently, observation-prerequisite validation is a necessary causal consistency check for declared dependencies, not a general proof of nonanticipativity.

## Executable Liquidity and Attainable Outcomes

### Candidate Execution Policies

A candidate policy is a finite, named sequence of participant-owned dispatches.

Let P be a finite collection of such candidates, E a fixed exogenous message trace, and O a fixed set of delivered observations.

Each candidate p in P is replayed independently against E and O, subject to message lifecycle and declared information-prerequisite constraints.

The exogenous trace remains unchanged across candidate evaluations.

This construction supports controlled comparisons of predefined actions under the same modeled market conditions. It does not optimize over all possible contingent strategies or all feasible future message schedules.

### Execution Outcome

For a participant, define the execution outcome as

X(p) = (B(p), S(p), C(p)),

where:

- B(p) is total executed buy quantity.
- S(p) is total executed sell quantity.
- C(p) is signed cash flow in integer price-tick times quantity units.

For fills executed at prices r_k with quantities q_k,

C(p) = sum_sell(r_k q_k) - sum_buy(r_k q_k).

Both incoming and resting fills belonging to the participant are included. A fill between a participant-owned order and an exogenous order contributes once to that participant's accounting.

Cash flow excludes fees, rebates, financing, inventory valuation, and other transaction-cost components.

### Finite Attainable Set

The modeled attainable execution set is

A(P; E, O) = {X(p) : p in P}.

Duplicate outcomes are removed while individual policy results remain available for inspection.

The set is conditional on the supplied candidate policies, venue rules, exogenous trace, observation metadata, and timestamps.

It is not a complete feasible-execution frontier over all admissible strategies. Selecting its most favorable element retrospectively would generally introduce hindsight and must not be interpreted as an implementable trading decision.

### Cancellation Races

A resting order may be executed before its cancellation is processed, or removed before a competing incoming order reaches the matching engine.

The model resolves these outcomes through deterministic venue processing order.

This permits explicit comparison of latency-dependent execution outcomes without assigning probabilistic fill rates or assuming that displayed liquidity remains available until a participant's order arrives.

## Computational Implementation

| Component | Responsibility |
| --- | --- |
| `python/venue_kernel.py` | Deterministic price-time matching, cancellations, execution records, and order conservation |
| `python/latency_model.py` | Message lifecycles, observation delivery constraints, and independent venue replay |
| `python/executability.py` | Finite candidate-policy evaluation and attainable execution outcome construction |
| `tests/test_latency_execution.py` | Deterministic analytical reference tests |
| `.github/workflows/research-03-ci.yml` | Independent automated scientific validation at the repository root |

The implementation uses Python and integer arithmetic for prices, quantities, timestamps, and execution cash flows.

No external market-data feed, exchange gateway, proprietary routing logic, or production execution system is required.

## Analytical Reference Cases

The scientific validation suite covers eight deterministic cases:

1. Price-time priority and partial execution against multiple resting orders.
2. Cancellation-before-execution and execution-before-cancellation races.
3. Partial cancellation, ownership validation, and quantity conservation.
4. Independent venue books and venue-local execution.
5. Market-data delivery prerequisites and message lifecycle consistency.
6. Latency-dependent attainable outcomes under a fixed exogenous trace.
7. Venue-specific execution accounting and cash-flow consistency.
8. Duplicate policy-name and message-identifier rejection.

These tests establish agreement with specified reference cases. They do not constitute exhaustive verification of every possible message trace or exchange behavior.

## Reproducibility

From the repository root, install the focused test dependency:

```bash
python -m pip install pytest
```

Run the scientific validation suite:

```bash
python -m pytest -q research_03/tests/test_latency_execution.py
```

The dedicated GitHub Actions workflow executes the same test file on the Research 03 branch and qualifying pull requests.

All reference scenarios use synthetic orders, deterministic event times, and explicit expected outcomes.

## Scope and Limitations

### Market Mechanisms

The matching kernel represents a simplified continuous limit order book with limit submissions and cancellations.

It does not model hidden liquidity, midpoint orders, pegged orders, exchange auctions, order modifications, self-trade prevention, fee schedules, venue-specific priority exceptions, or regulatory routing obligations.

### Latency Representation

Communication and processing delays are externally specified. No stochastic latency distribution, congestion model, clock-synchronization error, or hardware timestamp uncertainty is estimated.

### Information and Strategy

The framework checks explicitly declared observation prerequisites. It does not construct complete information filtrations or prove that a policy is nonanticipative across alternative future states.

Candidate policies are predefined, finite action sequences rather than adaptive decision rules.

### Price Discovery

The research title identifies latency-constrained price discovery as the broader subject of investigation.

The present implementation measures execution outcomes under specified order-book states and event sequences. It does not estimate informational price discovery, permanent price impact, cross-venue price leadership, or convergence to a fundamental value.

### Empirical Interpretation

No market-data calibration, transaction-cost estimation, empirical fill-probability inference, or predictive validation is included.

Results are conditional on the modeled event trace and cannot be generalized to live market conditions without additional data, identification assumptions, and validation.

## Relationship to Earlier Research

Research 01 addresses quantitative market microstructure methods and computational implementations.

Research 02 examines state-dependent order book dynamics through finite-state continuous-time Markov models, spectral diagnostics, and liquidity-depletion probabilities.

Research 03 instead focuses on deterministic message ordering, causal communication constraints, and finite attainable execution outcomes across independent venues.

The investigations are methodologically distinct. Research 03 does not modify or depend on the scientific implementations of Research 01 or Research 02.

## Scientific Integrity

The research separates displayed liquidity, modeled executable quantity, and economically realizable execution.

Its results are finite, conditional, and reproducible within the specified assumptions. Analytical reference tests establish consistency with selected deterministic cases, not empirical accuracy or production readiness.

No proprietary trading strategies, confidential market data, investment signals, or live execution infrastructure are disclosed.
