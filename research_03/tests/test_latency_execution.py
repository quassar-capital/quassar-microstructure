
"""Analytical reference tests for latency-constrained fragmented-market execution."""

import pytest

from research_03.python.executability import (
    CandidatePolicy,
    ExecutionOutcome,
    enumerate_attainable,
)
from research_03.python.latency_model import (
    Dispatch,
    LatencyScenario,
    Observation,
)
from research_03.python.venue_kernel import Message, VenueBook


def submit(identifier, owner, side, price, quantity, time, priority=0):
    return Message(
        identifier, "submit", owner, identifier, time, priority,
        side, price, quantity,
    )


def cancel(identifier, owner, order_id, time, quantity=None, priority=0):
    return Message(
        identifier, "cancel", owner, order_id, time, priority,
        quantity=quantity,
    )


def dispatch(venue, message, sent=0, received=None, required=()):
    if received is None:
        received = message.processing_time
    return Dispatch(venue, message, sent, received, required)


def test_price_time_priority_and_partial_execution():
    book = VenueBook()
    book.replay([
        submit("ask_late", "maker_b", "sell", 101, 4, 2),
        submit("ask_early", "maker_a", "sell", 101, 3, 1),
        submit("bid", "taker", "buy", 102, 5, 3),
    ])
    assert [(f.resting_id, f.price, f.quantity) for f in book.fills] == [
        ("ask_early", 101, 3),
        ("ask_late", 101, 2),
    ]
    assert dict((oid, (remaining, executed, canceled))
                for oid, remaining, executed, canceled in book.snapshot()) == {
        "ask_early": (0, 3, 0),
        "ask_late": (2, 2, 0),
        "bid": (0, 5, 0),
    }
    book.assert_conservation()


def test_cancellation_race_and_deterministic_tie_break():
    messages = [
        submit("ask", "maker", "sell", 100, 5, 0),
        cancel("cancel", "maker", "ask", 2, priority=0),
        submit("buy", "taker", "buy", 100, 5, 2, priority=1),
    ]
    book = VenueBook()
    book.replay(list(reversed(messages)))
    assert book.fills == []
    assert "buy" not in book.rejections
    assert ("ask", 0, 0, 5) in book.snapshot()

    competing = VenueBook()
    competing.replay([
        messages[0],
        submit("buy", "taker", "buy", 100, 5, 1),
        cancel("cancel", "maker", "ask", 2),
    ])
    assert len(competing.fills) == 1
    assert competing.fills[0].quantity == 5
    assert competing.rejections == ["cancel"]


def test_partial_cancellation_and_unauthorized_message():
    book = VenueBook()
    book.replay([
        submit("ask", "maker", "sell", 100, 7, 0),
        cancel("unauthorized", "other", "ask", 1, quantity=3),
        cancel("partial", "maker", "ask", 2, quantity=3),
    ])
    assert book.rejections == ["unauthorized"]
    assert book.snapshot() == (("ask", 4, 0, 3),)
    book.assert_conservation()


def test_venue_isolation_and_latency_ordering():
    scenario = LatencyScenario(("A", "B"))
    result = scenario.run((
        dispatch("A", submit("a1", "maker", "sell", 100, 2, 1)),
        dispatch("B", submit("b1", "maker", "sell", 100, 2, 1)),
        dispatch("A", submit("a2", "taker", "buy", 100, 2, 3)),
    ))
    assert len(result["A"].fills) == 1
    assert result["A"].fills[0].quantity == 2
    assert result["B"].fills == ()
    assert result["B"].orders == (("b1", 2, 0, 0),)


def test_information_causality_and_message_lifecycle():
    scenario = LatencyScenario(("A",))
    observation = Observation("quote", "taker", "A", 2, 7)
    action = submit("buy", "taker", "buy", 100, 1, 10)

    valid = dispatch("A", action, sent=7, received=9, required=("quote",))
    result = scenario.run((valid,), (observation,))
    assert result["A"].orders == (("buy", 1, 0, 0),)

    early = dispatch("A", action, sent=6, received=9, required=("quote",))
    with pytest.raises(ValueError, match="Unavailable information"):
        scenario.run((early,), (observation,))

    impossible = dispatch("A", action, sent=8, received=11)
    with pytest.raises(ValueError, match="Invalid message lifecycle"):
        scenario.run((impossible,), (observation,))


def test_attainable_set_with_latency_dependent_fill():
    scenario = LatencyScenario(("A",))
    resting = dispatch(
        "A", submit("ask", "maker", "sell", 100, 3, 1),
    )
    cancellation = dispatch(
        "A", cancel("withdraw", "maker", "ask", 5),
    )

    fast = CandidatePolicy("fast", (
        dispatch("A", submit("fast_buy", "taker", "buy", 100, 3, 3)),
    ))
    slow = CandidatePolicy("slow", (
        dispatch("A", submit("slow_buy", "taker", "buy", 100, 3, 6)),
    ))

    attainable = enumerate_attainable(
        scenario, "taker", (resting, cancellation), (fast, slow),
    )
    assert attainable.policies[0].outcome == ExecutionOutcome(3, 0, -300)
    assert attainable.policies[1].outcome == ExecutionOutcome(0, 0, 0)
    assert attainable.outcomes == (
        ExecutionOutcome(0, 0, 0),
        ExecutionOutcome(3, 0, -300),
    )


def test_attainable_set_respects_venue_specific_identity():
    scenario = LatencyScenario(("A", "B"))
    exogenous = (
        dispatch("A", submit("ask_a", "maker", "sell", 100, 2, 1)),
        dispatch("B", submit("ask_b", "maker", "sell", 105, 2, 1)),
    )
    policy = CandidatePolicy("route_b", (
        dispatch("B", submit("buy", "taker", "buy", 105, 2, 2)),
    ))
    result = enumerate_attainable(scenario, "taker", exogenous, (policy,))
    assert result.outcomes == (ExecutionOutcome(2, 0, -210),)


def test_invalid_policy_and_duplicate_messages():
    scenario = LatencyScenario(("A",))
    message = submit("buy", "taker", "buy", 100, 1, 1)

    with pytest.raises(ValueError, match="Policy names must be unique"):
        enumerate_attainable(
            scenario, "taker", (),
            (
                CandidatePolicy("same", (dispatch("A", message),)),
                CandidatePolicy("same", ()),
            ),
        )

    with pytest.raises(ValueError, match="duplicate message"):
        scenario.run((
            dispatch("A", message),
            dispatch("A", message),
        ))
