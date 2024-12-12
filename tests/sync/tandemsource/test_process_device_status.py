#!/usr/bin/env python3

import unittest

from tconnectsync.sync.tandemsource.process_device_status import ProcessDeviceStatus
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

class TestProcessDeviceStatus(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessDeviceStatus(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False)

    def test_single_event_no_last_uploaded(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        events = [
            Event(b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidDailyBasal)
        self.assertEqual(events[0].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[0].batterychargepercentlsbRaw, 246)
        self.assertEqual(events[0].batterylipomillivolts, 14080)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-03 23:40:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'battery': {
                    'string': '48%',
                    'voltage': 14.08
                }
            },
            'pump_event_id': '1046436'
        })

    def test_single_event_already_uploaded(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: {'created_at': '2024-12-03 23:40:23-05:00'}

        events = [
            Event(b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidDailyBasal)
        self.assertEqual(events[0].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[0].batterychargepercentlsbRaw, 246)
        self.assertEqual(events[0].batterylipomillivolts, 14080)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 0)


    def test_multiple_event_with_last_uploaded(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: {'created_at': '2024-12-03 23:40:23-05:00'}

        events = [
            Event(b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00'),
            Event(b'\x00Q\x1f\xd6<?\x00\x0f\xf9[@\r\xcd{?\x9b\xa5\xe3?\xe3\x9a;\x0e\xf36\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidDailyBasal)
        self.assertEqual(events[0].raw.timestampRaw, 534123623) # 2024-12-03 23:40:23-05:00
        self.assertEqual(events[0].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[0].batterychargepercentlsbRaw, 246)
        self.assertEqual(events[0].batterylipomillivolts, 14080)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[1].batterychargepercentlsbRaw, 243)
        self.assertEqual(events[1].batterylipomillivolts, 13824)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-04 02:30:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'battery': {
                    'string': '47%',
                    'voltage': 13.824
                }
            },
            'pump_event_id': '1046875'
        })

    def test_multiple_event_only_latest_applied(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: {'created_at': '2024-12-03 23:40:23-05:00'}

        events = [
            Event(b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00'),
            Event(b'\x00Q\x1f\xd6<?\x00\x0f\xf9[@\r\xcd{?\x9b\xa5\xe3?\xe3\x9a;\x0e\xf36\x00'),
            Event(b'\x00Q\x1f\xd6k\x1f\x00\x0f\xfc>A\x0e\xa3\x80?\x9a~\xfa@\x11z6\x0e\xee5\x00')
        ]

        self.assertEqual(type(events[0]), eventtypes.LidDailyBasal)
        self.assertEqual(events[0].raw.timestampRaw, 534123623) # 2024-12-03 23:40:23-05:00
        self.assertEqual(events[0].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[0].batterychargepercentlsbRaw, 246)
        self.assertEqual(events[0].batterylipomillivolts, 14080)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[1].batterychargepercentlsbRaw, 243)
        self.assertEqual(events[1].batterylipomillivolts, 13824)

        self.assertEqual(type(events[2]), eventtypes.LidDailyBasal)
        self.assertEqual(events[2].raw.timestampRaw, 534145823) # 2024-12-04 05:50:23-05:00
        self.assertEqual(events[2].batterychargepercentmsbRaw, 14)
        self.assertEqual(events[2].batterychargepercentlsbRaw, 238)
        self.assertEqual(events[2].batterylipomillivolts, 13568)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-04 05:50:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'battery': {
                    'string': '46%',
                    'voltage': 13.568
                }
            },
            'pump_event_id': '1047614'
        })






if __name__ == '__main__':
    unittest.main()