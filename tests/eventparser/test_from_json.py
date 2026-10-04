#!/usr/bin/env python3

import unittest

from tconnectsync.eventparser.generic import Event, Events
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent

# Trimmed real pump-log events (values from a captured account response).
BASAL_279 = {
    "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
    "eventCode": 279,
    "sequenceGroup": 0,
    "sequenceNumber": 393131,
    "pumpDateTime": "2026-04-30T00:03:29",
    "eventProperties": {
        "commandedRateSource": 3, "reservedA2": 0, "spareA3": 0,
        "commandedRate": 0, "profileBasalRate": 1000, "algorithmRate": 0,
        "tempRate": 65535,
    },
    "estimatedDateTime": "2026-04-30T00:03:29Z",
}

ALARM_5 = {
    "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
    "eventCode": 5,
    "sequenceGroup": 0,
    "sequenceNumber": 500001,
    "pumpDateTime": "2026-04-30T01:00:00",
    "eventProperties": {"alarmId": 18, "faultLocatorData": 8311, "param1": 3993668, "param2": 0},
    "estimatedDateTime": "2026-04-30T01:00:00Z",
}

# Real LID_CGM_DATA_G7 event: enum (glucoseValueStatus), ratio (rate ×0.1),
# raw egv seconds (egvTimeStamp), and bitmask arrays (cgmDataType, egvInfoBitmask).
CGM_399 = {
    "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
    "eventCode": 399,
    "sequenceGroup": 0,
    "sequenceNumber": 441314,
    "pumpDateTime": "2026-05-14T00:01:31",
    "eventProperties": {
        "glucoseValueStatus": 0, "cgmDataType": [0], "rate": -6,
        "algorithmState": 32, "rssi": -78, "currentGlucoseDisplayValue": 167,
        "egvTimeStamp": 579571288, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12],
        "interval": 0, "reservedD15": 0,
    },
    "estimatedDateTime": "2026-05-14T00:01:31Z",
}

# Real LID_AA_USER_MODE_CHANGE event: enum (requestedAction) and a bitmask
# array (activeSleepSchedule).
UMC_229 = {
    "deviceAssignmentId": "4ff6bebc-d4d6-4423-b123-eecfcf5a4238",
    "eventCode": 229,
    "sequenceGroup": 0,
    "sequenceNumber": 456851,
    "pumpDateTime": "2026-05-18T10:15:53",
    "eventProperties": {
        "currentUserMode": 0, "previousUserMode": 1, "requestedAction": 2,
        "spareA3": 0, "sleepStartedByGui": 1, "activeSleepSchedule": [0],
        "spareB6": 0, "exerciseStoppedByTimer": 0, "exerciseChoice": 0,
        "exerciseTime": 0, "eatingSoonStoppedByTimer": 0,
    },
    "estimatedDateTime": "2026-05-18T10:15:53Z",
}


class TestBuildFromJson(unittest.TestCase):
    maxDiff = None

    def test_dispatches_to_correct_class(self):
        self.assertIsInstance(Event(BASAL_279), eventtypes.LidBasalDelivery)
        self.assertIsInstance(Event(ALARM_5), eventtypes.LidAlarmActivated)

    def test_plain_fields(self):
        ev = Event(BASAL_279)
        self.assertEqual(ev.commandedRate, 0)
        self.assertEqual(ev.profileBasalRate, 1000)
        self.assertEqual(ev.tempRate, 65535)

    def test_envelope_fields(self):
        ev = Event(BASAL_279)
        self.assertEqual(ev.seqNum, 393131)
        self.assertEqual(ev.eventId, 279)

    def test_timestamp_preserves_wall_clock(self):
        # eventTimestamp keeps pumpDateTime's wall-clock (tz forced to the
        # configured TIMEZONE_NAME), so the naive portion round-trips exactly.
        ev = Event(BASAL_279)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'), "2026-04-30T00:03:29")

    def test_missing_plain_field_defaults_to_none(self):
        event = dict(BASAL_279)
        event["eventProperties"] = {k: v for k, v in BASAL_279["eventProperties"].items() if k != "tempRate"}
        ev = Event(event)
        self.assertIsNone(ev.tempRate)
        self.assertEqual(ev.commandedRate, 0)  # others still parse

    def test_extra_keys_are_ignored(self):
        event = dict(BASAL_279)
        event["eventProperties"] = dict(BASAL_279["eventProperties"], someFutureField=42)
        ev = Event(event)  # must not raise
        self.assertFalse(hasattr(ev, "someFutureField"))

    def test_events_from_json_yields_in_order(self):
        out = list(Events([BASAL_279, ALARM_5]))
        self.assertEqual([type(e).__name__ for e in out],
                         ["LidBasalDelivery", "LidAlarmActivated"])

    def test_unknown_eventcode_falls_back_to_rawevent(self):
        ev = Event({
            "eventCode": 99999,
            "sequenceNumber": 7,
            "pumpDateTime": "2026-04-30T00:00:00",
            "eventProperties": {},
        })
        self.assertIs(type(ev), RawEvent)
        self.assertEqual(ev.eventId, 99999)
        self.assertEqual(ev.seqNum, 7)
        self.assertEqual(ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'), "2026-04-30T00:00:00")


class TestEnumAndRatioFields(unittest.TestCase):
    """#13: enum/dictionary fields arrive as raw ints and resolve through the
    generated {field}Raw attr; ratio fields (×0.1) still compute."""
    maxDiff = None

    def test_enum_resolves_from_raw_int(self):
        # commandedRateSource:3 -> Algorithm
        ev = Event(BASAL_279)
        self.assertEqual(ev.commandedRateSourceRaw, 3)
        self.assertEqual(ev.commandedRateSource,
                         eventtypes.LidBasalDelivery.CommandedratesourceEnum.Algorithm)

    def test_dictionary_enum_resolves_from_raw_int(self):
        # alarmId:18 -> ResumePumpAlarm (stored on the alarmidRaw attr)
        ev = Event(ALARM_5)
        self.assertEqual(ev.alarmIdRaw, 18)
        self.assertEqual(ev.alarmId,
                         eventtypes.LidAlarmActivated.AlarmidEnum.ResumePumpAlarm)

    def test_multiple_enums_on_one_event(self):
        # requestedAction:2 -> StopSleep; previousUserMode:1 -> Sleeping
        ev = Event(UMC_229)
        self.assertEqual(ev.requestedAction,
                         eventtypes.LidAaUserModeChange.RequestedactionEnum.StopSleep)
        self.assertEqual(ev.previousUserMode,
                         eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Sleeping)

    def test_rate_is_unscaled(self):
        # rate:-6 is in tenths of mg/dL/min; the schema no longer scales it
        ev = Event(CGM_399)
        self.assertEqual(ev.rate, -6)

    def test_enum_zero_value_resolves(self):
        # glucoseValueStatus:0 -> PreciseValue (0 must not be treated as missing)
        ev = Event(CGM_399)
        self.assertEqual(ev.glucoseValueStatusRaw, 0)
        self.assertEqual(ev.glucoseValueStatus,
                         eventtypes.LidCgmDataG7.GlucosevaluestatusEnum.PreciseValue)


class TestBitmaskFields(unittest.TestCase):
    """#14: bitmask fields arrive as arrays of set-bit indices and must be
    folded back into the raw int the {field}Raw attr / IntFlag expects."""
    maxDiff = None

    def test_single_bit_array(self):
        # activeSleepSchedule:[0] -> 1<<0 == 1
        ev = Event(UMC_229)
        self.assertEqual(ev.activeSleepScheduleRaw, 1)
        self.assertEqual(ev.activeSleepSchedule,
                         eventtypes.LidAaUserModeChange.ActivesleepscheduleBitmask.SleepSchedule1IsActive)

    def test_cgm_datatype_array(self):
        # cgmDataType:[0] -> 1<<0 == 1 -> Fmr
        ev = Event(CGM_399)
        self.assertEqual(ev.cgmDataTypeRaw, 1)
        self.assertEqual(ev.cgmDataType,
                         eventtypes.LidCgmDataG7.CgmdatatypeBitmask.Fmr)

    def test_multi_bit_array_round_trips_to_int(self):
        # egvInfoBitmask:[0,5,6,7,8,11,12] -> sum(1<<i) == 6625
        ev = Event(CGM_399)
        self.assertEqual(ev.egvInfoBitmaskRaw,
                         sum(1 << i for i in [0, 5, 6, 7, 8, 11, 12]))
        self.assertEqual(ev.egvInfoBitmaskRaw, 6625)

    def test_empty_bitmask_array(self):
        # An empty array must fold to 0, not None (matches the byte path).
        event = dict(UMC_229)
        event["eventProperties"] = dict(UMC_229["eventProperties"], activeSleepSchedule=[])
        ev = Event(event)
        self.assertEqual(ev.activeSleepScheduleRaw, 0)


class TestRawFieldShims(unittest.TestCase):
    """#15: process_device_status sorts on event.raw.timestamp; ProcessCGMReading
    reads event.egvTimeStamp as raw seconds — both must survive the JSON path."""
    maxDiff = None

    def test_raw_timestamp_shim_available(self):
        # process_device_status uses `sorted(events, key=lambda x: x.raw.timestamp)`,
        # so adapted events must expose raw.timestamp as the wall-clock instant.
        ev = Event(BASAL_279)
        self.assertEqual(ev.raw.timestamp.format('YYYY-MM-DDTHH:mm:ss'),
                         "2026-04-30T00:03:29")

    def test_cgm_egv_timestamp_is_raw_seconds(self):
        # egvTimeStamp (camelCase in the JSON) normalizes onto egvTimestamp and is
        # kept as a raw seconds int; ProcessCGMReading adds TANDEM_EPOCH to it.
        ev = Event(CGM_399)
        self.assertEqual(ev.egvTimeStamp, 579571288)
        self.assertEqual(ev.currentGlucoseDisplayValue, 167)


if __name__ == "__main__":
    unittest.main()
