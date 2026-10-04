#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidBolusActivated(unittest.TestCase):
    """55 LID_BOLUS_ACTIVATED: real captured pump-log events."""
    maxDiff = None

    def setUp(self):
        # Real captured events (verbatim). All observed captures have
        # selectedIob=1 (Swan IOB Meal); fixtures differ by bolusSize/iob.
        self.fixtureMeal = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 55,
            "sequenceGroup": 0,
            "sequenceNumber": 394650,
            "pumpDateTime": "2026-04-30T11:57:53",
            "eventProperties": {
                "bolusId": 1423, "selectedIob": 1, "spareA3": 0,
                "iob": 1.8189592, "bolusSize": 8.33,
            },
            "estimatedDateTime": "2026-04-30T11:57:53Z",
        }
        self.fixtureZeroIob = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 55,
            "sequenceGroup": 0,
            "sequenceNumber": 395970,
            "pumpDateTime": "2026-04-30T21:38:00",
            "eventProperties": {
                "bolusId": 1426, "selectedIob": 1, "spareA3": 0,
                "iob": 0, "bolusSize": 10.96,
            },
            "estimatedDateTime": "2026-04-30T21:38:00Z",
        }
        self.fixtureSmall = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 55,
            "sequenceGroup": 0,
            "sequenceNumber": 395158,
            "pumpDateTime": "2026-04-30T15:13:14",
            "eventProperties": {
                "bolusId": 1425, "selectedIob": 1, "spareA3": 0,
                "iob": 4.116488, "bolusSize": 2,
            },
            "estimatedDateTime": "2026-04-30T15:13:14Z",
        }

    def test_dispatches_to_correct_class(self):
        ev = Event(self.fixtureMeal)
        self.assertIsInstance(ev, eventtypes.LidBolusActivated)
        self.assertNotIsInstance(ev, RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureMeal)
        self.assertEqual(ev.eventId, 55)
        self.assertEqual(ev.seqNum, 394650)

    def test_timestamp_preserves_wall_clock(self):
        ev = Event(self.fixtureMeal)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-04-30T11:57:53")

    def test_bolus_fields_round_trip(self):
        ev = Event(self.fixtureMeal)
        self.assertEqual(ev.bolusId, 1423)
        self.assertAlmostEqual(ev.iob, 1.8189592)
        self.assertAlmostEqual(ev.bolusSize, 8.33)

    def test_zero_iob_is_preserved(self):
        # iob:0 must not be dropped as missing.
        ev = Event(self.fixtureZeroIob)
        self.assertEqual(ev.bolusId, 1426)
        self.assertEqual(ev.iob, 0)
        self.assertAlmostEqual(ev.bolusSize, 10.96)

    def test_small_bolus_round_trips(self):
        ev = Event(self.fixtureSmall)
        self.assertEqual(ev.bolusId, 1425)
        self.assertAlmostEqual(ev.iob, 4.116488)
        self.assertEqual(ev.bolusSize, 2)

    def test_selectediob_resolves_to_enum(self):
        # selectedIob:1 -> Algorithm IOB
        ev = Event(self.fixtureMeal)
        self.assertEqual(ev.selectedIobRaw, 1)
        self.assertEqual(ev.selectedIob,
                         eventtypes.LidBolusActivated.SelectediobEnum.AlgorithmIob)

    def test_spareA3_is_ignored(self):
        ev = Event(self.fixtureMeal)
        self.assertFalse(hasattr(ev, "spareA3"))

    def test_todict_is_json_serializable(self):
        for fixture in (self.fixtureMeal, self.fixtureZeroIob, self.fixtureSmall):
            ev = Event(fixture)
            d = ev.todict()
            json.dumps(d)  # must not raise
            self.assertEqual(d["id"], 55)
            self.assertEqual(d["name"], "LID_BOLUS_ACTIVATED")


if __name__ == "__main__":
    unittest.main()
