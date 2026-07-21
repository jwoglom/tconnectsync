#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidMalfunctionActivated(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.fixture = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 6,
            "sequenceGroup": 0,
            "sequenceNumber": 500123,
            "pumpDateTime": "2026-05-16T00:07:00",
            "eventProperties": {"malfId": 7, "faultLocatorData": 8311, "param1": 42, "param2": 0},
            "estimatedDateTime": "2026-05-16T00:07:00Z",
        }

    def test_dispatches_to_correct_class(self):
        self.assertIsInstance(Event(self.fixture), eventtypes.LidMalfunctionActivated)
        self.assertNotIsInstance(Event(self.fixture), RawEvent)

    def test_has_no_alarmid_attribute(self):
        ev = Event(self.fixture)
        self.assertFalse(hasattr(ev, 'alarmId'))
        self.assertEqual(ev.malfIdRaw, 7)

    def test_envelope_fields(self):
        ev = Event(self.fixture)
        self.assertEqual(ev.eventId, 6)
        self.assertEqual(ev.seqNum, 500123)

    def test_timestamp_preserves_wall_clock(self):
        ev = Event(self.fixture)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'), "2026-05-16T00:07:00")

    def test_plain_fields(self):
        ev = Event(self.fixture)
        self.assertEqual(ev.faultLocatorData, 8311)
        self.assertEqual(ev.param1, 42)
        self.assertEqual(ev.param2, 0)

    def test_todict_is_json_serializable(self):
        ev = Event(self.fixture)
        d = ev.todict()
        json.dumps(d)  # must not raise
        self.assertEqual(d["id"], 6)
        self.assertEqual(d["name"], "LID_MALFUNCTION_ACTIVATED")
        self.assertEqual(d["malfIdRaw"], 7)


if __name__ == "__main__":
    unittest.main()
