#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidCgmDataG7(unittest.TestCase):
    """399 LID_CGM_DATA_G7 parsed from real captured pump-log events."""
    maxDiff = None

    def setUp(self):
        # Rising: large positive rate, high glucose, FMR reading.
        self.fixtureRising = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 464452,
            "pumpDateTime": "2026-05-20T12:15:13",
            "eventProperties": {
                "glucoseValueStatus": 0, "cgmDataType": [0], "rate": 52,
                "algorithmState": 32, "rssi": -87, "currentGlucoseDisplayValue": 287,
                "egvTimeStamp": 580133707, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12],
                "interval": 0, "reservedD15": 0,
            },
            "estimatedDateTime": "2026-05-20T12:15:13Z",
        }
        # Falling: large negative rate.
        self.fixtureFalling = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 416862,
            "pumpDateTime": "2026-05-06T23:26:04",
            "eventProperties": {
                "glucoseValueStatus": 0, "cgmDataType": [0], "rate": -39,
                "algorithmState": 32, "rssi": -54, "currentGlucoseDisplayValue": 195,
                "egvTimeStamp": 578964361, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12],
                "interval": 0, "reservedD15": 0,
            },
            "estimatedDateTime": "2026-05-06T23:26:04Z",
        }
        # SpecialLow: glucoseValueStatus 2, very low display value.
        self.fixtureSpecialLow = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 450303,
            "pumpDateTime": "2026-05-16T15:44:53",
            "eventProperties": {
                "glucoseValueStatus": 2, "cgmDataType": [0], "rate": -5,
                "algorithmState": 32, "rssi": -55, "currentGlucoseDisplayValue": 31,
                "egvTimeStamp": 579800690, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12],
                "interval": 0, "reservedD15": 0,
            },
            "estimatedDateTime": "2026-05-16T15:44:53Z",
        }
        # Backfill: different cgmDataType/egvInfoBitmask, high glucose, zero rate.
        self.fixtureBackfill = {
            "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
            "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 484027,
            "pumpDateTime": "2026-05-25T22:34:18",
            "eventProperties": {
                "glucoseValueStatus": 0, "cgmDataType": [1], "rate": 0,
                "algorithmState": 32, "rssi": -83, "currentGlucoseDisplayValue": 380,
                "egvTimeStamp": 580602548, "egvInfoBitmask": [1, 5, 6, 7, 8, 11, 12],
                "interval": 1, "reservedD15": 0,
            },
            "estimatedDateTime": "2026-05-25T22:34:18Z",
        }

    def test_dispatches_to_lidcgmdatag7(self):
        for fx in (self.fixtureRising, self.fixtureFalling,
                   self.fixtureSpecialLow, self.fixtureBackfill):
            ev = Event(fx)
            self.assertIsInstance(ev, eventtypes.LidCgmDataG7)
            self.assertNotIsInstance(ev, RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureRising)
        self.assertEqual(ev.eventId, 399)
        self.assertEqual(ev.seqNum, 464452)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-05-20T12:15:13")

    def test_display_value_and_rssi_round_trip(self):
        ev = Event(self.fixtureRising)
        self.assertEqual(ev.currentGlucoseDisplayValue, 287)
        self.assertEqual(ev.rssi, -87)

        low = Event(self.fixtureSpecialLow)
        self.assertEqual(low.currentGlucoseDisplayValue, 31)
        self.assertEqual(low.rssi, -55)

        high = Event(self.fixtureBackfill)
        self.assertEqual(high.currentGlucoseDisplayValue, 380)
        self.assertEqual(high.rssi, -83)

    def test_glucosevaluestatus_enum_resolves(self):
        # 0 -> PreciseValue: the zero value must resolve, not be treated as missing.
        ev = Event(self.fixtureRising)
        self.assertEqual(ev.glucoseValueStatusRaw, 0)
        self.assertEqual(ev.glucoseValueStatus,
                         eventtypes.LidCgmDataG7.GlucosevaluestatusEnum.PreciseValue)
        # 2 -> SpecialLow
        low = Event(self.fixtureSpecialLow)
        self.assertEqual(low.glucoseValueStatusRaw, 2)
        self.assertEqual(low.glucoseValueStatus,
                         eventtypes.LidCgmDataG7.GlucosevaluestatusEnum.SpecialLow)

    def test_algorithmstate_enum_resolves(self):
        # 32 -> ReportablePeriodValidEgv on every fixture.
        for fx in (self.fixtureRising, self.fixtureFalling,
                   self.fixtureSpecialLow, self.fixtureBackfill):
            ev = Event(fx)
            self.assertEqual(ev.algorithmStateRaw, 32)
            self.assertEqual(ev.algorithmState,
                             eventtypes.LidCgmDataG7.AlgorithmstateEnum.ReportablePeriodValidEgv)

    def test_cgm_datatype_bitmask_folds_to_raw_int(self):
        # cgmDataType:[0] -> 1<<0 == 1 -> Fmr
        ev = Event(self.fixtureRising)
        self.assertEqual(ev.cgmDataTypeRaw, 1)
        self.assertEqual(ev.cgmDataType,
                         eventtypes.LidCgmDataG7.CgmdatatypeBitmask.Fmr)
        # cgmDataType:[1] -> 1<<1 == 2 -> Backfill
        bf = Event(self.fixtureBackfill)
        self.assertEqual(bf.cgmDataTypeRaw, 2)
        self.assertEqual(bf.cgmDataType,
                         eventtypes.LidCgmDataG7.CgmdatatypeBitmask.Backfill)

    def test_egvinfobitmask_folds_to_raw_int(self):
        # [0,5,6,7,8,11,12] -> sum(1<<i) == 6625
        ev = Event(self.fixtureRising)
        self.assertEqual(ev.egvInfoBitmaskRaw,
                         sum(1 << i for i in [0, 5, 6, 7, 8, 11, 12]))
        self.assertEqual(ev.egvInfoBitmaskRaw, 6625)
        # [1,5,6,7,8,11,12] -> sum(1<<i) == 6626
        bf = Event(self.fixtureBackfill)
        self.assertEqual(bf.egvInfoBitmaskRaw,
                         sum(1 << i for i in [1, 5, 6, 7, 8, 11, 12]))
        self.assertEqual(bf.egvInfoBitmaskRaw, 6626)

    def test_rate_is_unscaled(self):
        # rate is in tenths of mg/dL/min; the schema no longer scales it
        rising = Event(self.fixtureRising)
        self.assertEqual(rising.rate, 52)

        falling = Event(self.fixtureFalling)
        self.assertEqual(falling.rate, -39)

        flat = Event(self.fixtureBackfill)
        self.assertEqual(flat.rate, 0)

    def test_egv_timestamp_is_raw_seconds(self):
        # egvTimeStamp (camelCase) normalizes onto egvTimestamp, kept as raw seconds int.
        self.assertEqual(Event(self.fixtureRising).egvTimeStamp, 580133707)
        self.assertEqual(Event(self.fixtureFalling).egvTimeStamp, 578964361)
        self.assertEqual(Event(self.fixtureSpecialLow).egvTimeStamp, 579800690)
        self.assertEqual(Event(self.fixtureBackfill).egvTimeStamp, 580602548)

    def test_todict_json_serializable(self):
        for fx in (self.fixtureRising, self.fixtureFalling,
                   self.fixtureSpecialLow, self.fixtureBackfill):
            json.dumps(Event(fx).todict())  # must not raise


if __name__ == "__main__":
    unittest.main()
