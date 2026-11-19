"""Pump-logs JSON events that Tandem's event schema does not describe.

events.json and custom_events.json define an event by its byte layout, and
events.py is generated from them. The events here are only known from the
pump-logs JSON (the endpoint returns them when no eventCodes filter is sent),
so they have no byte layout to declare and are written by hand. A binary
event with one of these ids still comes through as a RawEvent.
"""
from dataclasses import dataclass, field
from typing import Optional

from .raw_event import RawEvent, BaseEvent


@dataclass
class PumpStatusSnapshot(BaseEvent):
    """9: a status snapshot the pump writes about 20 times a day while it is
    in use, never overnight (seen on a t:slim X2, software 7.8.1). Tandem's
    schema has no name for it; the name here is ours.

    insulin is what is left in the cartridge, in units, in the pump's own
    5-unit steps: it jumps to the fill volume when a cartridge is filled. abc
    is the battery percent, the same figure as LID_DAILY_BASAL's abc.

    The event also carries iob, but in tenths of a unit; LID_DAILY_BASAL has
    it as a float every ten minutes, so that one is used and this one is
    kept only in props.
    """
    ID = 9
    NAME = "PUMP_STATUS_SNAPSHOT"

    raw: RawEvent
    insulin: Optional[float] # units
    abc: Optional[int] # percent
    props: dict = field(default_factory=dict)

    @staticmethod
    def build_from_json(event):
        props = event.get("eventProperties") or {}
        return PumpStatusSnapshot(
            raw = RawEvent.build_from_json(event),
            insulin = props.get("insulin", None),
            abc = props.get("abc", None),
            props = dict(props),
        )

    @property
    def eventTimestamp(self):
        return self.raw.timestamp

    @property
    def seqNum(self):
        return self.raw.seqNum

    @property
    def eventId(self):
        return self.ID

    def todict(self):
        return dict(
            id=self.ID,
            name=self.NAME,
            seqNum=self.seqNum,
            eventTimestamp=str(self.eventTimestamp),
            insulin=self.insulin,
            abc=self.abc,
            props=self.props,
        )


JSON_EVENT_IDS = {
    PumpStatusSnapshot.ID: PumpStatusSnapshot,
}
