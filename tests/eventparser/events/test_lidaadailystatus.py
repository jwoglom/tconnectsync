#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes


class TestLidAaDailyStatus(unittest.TestCase):
    """313 LID_AA_DAILY_STATUS: pumpControlState/usermode/sensorType enums.

    Fixtures are real captured pump-log events copied verbatim.
    """
    maxDiff = None

    def setUp(self):
        # Real capture: pumpControlState 3 -> PcmClosedLoop.
        self.fixtureClosedLoop = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 313,
            "sequenceGroup": 0,
            "sequenceNumber": 393118,
            "pumpDateTime": "2026-04-30T00:00:06",
            "eventProperties": {
                "pumpControlState": 3, "usermode": 1, "sensorType": 3,
                "weightUnit": 0, "weight": 0, "currentTdIpop": 0,
            },
            "estimatedDateTime": "2026-04-30T00:00:06Z",
        }
        # Real capture: pumpControlState 0 -> PcmNoControlNoCartridgeInstalled.
        self.fixtureNoControl = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 313,
            "sequenceGroup": 0,
            "sequenceNumber": 420321,
            "pumpDateTime": "2026-05-08T00:00:06",
            "eventProperties": {
                "pumpControlState": 0, "usermode": 1, "sensorType": 3,
                "weightUnit": 0, "weight": 0, "currentTdIpop": 0,
            },
            "estimatedDateTime": "2026-05-08T00:00:06Z",
        }

    def test_dispatches_to_lidaadailystatus(self):
        self.assertIsInstance(Event(self.fixtureClosedLoop), eventtypes.LidAaDailyStatus)
        self.assertIsInstance(Event(self.fixtureNoControl), eventtypes.LidAaDailyStatus)

    def test_envelope_fields(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.eventId, 313)
        self.assertEqual(ev.seqNum, 393118)
        self.assertEqual(Event(self.fixtureNoControl).seqNum, 420321)

    def test_timestamp_preserves_wall_clock(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-04-30T00:00:06")

    def test_pumpcontrolstate_closed_loop(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.pumpControlStateRaw, 3)
        self.assertEqual(ev.pumpControlState,
                         eventtypes.LidAaDailyStatus.PumpcontrolstateEnum.PcmClosedLoop)

    def test_pumpcontrolstate_no_control_zero_value(self):
        # pumpControlState 0 must resolve, not be treated as missing.
        ev = Event(self.fixtureNoControl)
        self.assertEqual(ev.pumpControlStateRaw, 0)
        self.assertEqual(ev.pumpControlState,
                         eventtypes.LidAaDailyStatus.PumpcontrolstateEnum.PcmNoControlNoCartridgeInstalled)

    def test_usermode_resolves(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.usermodeRaw, 1)
        self.assertEqual(ev.usermode,
                         eventtypes.LidAaDailyStatus.UsermodeEnum.Sleeping)

    def test_sensortype_resolves(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.sensorTypeRaw, 3)
        self.assertEqual(ev.sensorType,
                         eventtypes.LidAaDailyStatus.SensortypeEnum.CgmTypeDexcomG7)

    def test_weight_and_tdi_fields_parsed(self):
        ev = Event(self.fixtureClosedLoop)
        self.assertEqual(ev.weightUnitRaw, 0)
        self.assertEqual(ev.weightUnit,
                         eventtypes.LidAaDailyStatus.WeightunitEnum.WeightUnitNotSet)
        self.assertEqual(ev.weight, 0)
        self.assertEqual(ev.currentTdIpop, 0)

    def test_todict_is_json_serializable(self):
        ev = Event(self.fixtureClosedLoop)
        d = ev.todict()
        json.dumps(d)  # must not raise
        self.assertEqual(d["id"], 313)
        self.assertEqual(d["name"], "LID_AA_DAILY_STATUS")
        self.assertEqual(d["seqNum"], 393118)
        self.assertEqual(d["pumpControlStateRaw"], 3)
        self.assertEqual(d["usermodeRaw"], 1)
        self.assertEqual(d["sensorTypeRaw"], 3)


if __name__ == "__main__":
    unittest.main()
