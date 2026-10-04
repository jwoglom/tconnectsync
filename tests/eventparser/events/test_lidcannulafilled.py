#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidCannulaFilled(unittest.TestCase):
    """61: LID_CANNULA_FILLED. Fixture is a real captured pump-log event.
    Only one distinct eventProperties shape exists in the captures, so a
    single fixture covers the observed behavior."""
    maxDiff = None

    def setUp(self):
        self.fixtureCompleted = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 61,
            "sequenceGroup": 0,
            "sequenceNumber": 412912,
            "pumpDateTime": "2026-05-05T19:16:40",
            "eventProperties": {
                "primeSize": 0.3, "completionStatus": 3, "infusionSetType": 0,
            },
            "estimatedDateTime": "2026-05-05T19:16:40Z",
        }

    def test_dispatches_to_lidcannulafilled(self):
        ev = Event(self.fixtureCompleted)
        self.assertIsInstance(ev, eventtypes.LidCannulaFilled)
        self.assertNotIsInstance(ev, RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureCompleted)
        self.assertEqual(ev.eventId, 61)
        self.assertEqual(ev.seqNum, 412912)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-05-05T19:16:40")

    def test_primesize_round_trips(self):
        ev = Event(self.fixtureCompleted)
        self.assertEqual(ev.primeSize, 0.3)

    def test_completionstatus_resolves_to_enum(self):
        # completionStatus:3 -> Completed
        ev = Event(self.fixtureCompleted)
        self.assertEqual(ev.completionStatusRaw, 3)
        self.assertEqual(ev.completionStatus,
                         eventtypes.LidCannulaFilled.CompletionstatusEnum.Completed)

    def test_infusionsettype_resolves_to_enum(self):
        # infusionSetType:0 -> DefaultTubed
        ev = Event(self.fixtureCompleted)
        self.assertEqual(ev.infusionSetTypeRaw, 0)
        self.assertEqual(ev.infusionSetType,
                         eventtypes.LidCannulaFilled.InfusionsettypeEnum.DefaultTubed)

    def test_todict_is_json_serializable(self):
        ev = Event(self.fixtureCompleted)
        json.dumps(ev.todict())  # must not raise


if __name__ == "__main__":
    unittest.main()
