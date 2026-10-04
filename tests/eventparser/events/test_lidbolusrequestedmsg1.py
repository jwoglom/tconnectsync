#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidBolusRequestedMsg1(unittest.TestCase):
    """64: LID_BOLUS_REQUESTED_MSG1. Fixtures are real captured pump-log events
    copied verbatim from a captured account response."""
    maxDiff = None

    def setUp(self):
        # bolusType 3 (Remote), correctionBolusIncluded 0 (No), carbs present.
        self.fixtureRemoteWithCarbs = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 64, "sequenceGroup": 0, "sequenceNumber": 394641,
            "pumpDateTime": "2026-04-30T11:57:38",
            "eventProperties": {
                "bolusId": 1423, "bolusType": 3, "correctionBolusIncluded": 0,
                "carbAmount": 50, "bg": 164, "iob": 1.82, "carbRatio": 0,
            },
            "estimatedDateTime": "2026-04-30T11:57:38Z",
        }
        # bolusType 3 (Remote), correctionBolusIncluded 1 (Yes), iob 0.
        self.fixtureRemoteWithCorrection = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 64, "sequenceGroup": 0, "sequenceNumber": 395959,
            "pumpDateTime": "2026-04-30T21:37:45",
            "eventProperties": {
                "bolusId": 1426, "bolusType": 3, "correctionBolusIncluded": 1,
                "carbAmount": 65, "bg": 114, "iob": 0, "carbRatio": 0,
            },
            "estimatedDateTime": "2026-04-30T21:37:45Z",
        }
        # bolusType 0 (Insulin), no carbs, bg 0, fractional iob.
        self.fixtureInsulinNoCarbs = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 64, "sequenceGroup": 0, "sequenceNumber": 395146,
            "pumpDateTime": "2026-04-30T15:12:59",
            "eventProperties": {
                "bolusId": 1425, "bolusType": 0, "correctionBolusIncluded": 0,
                "carbAmount": 0, "bg": 0, "iob": 4.116488, "carbRatio": 0,
            },
            "estimatedDateTime": "2026-04-30T15:12:59Z",
        }

    def test_dispatches_to_correct_class(self):
        ev = Event(self.fixtureRemoteWithCarbs)
        self.assertIsInstance(ev, eventtypes.LidBolusRequestedMsg1)
        self.assertNotIsInstance(ev, RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureRemoteWithCarbs)
        self.assertEqual(ev.eventId, 64)
        self.assertEqual(ev.seqNum, 394641)
        # eventTimestamp keeps pumpDateTime's wall-clock.
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-04-30T11:57:38")

    def test_plain_fields_round_trip(self):
        ev = Event(self.fixtureRemoteWithCarbs)
        self.assertEqual(ev.bolusId, 1423)
        self.assertEqual(ev.carbAmount, 50)
        self.assertEqual(ev.bg, 164)
        self.assertEqual(ev.iob, 1.82)

    def test_fractional_iob_and_zero_bg(self):
        ev = Event(self.fixtureInsulinNoCarbs)
        self.assertEqual(ev.bolusId, 1425)
        self.assertEqual(ev.carbAmount, 0)
        self.assertEqual(ev.bg, 0)
        self.assertAlmostEqual(ev.iob, 4.116488)

    def test_bolustype_remote(self):
        ev = Event(self.fixtureRemoteWithCarbs)
        self.assertEqual(ev.bolusTypeRaw, 3)
        self.assertEqual(ev.bolusType,
                         eventtypes.LidBolusRequestedMsg1.BolustypeEnum.Remote)

    def test_bolustype_insulin(self):
        # bolusType 0 must resolve (0 not treated as missing).
        ev = Event(self.fixtureInsulinNoCarbs)
        self.assertEqual(ev.bolusTypeRaw, 0)
        self.assertEqual(ev.bolusType,
                         eventtypes.LidBolusRequestedMsg1.BolustypeEnum.Insulin)

    def test_correctionbolusincluded_no(self):
        ev = Event(self.fixtureRemoteWithCarbs)
        self.assertEqual(ev.correctionBolusIncludedRaw, 0)
        self.assertEqual(
            ev.correctionBolusIncluded,
            eventtypes.LidBolusRequestedMsg1.CorrectionbolusincludedEnum.FalseVal)

    def test_correctionbolusincluded_yes(self):
        ev = Event(self.fixtureRemoteWithCorrection)
        self.assertEqual(ev.correctionBolusIncludedRaw, 1)
        self.assertEqual(
            ev.correctionBolusIncluded,
            eventtypes.LidBolusRequestedMsg1.CorrectionbolusincludedEnum.TrueVal)

    def test_carbratio_scales(self):
        # carbratio is carbratioRaw * 0.001; real captures carry 0.
        ev = Event(self.fixtureRemoteWithCorrection)
        self.assertEqual(ev.carbRatioRaw, 0)
        self.assertAlmostEqual(ev.carbRatio, 0.0)

    def test_todict_is_json_serializable(self):
        for fixture in (self.fixtureRemoteWithCarbs,
                        self.fixtureRemoteWithCorrection,
                        self.fixtureInsulinNoCarbs):
            ev = Event(fixture)
            d = ev.todict()
            json.dumps(d)  # must not raise
            self.assertEqual(d["id"], 64)
            self.assertEqual(d["name"], "LID_BOLUS_REQUESTED_MSG1")
            self.assertEqual(d["bolusId"],
                             fixture["eventProperties"]["bolusId"])


if __name__ == "__main__":
    unittest.main()
