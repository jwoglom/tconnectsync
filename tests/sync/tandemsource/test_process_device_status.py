#!/usr/bin/env python3

import unittest
import struct

from tconnectsync.sync.tandemsource.process_device_status import ProcessDeviceStatus
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.events import UINT16
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
                'clock': '2024-12-03 23:40:23-05:00',
                'battery': {
                    'status': '32%',
                    'percent': 32,
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
                'clock': '2024-12-04 02:30:23-05:00',
                'battery': {
                    'status': '31%',
                    'percent': 31,
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
                'clock': '2024-12-04 05:50:23-05:00',
                'battery': {
                    'status': '30%',
                    'percent': 30,
                    'voltage': 13.568
                }
            },
            'pump_event_id': '1047614'
        })

    @unittest.skip
    def test_device_status_battery_calculation(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        def test_percentage_about(percent_str, event):
            with self.subTest(percent_str, event=event):
                # p = self.process.process([event], time_start=None, time_end=None)
                # self.assertEqual(len(p), 1)
                # self.assertEqual(p[0]['pump']['battery']['status'], percent_str)
                msb = event.batterychargepercentmsbRaw
                lsb = event.batterychargepercentlsbRaw


                MAX = struct.unpack(UINT16, bytearray((16, 128)))[0]
                MIN = struct.unpack(UINT16, bytearray((14, 128)))[0]
                val = struct.unpack(UINT16, bytearray((msb, lsb)))[0]
                pct = (val - MIN)/(MAX-MIN)
                # print(pct)
                # print(struct.unpack(UINT16, bytearray((msb, lsb))
                # (14, 100) =~ 0%
                # (15, 100) =~ 50%
                # (16, 98) =~ 100%
                # msb*256 + lsb - 14*256
                # pct = (msb*256 + lsb - 14*256 - 100) / 512

                calc_str = "%.0f%s" % (100*pct, '%')
                print(f'comp {calc_str=} {percent_str=}')
                self.assertEqual(calc_str, percent_str)


        test_percentage_about('80%', Event(b'\x00Q\x1f\xfdm\xf5\x00\x00\x04P@4\xa7\xed?L\xcc\xcd@+\xd8\x81\x0f\xa1P\x00'))
        test_percentage_about('55%', Event(b'\x00Q \x04\x15\xdd\x00\x00E\xb1A\x86\xe0\xcf\x00\x00\x00\x00A9\xd2w\x0f\x1d=\x00'))
        test_percentage_about('45%', Event(b'\x00Q \x04\xd8f\x00\x00L^A^\xc5\x9a>49X\x00\x00\x00\x00\x0e\xfa7\x00'))
        test_percentage_about('15%', Event(b'\x00Q \x06#U\x00\x00X{A\t\xed\xeb?\tx\xd5<\xe0\x81[\x0e\xb5 \x00'))
        test_percentage_about('20%', Event(b'\x00Q \x1d\xbb\xa5\x00\x019zA\x1e\x1f`@%p\xa4>\xad\xaa\xf1\x0e\xc1$\x00'))
        test_percentage_about('10%', Event(b'\x00Q \x1e\\m\x00\x01?}A\xa0\xe2\x8b?L\xcc\xcd?\xda\xeaj\x0e\xa1\x1b\x00'))
        test_percentage_about('10%', Event(b'\x00Q \x1ej~\x00\x01@2A\xa5\xafZ\x00\x00\x00\x00@\x8c[\xed\x0e\x9f\x1a\x00'))
        test_percentage_about('5%', Event(b'\x00Q \x1e\xa2\xbd\x00\x01C\x1a?\xd9?}@MO\xdf@uz<\x0e\x88\x15\x00'))


# Mobi @ MAX seen
# bytearray(b'\x00Q \x19U=\x00\x01\x0f\xa8A\xa5\x04V?L\xcc\xcd?s\x83b\x10Pd\x01')
#   batterychargepercentmsbRaw=16, batterychargepercentlsbRaw=80, batterylipomillivolts=25601

# Mobi @ ~80%
# bytearray(b'\x00Q\x1f\xfdm\xf5\x00\x00\x04P@4\xa7\xed?L\xcc\xcd@+\xd8\x81\x0f\xa1P\x00'):
#   batterychargepercentmsbRaw=15, batterychargepercentlsbRaw=161, batterylipomillivolts=20480
#   calc batteryChargePercent = 0.54296875

# Mobi @ ~55%
# bytearray(b'\x00Q \x04\x15\xdd\x00\x00E\xb1A\x86\xe0\xcf\x00\x00\x00\x00A9\xd2w\x0f\x1d=\x00')
#    batterychargepercentmsbRaw=15, batterychargepercentlsbRaw=29, batterylipomillivolts=15616
#    calc batteryChargePercent = 0.37109375

# Mobi @ ~45%
# bytearray(b'\x00Q \x04\xd8f\x00\x00L^A^\xc5\x9a>49X\x00\x00\x00\x00\x0e\xfa7\x00')
#    batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=250 batterylipomillivolts=14080
#    calc batteryChargePercent = 0.3255208333333333

# Mobi @ ~15%
# bytearray(b'\x00Q \x06#U\x00\x00X{A\t\xed\xeb?\tx\xd5<\xe0\x81[\x0e\xb5 \x00')
#   batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=181 batterylipomillivolts=8192
#   calc batteryChargePercent = 0.23567708333333334

# Mobi @ ~20%
# bytearray(b'\x00Q \x1d\xbb\xa5\x00\x019zA\x1e\x1f`@%p\xa4>\xad\xaa\xf1\x0e\xc1$\x00')
#   batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=193 batterylipomillivolts=9216
#   calc batteryChargePercent = 0.2513020833333333

# Mobi @ ~10%
# bytearray(b'\x00Q \x1e\\m\x00\x01?}A\xa0\xe2\x8b?L\xcc\xcd?\xda\xeaj\x0e\xa1\x1b\x00')
#    batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=161 batterylipomillivolts=6912
#    calc batteryChargePercent = 0.20963541666666666

# Mobi @ ~10%
# bytearray(b'\x00Q \x1ej~\x00\x01@2A\xa5\xafZ\x00\x00\x00\x00@\x8c[\xed\x0e\x9f\x1a\x00')
#   batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=159 batterylipomillivolts=6656
#   calc batteryChargePercent = 0.20703125

# Mobi @ ~5%
# bytearray(b'\x00Q \x1e\xa2\xbd\x00\x01C\x1a?\xd9?}@MO\xdf@uz<\x0e\x88\x15\x00')
#   batterychargepercentmsbRaw=14, batterychargepercentlsbRaw=136
#   calc batteryChargePercent = 0.17708333333333334 batterylipomillivolts=5376

# Mobi @ ~5%
# bytearray(b'\x00Q \x1e\xb0\xcd\x00\x01C\xd3@L9W@#33@\x8b\x04\xd2\x0e\x88\x15\x00')
#   batterychargepercentmsbRaw=14 batterychargepercentlsbRaw=136 batterylipomillivolts=5376
#   calc 0.17708333333333334


if __name__ == '__main__':
    unittest.main()