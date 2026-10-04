#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidAaPcmChange(unittest.TestCase):
    """230 LID_AA_PCM_CHANGE: currentPcm/previousPcm resolve to a PCM enum,
    and the boolean-ish fields resolve to False/True enum members. All
    fixtures are real captured events copied verbatim."""
    maxDiff = None

    def setUp(self):
        # currentPcm:0 (NoControl) from previousPcm:3 (ClosedLoop), suspended.
        self.fixtureSuspendedNoControl = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 230,
            "sequenceGroup": 0,
            "sequenceNumber": 394337,
            "pumpDateTime": "2026-04-30T10:01:49",
            "eventProperties": {
                "currentPcm": 0, "previousPcm": 3, "pumpSuspended": 1,
                "calculationAvailable": 1, "cgmAvailable": 1,
                "closedLoopPreferred": 1, "sufficientClosedLoopParams": 1,
            },
            "estimatedDateTime": "2026-04-30T10:01:49Z",
        }

        # currentPcm:3 (ClosedLoop) from previousPcm:0 (NoControl), not suspended.
        self.fixtureResumedClosedLoop = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 230,
            "sequenceGroup": 0,
            "sequenceNumber": 394430,
            "pumpDateTime": "2026-04-30T10:16:31",
            "eventProperties": {
                "currentPcm": 3, "previousPcm": 0, "pumpSuspended": 0,
                "calculationAvailable": 1, "cgmAvailable": 1,
                "closedLoopPreferred": 1, "sufficientClosedLoopParams": 1,
            },
            "estimatedDateTime": "2026-04-30T10:16:31Z",
        }

        # currentPcm:2 (Pining) with cgmAvailable:0.
        self.fixturePiningNoCgm = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 230,
            "sequenceGroup": 0,
            "sequenceNumber": 409128,
            "pumpDateTime": "2026-05-04T18:58:22",
            "eventProperties": {
                "currentPcm": 2, "previousPcm": 3, "pumpSuspended": 0,
                "calculationAvailable": 1, "cgmAvailable": 0,
                "closedLoopPreferred": 1, "sufficientClosedLoopParams": 1,
            },
            "estimatedDateTime": "2026-05-04T18:58:22Z",
        }

    def test_dispatches_to_correct_class(self):
        ev = Event(self.fixtureSuspendedNoControl)
        self.assertIsInstance(ev, eventtypes.LidAaPcmChange)
        self.assertNotIsInstance(ev, RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureSuspendedNoControl)
        self.assertEqual(ev.eventId, 230)
        self.assertEqual(ev.seqNum, 394337)

    def test_timestamp_preserves_wall_clock(self):
        ev = Event(self.fixtureSuspendedNoControl)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-04-30T10:01:49")

    def test_pcm_enums_no_control_from_closed_loop(self):
        # currentPcm:0 -> NoControl, previousPcm:3 -> ClosedLoop
        ev = Event(self.fixtureSuspendedNoControl)
        self.assertEqual(ev.currentPcmRaw, 0)
        self.assertEqual(ev.currentPcm,
                         eventtypes.LidAaPcmChange.CurrentpcmEnum.NoControl)
        self.assertEqual(ev.previousPcmRaw, 3)
        self.assertEqual(ev.previousPcm,
                         eventtypes.LidAaPcmChange.PreviouspcmEnum.ClosedLoop)

    def test_pcm_enums_closed_loop_from_no_control(self):
        # currentPcm:3 -> ClosedLoop, previousPcm:0 -> NoControl
        ev = Event(self.fixtureResumedClosedLoop)
        self.assertEqual(ev.currentPcm,
                         eventtypes.LidAaPcmChange.CurrentpcmEnum.ClosedLoop)
        self.assertEqual(ev.previousPcm,
                         eventtypes.LidAaPcmChange.PreviouspcmEnum.NoControl)

    def test_pcm_enum_pining(self):
        # currentPcm:2 -> Pining
        ev = Event(self.fixturePiningNoCgm)
        self.assertEqual(ev.currentPcmRaw, 2)
        self.assertEqual(ev.currentPcm,
                         eventtypes.LidAaPcmChange.CurrentpcmEnum.Pining)

    def test_boolean_fields_when_suspended(self):
        ev = Event(self.fixtureSuspendedNoControl)
        self.assertEqual(ev.pumpSuspended, 1)
        self.assertEqual(ev.calculationAvailable, 1)
        self.assertEqual(ev.cgmAvailable, 1)
        self.assertEqual(ev.closedLoopPreferred, 1)
        self.assertEqual(ev.sufficientClosedLoopParams, 1)

    def test_pump_suspended_false(self):
        # pumpSuspended:0 (0 must not be treated as missing)
        ev = Event(self.fixtureResumedClosedLoop)
        self.assertEqual(ev.pumpSuspended, 0)

    def test_cgm_available_false(self):
        # cgmAvailable:0 while other boolean fields stay 1
        ev = Event(self.fixturePiningNoCgm)
        self.assertEqual(ev.cgmAvailable, 0)
        self.assertEqual(ev.calculationAvailable, 1)
        self.assertEqual(ev.closedLoopPreferred, 1)

    def test_todict_is_json_serializable(self):
        for fixture in (self.fixtureSuspendedNoControl,
                        self.fixtureResumedClosedLoop,
                        self.fixturePiningNoCgm):
            ev = Event(fixture)
            d = ev.todict()
            json.dumps(d)  # must not raise
            self.assertEqual(d["id"], 230)
            self.assertEqual(d["name"], "LID_AA_PCM_CHANGE")


if __name__ == "__main__":
    unittest.main()
