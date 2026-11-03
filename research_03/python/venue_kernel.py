
"""Deterministic price-time matching and cancellation for a single venue."""

from dataclasses import dataclass
from typing import Literal

Side = Literal["buy", "sell"]
Kind = Literal["submit", "cancel"]


@dataclass(frozen=True)
class Message:
    message_id: str
    kind: Kind
    owner: str
    order_id: str
    processing_time: int
    priority: int
    side: Side | None = None
    price: int | None = None
    quantity: int | None = None


@dataclass(frozen=True)
class Fill:
    incoming_id: str
    resting_id: str
    price: int
    quantity: int
    processing_time: int


@dataclass
class _Order:
    owner: str
    side: Side
    price: int
    initial: int
    remaining: int
    executed: int = 0
    canceled: int = 0
    sequence: int = 0


class VenueBook:
    """A finite, integer-valued, deterministic continuous limit order book."""

    def __init__(self) -> None:
        self.orders: dict[str, _Order] = {}
        self.fills: list[Fill] = []
        self.rejections: list[str] = []
        self._seen_messages: set[str] = set()
        self._sequence = 0

    def replay(self, messages: list[Message]) -> None:
        """Process a finite trace in explicit venue processing order."""
        keys = [(m.processing_time, m.priority, m.message_id) for m in messages]
        if any(not isinstance(m.processing_time, int) or isinstance(m.processing_time, bool)
               or m.processing_time < 0 or not isinstance(m.priority, int)
               or isinstance(m.priority, bool) or m.priority < 0 for m in messages):
            raise ValueError("Processing times and priorities must be nonnegative integers")
        if len({m.message_id for m in messages}) != len(messages):
            raise ValueError("Duplicate message identifier in trace")
        if any(m.message_id in self._seen_messages for m in messages):
            raise ValueError("Message identifier was already processed")
        for _, m in sorted(zip(keys, messages), key=lambda pair: pair[0]):
            self._seen_messages.add(m.message_id)
            if m.kind == "submit":
                self._submit(m)
            elif m.kind == "cancel":
                self._cancel(m)
            else:
                self.rejections.append(m.message_id)
            self.assert_conservation()

    def _submit(self, m: Message) -> None:
        if (not m.owner or not m.order_id or m.order_id in self.orders
                or m.side not in ("buy", "sell")
                or type(m.price) is not int or m.price <= 0
                or type(m.quantity) is not int or m.quantity <= 0):
            self.rejections.append(m.message_id)
            return
        incoming = _Order(m.owner, m.side, m.price, m.quantity, m.quantity)
        self.orders[m.order_id] = incoming
        opposite = "sell" if m.side == "buy" else "buy"
        eligible = [
            (oid, order) for oid, order in self.orders.items()
            if oid != m.order_id and order.side == opposite and order.remaining > 0
            and (order.price <= m.price if m.side == "buy" else order.price >= m.price)
        ]
        eligible.sort(key=lambda item: (
            item[1].price if m.side == "buy" else -item[1].price,
            item[1].sequence,
        ))
        for resting_id, resting in eligible:
            if incoming.remaining == 0:
                break
            amount = min(incoming.remaining, resting.remaining)
            incoming.remaining -= amount
            incoming.executed += amount
            resting.remaining -= amount
            resting.executed += amount
            self.fills.append(Fill(m.order_id, resting_id, resting.price, amount,
                                   m.processing_time))
        self._sequence += 1
        incoming.sequence = self._sequence

    def _cancel(self, m: Message) -> None:
        order = self.orders.get(m.order_id)
        if (order is None or m.owner != order.owner or order.remaining == 0
                or m.quantity is not None and (
                    type(m.quantity) is not int or not 0 < m.quantity <= order.remaining
                )):
            self.rejections.append(m.message_id)
            return
        amount = order.remaining if m.quantity is None else m.quantity
        order.remaining -= amount
        order.canceled += amount

    def assert_conservation(self) -> None:
        for order in self.orders.values():
            assert order.initial == order.remaining + order.executed + order.canceled
            assert min(order.remaining, order.executed, order.canceled) >= 0

    def snapshot(self) -> tuple[tuple[str, int, int, int], ...]:
        """Return stable, public accounting fields for independent verification."""
        return tuple(sorted((oid, o.remaining, o.executed, o.canceled)
                            for oid, o in self.orders.items()))
