#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process_alarm import ProcessAlarm
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event, Events

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

class TestProcessAlarm(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessAlarm(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False)

    def test_resume_alarm_ignored(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-11-11 07:24:29-05:00
            Event(b'\x00\x05\x1f\xb8.\xad\x00\x0e\x91\xee\x00\x00\x00\x12\x00\x00 w\x01N\x0b\x16\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAlarmActivated)
        self.assertEqual(events[0].alarmId, eventtypes.LidAlarmActivated.AlarmidEnum.ResumePumpAlarm)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 0)


    def test_empty_cartridge_alarm(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-11-17 08:44:17-05:00
            Event(b'\x00\x05\x1f\xc0*a\x00\x0e\xf5\x90\x00\x00\x00\x08\x00\x00 1\x00\x00\x00gA\x1a\x1e\x84')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAlarmActivated)
        self.assertEqual(events[0].alarmId, eventtypes.LidAlarmActivated.AlarmidEnum.EmptyCartridgeAlarm)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'eventType': 'Alarm',
            'created_at': '2024-11-17 08:44:17-05:00',
            'enteredBy': 'Pump (tconnectsync)',
            'notes': 'EmptyCartridgeAlarm',
            'reason': 'EmptyCartridgeAlarm',
            'pump_event_id': '980368'
        })



# Real captured LID_ALARM_ACTIVATED (eventCode 5) events
# (deviceAssignmentId redacted).
ALARM_PUMP_RESET = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 5,
    "sequenceGroup": 0,
    "sequenceNumber": 2353636,
    "pumpDateTime": "2024-02-26T22:44:48",
    "estimatedDateTime": "2024-02-26T22:44:48Z",
    "eventProperties": {"alarmId": 3, "faultLocatorData": 8230, "param1": 0, "param2": 0},
}

ALARM_EMPTY_CARTRIDGE = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 5,
    "sequenceGroup": 0,
    "sequenceNumber": 1124751,
    "pumpDateTime": "2024-12-23T09:36:37",
    "estimatedDateTime": "2024-12-23T09:36:37Z",
    "eventProperties": {"alarmId": 8, "faultLocatorData": 8241, "param1": 103, "param2": 9.475377},
}

ALARM_RESUME = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 5,
    "sequenceGroup": 0,
    "sequenceNumber": 448136,
    "pumpDateTime": "2026-05-16T00:06:00",
    "estimatedDateTime": "2026-05-16T00:06:00Z",
    "eventProperties": {"alarmId": 18, "faultLocatorData": 8311, "param1": 5228339, "param2": 0},
}

MALFUNCTION = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 6,
    "sequenceGroup": 0,
    "sequenceNumber": 500123,
    "pumpDateTime": "2026-05-16T00:07:00",
    "estimatedDateTime": "2026-05-16T00:07:00Z",
    "eventProperties": {"malfId": 7, "faultLocatorData": 8311, "param1": 42, "param2": 0},
}


class TestProcessAlarmJson(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.process = ProcessAlarm(self.tconnect, self.nightscout, 'abcdef', pretend=False)
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

    def test_reportable_alarms(self):
        p = self.process.process(list(Events([dict(ALARM_PUMP_RESET), dict(ALARM_EMPTY_CARTRIDGE)])), None, None)

        self.assertEqual(len(p), 2)
        self.assertDictEqual(p[0], {
            'eventType': 'Alarm',
            'reason': 'PumpResetAlarm',
            'notes': 'PumpResetAlarm',
            'created_at': '2024-02-26 22:44:48-05:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '2353636'
        })
        self.assertDictEqual(p[1], {
            'eventType': 'Alarm',
            'reason': 'EmptyCartridgeAlarm',
            'notes': 'EmptyCartridgeAlarm',
            'created_at': '2024-12-23 09:36:37-05:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '1124751'
        })

    def test_resume_alarm_skipped(self):
        p = self.process.process(list(Events([dict(ALARM_RESUME)])), None, None)
        self.assertEqual(p, [])

    def test_malfunction_alarm_uploaded(self):
        event = Event(dict(MALFUNCTION))
        self.assertEqual(type(event), eventtypes.LidMalfunctionActivated)
        self.assertFalse(hasattr(event, 'alarmId'))

        p = self.process.process([event], None, None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'eventType': 'Alarm',
            'reason': 'Malfunction',
            'notes': 'Malfunction',
            'created_at': '2026-05-16 00:07:00-04:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '500123'
        })

    def test_alarm_and_malfunction_mixed(self):
        # A batch mixing both ALARM-class event types must not crash and must
        # emit an entry for each.
        p = self.process.process(list(Events([dict(ALARM_PUMP_RESET), dict(MALFUNCTION)])), None, None)

        self.assertEqual(len(p), 2)
        reasons = {entry['reason'] for entry in p}
        self.assertEqual(reasons, {'PumpResetAlarm', 'Malfunction'})


class TestAlarmOrMalfunctionUnion(unittest.TestCase):
    def test_union_matches_eventclass(self):
        from typing import get_args
        from tconnectsync.sync.tandemsource.process_alarm import AlarmOrMalfunction
        from tconnectsync.domain.tandemsource.event_class import EventClass

        self.assertEqual(set(get_args(AlarmOrMalfunction)), set(EventClass.ALARM))


if __name__ == '__main__':
    unittest.main()