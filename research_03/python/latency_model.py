
"""Causal message delivery and independent fragmented-venue replay."""

from dataclasses import dataclass
from typing import Mapping

from research_03.python.venue_kernel import Fill, Message, VenueBook


@dataclass(frozen=True)
class Observation:
    """A market-data update published by a venue and delivered to a participant."""

    observation_id: str
    participant: str
    venue: str
    published_at: int
    delivered_at: int


@dataclass(frozen=True)
class Dispatch:
    """An inbound message with an explicit causal information prerequisite."""

    venue: str
    message: Message
    sent_at: int
    received_at: int
    required_observations: tuple[str, ...] = ()


@dataclass(frozen=True)
class VenueResult:
    venue: str
    orders: tuple[tuple[str, int, int, int], ...]
    fills: tuple[Fill, ...]
    rejections: tuple[str, ...]


class LatencyScenario:
    """Validate message lifecycles and replay independently processed venues."""

    def __init__(self, venues: tuple[str, ...]) -> None:
        if not venues or any(not isinstance(v, str) or not v for v in venues):
            raise ValueError("Venue identifiers must be nonempty strings")
        if len(set(venues)) != len(venues):
            raise ValueError("Venue identifiers must be unique")
        self.venues = venues

    @staticmethod
    def _time(value: int) -> bool:
        return type(value) is int and value >= 0

    def run(
        self,
        dispatches: tuple[Dispatch, ...],
        observations: tuple[Observation, ...] = (),
    ) -> Mapping[str, VenueResult]:
        """Replay a finite scenario with explicitly supplied processing times.

        Observations are exogenous published updates. Their contents are not
        inferred from the simulated venue state. An action that requires an
        observation must be sent no earlier than its delivery to the sender.
        """
        known: dict[str, Observation] = {}
        for obs in observations:
            if (not obs.observation_id or not obs.participant
                    or obs.venue not in self.venues
                    or not self._time(obs.published_at)
                    or not self._time(obs.delivered_at)
                    or obs.delivered_at < obs.published_at):
                raise ValueError("Invalid observation lifecycle")
            if obs.observation_id in known:
                raise ValueError("Duplicate observation identifier")
            known[obs.observation_id] = obs

        by_venue: dict[str, list[Message]] = {v: [] for v in self.venues}
        seen_messages: set[str] = set()
        for dispatch in dispatches:
            msg = dispatch.message
            if dispatch.venue not in by_venue:
                raise ValueError("Unknown destination venue")
            if (not msg.message_id or not msg.owner
                    or msg.message_id in seen_messages):
                raise ValueError("Invalid or duplicate message identifier")
            seen_messages.add(msg.message_id)
            if (not self._time(dispatch.sent_at)
                    or not self._time(dispatch.received_at)
                    or not self._time(msg.processing_time)
                    or not self._time(msg.priority)
                    or dispatch.sent_at > dispatch.received_at
                    or dispatch.received_at > msg.processing_time):
                raise ValueError("Invalid message lifecycle")
            if len(set(dispatch.required_observations)) != len(dispatch.required_observations):
                raise ValueError("Repeated observation prerequisite")
            for identifier in dispatch.required_observations:
                obs = known.get(identifier)
                if (obs is None or obs.participant != msg.owner
                        or obs.delivered_at > dispatch.sent_at):
                    raise ValueError("Unavailable information prerequisite")
            by_venue[dispatch.venue].append(msg)

        results: dict[str, VenueResult] = {}
        for venue in self.venues:
            book = VenueBook()
            book.replay(by_venue[venue])
            results[venue] = VenueResult(
                venue=venue,
                orders=book.snapshot(),
                fills=tuple(book.fills),
                rejections=tuple(book.rejections),
            )
        return results
