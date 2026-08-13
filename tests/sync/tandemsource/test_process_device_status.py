#!/usr/bin/env python3

import unittest

from tconnectsync.sync.tandemsource.process_device_status import ProcessDeviceStatus
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event, Events
from tconnectsync.eventparser.raw_event import RawEvent

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
        self.assertEqual(events[0].batteryLipoMilliVolts, 3830)
        self.assertEqual(events[0].batteryChargePercent, 55)
        self.assertEqual(events[0].finalEventForDay, 0)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-03 23:40:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'clock': '2024-12-03 23:40:23-05:00',
                'battery': {
                    'status': '55%',
                    'percent': 55,
                    'voltage': 3.83
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
        self.assertEqual(events[0].batteryLipoMilliVolts, 3830)
        self.assertEqual(events[0].batteryChargePercent, 55)
        self.assertEqual(events[0].finalEventForDay, 0)

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
        self.assertEqual(events[0].batteryLipoMilliVolts, 3830)
        self.assertEqual(events[0].batteryChargePercent, 55)
        self.assertEqual(events[0].finalEventForDay, 0)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].batteryLipoMilliVolts, 3827)
        self.assertEqual(events[1].batteryChargePercent, 54)
        self.assertEqual(events[1].finalEventForDay, 0)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-04 02:30:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'clock': '2024-12-04 02:30:23-05:00',
                'battery': {
                    'status': '54%',
                    'percent': 54,
                    'voltage': 3.827
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
        self.assertEqual(events[0].batteryLipoMilliVolts, 3830)
        self.assertEqual(events[0].batteryChargePercent, 55)
        self.assertEqual(events[0].finalEventForDay, 0)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].batteryLipoMilliVolts, 3827)
        self.assertEqual(events[1].batteryChargePercent, 54)
        self.assertEqual(events[1].finalEventForDay, 0)

        self.assertEqual(type(events[2]), eventtypes.LidDailyBasal)
        self.assertEqual(events[2].raw.timestampRaw, 534145823) # 2024-12-04 05:50:23-05:00
        self.assertEqual(events[2].batteryLipoMilliVolts, 3822)
        self.assertEqual(events[2].batteryChargePercent, 53)
        self.assertEqual(events[2].finalEventForDay, 0)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'created_at': '2024-12-04 05:50:23-05:00',
            'device': 'Pump (tconnectsync)',
            'pump': {
                'clock': '2024-12-04 05:50:23-05:00',
                'battery': {
                    'status': '53%',
                    'percent': 53,
                    'voltage': 3.822
                }
            },
            'pump_event_id': '1047614'
        })

    def test_no_daily_basal_event_degrades_gracefully(self):
        # DEVICE_STATUS relies on event 81 (LidDailyBasal), which is not in
        # Tandem's default id list and may not be returned by the pump-logs
        # endpoint. When it is absent the processor must return nothing rather
        # than raise. Feed a real non-daily-basal event (eventCode 16).
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        events = [Event({
            "eventCode": 16,
            "sequenceGroup": 0,
            "sequenceNumber": 100,
            "pumpDateTime": "2024-12-03T23:40:23",
            "eventProperties": {"iob": 1.25, "bg": 112},
        })]

        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual(p, [])

    def test_daily_basal_missing_battery_is_skipped(self):
        # If an event 81 is returned without parseable battery fields, skip it
        # instead of raising on the battery-percent arithmetic.
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        raw = RawEvent.build_from_json({
            "eventCode": 81,
            "sequenceNumber": 200,
            "pumpDateTime": "2024-12-03T23:40:23",
        })
        event = eventtypes.LidDailyBasal(
            raw=raw,
            dailyTotalBasal=None,
            lastBasalRate=None,
            iob=None,
            batteryLipoMilliVolts=None,
            batteryChargePercent=None,
            finalEventForDay=None,
        )

        p = self.process.process([event], time_start=None, time_end=None)
        self.assertEqual(p, [])

    def test_device_status_battery_percent_is_the_pumps_own_byte(self):
        # The SoC byte is emitted verbatim: no scaling, no derivation from the
        # millivolt bytes. Across a spread of real captures it stays within
        # 0-100 and tracks batteryLipoMilliVolts monotonically.
        captures = [
            # (raw event, batteryLipoMilliVolts, batteryChargePercent)
            (b'\x00Q \x19U=\x00\x01\x0f\xa8A\xa5\x04V?L\xcc\xcd?s\x83b\x10Pd\x01', 4176, 100),
            (b'\x00Q\x1f\xfdm\xf5\x00\x00\x04P@4\xa7\xed?L\xcc\xcd@+\xd8\x81\x0f\xa1P\x00', 4001, 80),
            (b'\x00Q \x04\x15\xdd\x00\x00E\xb1A\x86\xe0\xcf\x00\x00\x00\x00A9\xd2w\x0f\x1d=\x00', 3869, 61),
            (b'\x00Q \x04\xd8f\x00\x00L^A^\xc5\x9a>49X\x00\x00\x00\x00\x0e\xfa7\x00', 3834, 55),
            (b'\x00Q \x1d\xbb\xa5\x00\x019zA\x1e\x1f`@%p\xa4>\xad\xaa\xf1\x0e\xc1$\x00', 3777, 36),
            (b'\x00Q \x06#U\x00\x00X{A\t\xed\xeb?\tx\xd5<\xe0\x81[\x0e\xb5 \x00', 3765, 32),
            (b'\x00Q \x1e\\m\x00\x01?}A\xa0\xe2\x8b?L\xcc\xcd?\xda\xeaj\x0e\xa1\x1b\x00', 3745, 27),
            (b'\x00Q \x1ej~\x00\x01@2A\xa5\xafZ\x00\x00\x00\x00@\x8c[\xed\x0e\x9f\x1a\x00', 3743, 26),
            (b'\x00Q \x1e\xa2\xbd\x00\x01C\x1a?\xd9?}@MO\xdf@uz<\x0e\x88\x15\x00', 3720, 21),
            (b'\x00Q \x1e\xb0\xcd\x00\x01C\xd3@L9W@#33@\x8b\x04\xd2\x0e\x88\x15\x00', 3720, 21),
        ]

        for raw, millivolts, percent in captures:
            with self.subTest(millivolts=millivolts):
                event = Event(raw)
                self.assertEqual(type(event), eventtypes.LidDailyBasal)
                self.assertEqual(event.batteryLipoMilliVolts, millivolts)
                self.assertEqual(event.batteryChargePercent, percent)
                self.assertLessEqual(event.batteryChargePercent, 100)

        # Sorted descending by voltage above; percent must be non-increasing.
        percents = [percent for _, _, percent in captures]
        self.assertEqual(percents, sorted(percents, reverse=True))

    def test_final_event_for_day_is_decoded_but_not_acted_on(self):
        # The only capture in this set with finalEventForDay=1 is the 23:58
        # end-of-day record. Decoding it must not change what is uploaded.
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        event = Event(b'\x00Q \x19U=\x00\x01\x0f\xa8A\xa5\x04V?L\xcc\xcd?s\x83b\x10Pd\x01')
        self.assertEqual(event.finalEventForDay, 1)

        p = self.process.process([event], time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['pump']['battery'], {
            'status': '100%',
            'percent': 100,
            'voltage': 4.176,
        })


if __name__ == '__main__':
    unittest.main()