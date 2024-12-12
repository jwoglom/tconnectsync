#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process_user_mode import ProcessUserMode
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

class TestProcessUserModeSleep(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessUserMode(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False)

    def test_single_start_sleep_active(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 23:00:23-05:00 - sleep start
            Event(b'\x00\xe5\x1f\xd7\\\x87\x00\x10\t\xaa\x00\x01\x00\x01\x00\x00\x01\x00\x00\xf0\x01\x01\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Normal)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Sleeping)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StartSleep)

        time_end = arrow.get('2024-12-04T23:00:30-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Sleep',
            "reason": 'Sleep (Scheduled) - Not Ended',
            "notes": 'Sleep (Scheduled) - Not Ended',
            "duration": 0.11666666666666667,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050'
        })
        self.assertEqual(self.nightscout.deleted_entries, [])

    def test_single_stop_sleep_no_last_uploaded(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 09:01:23-05:00 - sleep end
            Event(b'\x00\xe5\x1f\xd6\x97\xe3\x00\x0f\xfe\xb0\x00\x02\x01\x00\x00\x00\x00\x00\x00\xf0\x01\x01\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Sleeping)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopSleep)

        time_end = arrow.get('2024-12-04T23:00:30-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 0)
        self.assertEqual(self.nightscout.deleted_entries, [])


    def test_start_and_stop_sleep(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 23:00:23-05:00 - sleep start
            Event(b'\x00\xe5\x1f\xd7\\\x87\x00\x10\t\xaa\x00\x01\x00\x01\x00\x00\x01\x00\x00\xf0\x01\x01\x00\x00\x00\x00'),
            # 2024-12-05 09:01:23-05:00 - sleep end
            Event(b'\x00\xe5\x1f\xd7\xe9c\x00\x10\x10\xf8\x00\x02\x01\x00\x00\x00\x00\x00\x00\xf0\x01\x01\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Normal)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Sleeping)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StartSleep)


        self.assertEqual(type(events[1]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[1].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Sleeping)
        self.assertEqual(events[1].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[1].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopSleep)

        time_end = arrow.get('2024-12-05T10:00:00-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Sleep',
            "reason": 'Sleep (Scheduled)',
            "notes": 'Sleep (Scheduled)',
            "duration": 601.0,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050,1052920'
        })
        self.assertEqual(self.nightscout.deleted_entries, [])

    def test_stop_with_partial_last_uploaded(self):
        self.nightscout.last_uploaded_entry = lambda eventType, **kwargs: {
            'Sleep': {
                "eventType": 'Sleep',
                "reason": 'Sleep (Scheduled) - Not Ended',
                "notes": 'Sleep (Scheduled) - Not Ended',
                "duration": 0.11666666666666667,
                "created_at": '2024-12-04 23:00:23-05:00',
                "enteredBy": "Pump (tconnectsync)",
                "pump_event_id": '1051050',
                "_id": "id_to_delete"
            }
        }.get(eventType)

        events = [
            # 2024-12-05 09:01:23-05:00 - sleep end
            Event(b'\x00\xe5\x1f\xd7\xe9c\x00\x10\x10\xf8\x00\x02\x01\x00\x00\x00\x00\x00\x00\xf0\x01\x01\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Sleeping)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopSleep)

        time_end = arrow.get('2024-12-05T10:00:00-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Sleep',
            "reason": 'Sleep (Scheduled)',
            "notes": 'Sleep (Scheduled)',
            "duration": 601.0,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050,1052920'
        })
        self.assertEqual(self.nightscout.deleted_entries, ['treatments/id_to_delete'])


class TestProcessUserModeExercise(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessUserMode(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False)

    def test_single_start_exercise_active(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 23:00:23-05:00 - exercise start
            Event(b'\x00\xe5\x1f\xd7\\\x87\x00\x10\t\xaa\x00\x03\x00\x02\x00\x00\x01\x00\x00\xf0\x00\x01\x00\x00\x00\x00'),
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Normal)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Exercising)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StartExercise)

        time_end = arrow.get('2024-12-04T23:00:30-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Exercise',
            "reason": 'Exercise - Not Ended',
            "notes": 'Exercise - Not Ended',
            "duration": 0.11666666666666667,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050'
        })
        self.assertEqual(self.nightscout.deleted_entries, [])

    def test_single_stop_exercise_no_last_uploaded(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 09:01:23-05:00 - exercise end
            Event(b'\x00\xe5\x1f\xd6\x97\xe3\x00\x0f\xfe\xb0\x00\x04\x02\x00\x00\x00\x00\x00\x00\xf0\x01\x03\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Exercising)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopExercise)

        time_end = arrow.get('2024-12-04T23:00:30-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 0)
        self.assertEqual(self.nightscout.deleted_entries, [])


    def test_start_and_stop_exercise(self):
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        events = [
            # 2024-12-04 23:00:23-05:00 - exercise start
            Event(b'\x00\xe5\x1f\xd7\\\x87\x00\x10\t\xaa\x00\x03\x00\x02\x00\x00\x01\x00\x00\xf0\x00\x01\x00\x00\x00\x00'),
            # 2024-12-05 09:01:23-05:00 - exercise end
            Event(b'\x00\xe5\x1f\xd7\xe9c\x00\x10\x10\xf8\x00\x04\x02\x00\x00\x00\x00\x00\x00\xf0\x00\x00\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Normal)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Exercising)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StartExercise)


        self.assertEqual(type(events[1]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[1].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Exercising)
        self.assertEqual(events[1].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[1].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopExercise)

        time_end = arrow.get('2024-12-05T10:00:00-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Exercise',
            "reason": 'Exercise',
            "notes": 'Exercise',
            "duration": 601.0,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050,1052920'
        })
        self.assertEqual(self.nightscout.deleted_entries, [])

    def test_stop_with_partial_last_uploaded(self):
        self.nightscout.last_uploaded_entry = lambda eventType, **kwargs: {
            'Exercise': {
                "eventType": 'Exercise',
                "reason": 'Exercise - Not Ended',
                "notes": 'Exercise - Not Ended',
                "duration": 0.11666666666666667,
                "created_at": '2024-12-04 23:00:23-05:00',
                "enteredBy": "Pump (tconnectsync)",
                "pump_event_id": '1051050',
                "_id": 'id_to_delete'
            }
        }.get(eventType)

        events = [
            # 2024-12-05 09:01:23-05:00 - exercise end
            Event(b'\x00\xe5\x1f\xd7\xe9c\x00\x10\x10\xf8\x00\x04\x02\x00\x00\x00\x00\x00\x00\xf0\x00\x00\x00\x00\x00\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidAaUserModeChange)
        self.assertEqual(events[0].previoususermode, eventtypes.LidAaUserModeChange.PrevioususermodeEnum.Exercising)
        self.assertEqual(events[0].currentusermode, eventtypes.LidAaUserModeChange.CurrentusermodeEnum.Normal)
        self.assertEqual(events[0].requestedaction, eventtypes.LidAaUserModeChange.RequestedactionEnum.StopExercise)

        time_end = arrow.get('2024-12-05T10:00:00-05:00')
        p = self.process.process(events, time_start=None, time_end=time_end)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            "eventType": 'Exercise',
            "reason": 'Exercise',
            "notes": 'Exercise',
            "duration": 601.0,
            "created_at": '2024-12-04 23:00:23-05:00',
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": '1051050,1052920'
        })
        self.assertEqual(self.nightscout.deleted_entries, ['treatments/id_to_delete'])




if __name__ == '__main__':
    unittest.main()