
"""Finite ex post attainable execution sets under explicit causal dispatch constraints."""

from dataclasses import dataclass

from research_03.python.latency_model import Dispatch, LatencyScenario, Observation


@dataclass(frozen=True)
class CandidatePolicy:
    """A named, predeclared sequence of participant dispatches."""

    name: str
    dispatches: tuple[Dispatch, ...]


@dataclass(frozen=True, order=True)
class ExecutionOutcome:
    """Executed lots and signed cash flow in integer tick-lot units."""

    bought: int
    sold: int
    cash_flow: int


@dataclass(frozen=True)
class PolicyResult:
    policy: str
    outcome: ExecutionOutcome


@dataclass(frozen=True)
class AttainableSet:
    """Policy outcomes and their distinct attainable price-quantity projections."""

    policies: tuple[PolicyResult, ...]
    outcomes: tuple[ExecutionOutcome, ...]


def enumerate_attainable(
    scenario: LatencyScenario,
    participant: str,
    exogenous: tuple[Dispatch, ...],
    policies: tuple[CandidatePolicy, ...],
    observations: tuple[Observation, ...] = (),
    *,
    max_policies: int = 256,
) -> AttainableSet:
    """Replay finite predeclared alternatives against the same exogenous trace.

    Each candidate is validated by LatencyScenario, including its declared
    observation prerequisites. This is ex post scenario enumeration, not a
    proof that a candidate policy is nonanticipative under every possible
    future state or that its best outcome is knowable before execution.
    """
    if not isinstance(participant, str) or not participant:
        raise ValueError("Participant must be a nonempty string")
    if type(max_policies) is not int or max_policies < 1:
        raise ValueError("max_policies must be a positive integer")
    if not policies or len(policies) > max_policies:
        raise ValueError("Policy count must be between one and max_policies")
    if len({policy.name for policy in policies}) != len(policies):
        raise ValueError("Policy names must be unique")
    if any(not isinstance(policy.name, str) or not policy.name for policy in policies):
        raise ValueError("Policy names must be nonempty strings")
    if any(dispatch.message.owner == participant for dispatch in exogenous):
        raise ValueError("Exogenous dispatches cannot belong to the evaluated participant")

    results: list[PolicyResult] = []
    for policy in policies:
        if any(dispatch.message.owner != participant for dispatch in policy.dispatches):
            raise ValueError("Every policy dispatch must belong to the participant")
        exogenous_orders = {
            (dispatch.venue, dispatch.message.order_id)
            for dispatch in exogenous
            if dispatch.message.kind == "submit"
        }
        policy_orders = [
            (dispatch.venue, dispatch.message.order_id)
            for dispatch in policy.dispatches
            if dispatch.message.kind == "submit"
        ]
        if len(set(policy_orders)) != len(policy_orders):
            raise ValueError("Duplicate policy submission order identifier within a venue")
        if exogenous_orders.intersection(policy_orders):
            raise ValueError("Policy and exogenous submissions share an order identifier")
        combined = exogenous + policy.dispatches
        replay = scenario.run(combined, observations)
        # Venue-local order IDs are not assumed to be globally unique.
        submitted_by_venue = {
            (dispatch.venue, dispatch.message.order_id): dispatch.message
            for dispatch in policy.dispatches
            if dispatch.message.kind == "submit"
        }
        bought = sold = cash_flow = 0
        for venue, venue_result in replay.items():
            for fill in venue_result.fills:
                for order_id in (fill.incoming_id, fill.resting_id):
                    owned = submitted_by_venue.get((venue, order_id))
                    if owned is None:
                        continue
                    if owned.side == "buy":
                        bought += fill.quantity
                        cash_flow -= fill.quantity * fill.price
                    elif owned.side == "sell":
                        sold += fill.quantity
                        cash_flow += fill.quantity * fill.price
                    else:
                        raise AssertionError("An executed order must have a valid side")
        results.append(PolicyResult(policy.name, ExecutionOutcome(bought, sold, cash_flow)))

    return AttainableSet(
        policies=tuple(results),
        outcomes=tuple(sorted({result.outcome for result in results})),
    )
