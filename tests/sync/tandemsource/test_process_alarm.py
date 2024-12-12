#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process_alarm import ProcessAlarm
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event

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
        self.assertEqual(events[0].alarmid, eventtypes.LidAlarmActivated.AlarmidEnum.ResumePumpAlarm)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 0)


    def test_empty_cartridge_alarm(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-11-17 08:44:17-05:00
            Event(b'\x00\x05\x1f\xc0*a\x00\x0e\xf5\x90\x00\x00\x00\x08\x00\x00 1\x00\x00\x00gA\x1a\x1e\x84')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAlarmActivated)
        self.assertEqual(events[0].alarmid, eventtypes.LidAlarmActivated.AlarmidEnum.EmptyCartridgeAlarm)

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




if __name__ == '__main__':
    unittest.main()