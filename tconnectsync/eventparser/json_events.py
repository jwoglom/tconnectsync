"""
Build native eventparser objects from the Tandem Source "BFF" pump-logs JSON.

As of 2026-06-30 Tandem replaced the binary event blob returned by
``api/reports/reportsfacade/pumpevents/...`` with structured JSON from
``api/reports/bff/pump-logs/...`` (see issue #146). Each JSON event carries an
``eventCode``, a ``pumpDateTime``/``estimatedDateTime``, a ``sequenceNumber``,
and an ``eventProperties`` dict whose keys correspond -- up to camelCase and a
trailing ``Raw`` -- to the fields of the matching eventparser dataclass.

``build_event_from_json`` reconstructs the same typed objects the binary parser
produced, so the entire downstream sync pipeline is reused unchanged.
"""
import dataclasses
import logging

import arrow

from .events import EVENT_IDS
from .raw_event import RawEvent, TANDEM_EPOCH

logger = logging.getLogger(__name__)


def _synthetic_raw_event(evt):
    """A RawEvent carrying the event's timestamp and sequence number.

    ``RawEvent.timestamp`` interprets ``timestampRaw`` as "seconds since
    TANDEM_EPOCH expressed in the pump's local wall-clock" and relabels it to the
    configured timezone. The BFF ``pumpDateTime`` is exactly that naive local
    wall-clock, so we invert it back to the same ``timestampRaw`` and reproduce
    an identical instant to the binary path.
    """
    ts_raw = arrow.get(evt.get('pumpDateTime'), tzinfo='UTC').int_timestamp - TANDEM_EPOCH
    return RawEvent(
        source=0,
        id=evt.get('eventCode', 0),
        timestampRaw=ts_raw,
        seqNum=evt.get('sequenceNumber', 0),
        raw=b'',
    )


def _normalize(name):
    """Canonicalize a field/property name: drop a trailing ``Raw``, lowercase."""
    if name.endswith('Raw'):
        name = name[:-3]
    return name.lower()


def _coerce(value):
    """Fold an integer-bitmask array (e.g. ``[0, 5, 6]``) into a packed int."""
    if isinstance(value, list):
        try:
            return sum(1 << int(bit) for bit in value)
        except (TypeError, ValueError):
            return 0
    return value


_FIELD_MAP_CACHE = {}


def _field_map(cls):
    """``{normalized field name: actual field name}`` for an eventparser class."""
    cached = _FIELD_MAP_CACHE.get(cls)
    if cached is None:
        cached = {
            _normalize(f.name): f.name
            for f in dataclasses.fields(cls)
            if f.name != 'raw'
        }
        _FIELD_MAP_CACHE[cls] = cached
    return cached


def build_event_from_json(evt):
    """Return the eventparser object for a single BFF pump-logs event.

    Unknown event codes fall back to a bare ``RawEvent``, matching the binary
    eventparser's ``Event()`` behavior.
    """
    raw = _synthetic_raw_event(evt)
    cls = EVENT_IDS.get(evt.get('eventCode'))
    if cls is None:
        return raw

    properties = {
        _normalize(k): _coerce(v)
        for k, v in (evt.get('eventProperties') or {}).items()
    }
    kwargs = {'raw': raw}
    for norm_name, field_name in _field_map(cls).items():
        value = properties.get(norm_name)
        kwargs[field_name] = value if value is not None else 0
    return cls(**kwargs)


def build_events_from_json(body):
    """Build eventparser objects from a ``bff/pump-logs`` response body."""
    events = []
    for evt in (body or {}).get('events', []):
        try:
            events.append(build_event_from_json(evt))
        except Exception as e:
            logger.error("Failed to build event %s from BFF JSON: %s", evt.get('eventCode'), e)
    return events
