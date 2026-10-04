#!/usr/bin/env python3

import unittest

from tconnectsync.sync.tandemsource.process_device_status import ProcessDeviceStatus
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event, Events
from tconnectsync.eventparser.raw_event import RawEvent

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

# Every event 81 capture observed from a real pump, with its expected decode.
# The "Mobi @" labels are collection-time estimates; the pump's SoC byte wins.
OBSERVED_EVENTS = [
    {
        'raw': b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00',
        'seqNum': 1046436, 'timestampRaw': 534123623,
        'timestamp': '2024-12-03 23:40:23-05:00',
        'dailyTotalBasal': 22.3535, 'lastBasalRate': 0.8, 'iob': 3.9823,
        'liPoMV': 3830, 'abc': 55, 'displayInHistory': 0,
    },
    {
        'raw': b'\x00Q\x1f\xd6<?\x00\x0f\xf9[@\r\xcd{?\x9b\xa5\xe3?\xe3\x9a;\x0e\xf36\x00',
        'seqNum': 1046875, 'timestampRaw': 534133823,
        'timestamp': '2024-12-04 02:30:23-05:00',
        'dailyTotalBasal': 2.2157, 'lastBasalRate': 1.216, 'iob': 1.7781,
        'liPoMV': 3827, 'abc': 54, 'displayInHistory': 0,
    },
    {
        'raw': b'\x00Q\x1f\xd6k\x1f\x00\x0f\xfc>A\x0e\xa3\x80?\x9a~\xfa@\x11z6\x0e\xee5\x00',
        'seqNum': 1047614, 'timestampRaw': 534145823,
        'timestamp': '2024-12-04 05:50:23-05:00',
        'dailyTotalBasal': 8.9149, 'lastBasalRate': 1.207, 'iob': 2.2731,
        'liPoMV': 3822, 'abc': 53, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~80%
        'raw': b'\x00Q\x1f\xfdm\xf5\x00\x00\x04P@4\xa7\xed?L\xcc\xcd@+\xd8\x81\x0f\xa1P\x00',
        'seqNum': 1104, 'timestampRaw': 536702453,
        'timestamp': '2025-01-02 20:00:53-05:00',
        'dailyTotalBasal': 2.8227, 'lastBasalRate': 0.8, 'iob': 2.6851,
        'liPoMV': 4001, 'abc': 80, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~55%
        'raw': b'\x00Q \x04\x15\xdd\x00\x00E\xb1A\x86\xe0\xcf\x00\x00\x00\x00A9\xd2w\x0f\x1d=\x00',
        'seqNum': 17841, 'timestampRaw': 537138653,
        'timestamp': '2025-01-07 21:10:53-05:00',
        'dailyTotalBasal': 16.8598, 'lastBasalRate': 0.0, 'iob': 11.6139,
        'liPoMV': 3869, 'abc': 61, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~45%
        'raw': b'\x00Q \x04\xd8f\x00\x00L^A^\xc5\x9a>49X\x00\x00\x00\x00\x0e\xfa7\x00',
        'seqNum': 19550, 'timestampRaw': 537188454,
        'timestamp': '2025-01-08 11:00:54-05:00',
        'dailyTotalBasal': 13.9232, 'lastBasalRate': 0.176, 'iob': 0.0,
        'liPoMV': 3834, 'abc': 55, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~15%
        'raw': b'\x00Q \x06#U\x00\x00X{A\t\xed\xeb?\tx\xd5<\xe0\x81[\x0e\xb5 \x00',
        'seqNum': 22651, 'timestampRaw': 537273173,
        'timestamp': '2025-01-09 10:32:53-05:00',
        'dailyTotalBasal': 8.6206, 'lastBasalRate': 0.537, 'iob': 0.0274,
        'liPoMV': 3765, 'abc': 32, 'displayInHistory': 0,
    },
    {
        # Mobi @ MAX seen
        'raw': b'\x00Q \x19U=\x00\x01\x0f\xa8A\xa5\x04V?L\xcc\xcd?s\x83b\x10Pd\x01',
        'seqNum': 69544, 'timestampRaw': 538531133,
        'timestamp': '2025-01-23 23:58:53-05:00',
        'dailyTotalBasal': 20.6271, 'lastBasalRate': 0.8, 'iob': 0.9512,
        'liPoMV': 4176, 'abc': 100, 'displayInHistory': 1,
    },
    {
        # Mobi @ ~20%
        'raw': b'\x00Q \x1d\xbb\xa5\x00\x019zA\x1e\x1f`@%p\xa4>\xad\xaa\xf1\x0e\xc1$\x00',
        'seqNum': 80250, 'timestampRaw': 538819493,
        'timestamp': '2025-01-27 08:04:53-05:00',
        'dailyTotalBasal': 9.8827, 'lastBasalRate': 2.585, 'iob': 0.3392,
        'liPoMV': 3777, 'abc': 36, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~10%
        'raw': b'\x00Q \x1e\\m\x00\x01?}A\xa0\xe2\x8b?L\xcc\xcd?\xda\xeaj\x0e\xa1\x1b\x00',
        'seqNum': 81789, 'timestampRaw': 538860653,
        'timestamp': '2025-01-27 19:30:53-05:00',
        'dailyTotalBasal': 20.1106, 'lastBasalRate': 0.8, 'iob': 1.7103,
        'liPoMV': 3745, 'abc': 27, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~10%
        'raw': b'\x00Q \x1ej~\x00\x01@2A\xa5\xafZ\x00\x00\x00\x00@\x8c[\xed\x0e\x9f\x1a\x00',
        'seqNum': 81970, 'timestampRaw': 538864254,
        'timestamp': '2025-01-27 20:30:54-05:00',
        'dailyTotalBasal': 20.7106, 'lastBasalRate': 0.0, 'iob': 4.3862,
        'liPoMV': 3743, 'abc': 26, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~5%
        'raw': b'\x00Q \x1e\xa2\xbd\x00\x01C\x1a?\xd9?}@MO\xdf@uz<\x0e\x88\x15\x00',
        'seqNum': 82714, 'timestampRaw': 538878653,
        'timestamp': '2025-01-28 00:30:53-05:00',
        'dailyTotalBasal': 1.6973, 'lastBasalRate': 3.208, 'iob': 3.8356,
        'liPoMV': 3720, 'abc': 21, 'displayInHistory': 0,
    },
    {
        # Mobi @ ~5%
        'raw': b'\x00Q \x1e\xb0\xcd\x00\x01C\xd3@L9W@#33@\x8b\x04\xd2\x0e\x88\x15\x00',
        'seqNum': 82899, 'timestampRaw': 538882253,
        'timestamp': '2025-01-28 01:30:53-05:00',
        'dailyTotalBasal': 3.191, 'lastBasalRate': 2.55, 'iob': 4.3443,
        'liPoMV': 3720, 'abc': 21, 'displayInHistory': 0,
    },
]

# Captured over BLE from a second pump and re-serialized into Source byte order,
# so they are not "observed from a real pump" in the sense the table above is.
# They cover what the Source captures do not: the charging phase, and
# displayInHistory set. They are also what shows percent to be non-monotonic in
# voltage -- charging lifts terminal voltage well above the resting SoC curve,
# so a charging sample can read a higher voltage at a lower SoC than a resting
# one. Do not assert a global percent-vs-voltage correlation over these.
RESERIALIZED_BLE_EVENTS = [
    # Lowest SoC observed; the pump alarm-suspended for low battery 41 s later.
    {
        'raw': b'\x10Q#\x01\xb8\xe0\x00\x0b[o@\xe2\x93x=\xcc\xcc\xcd@P\xd6C\x0e\x82\x14\x00',
        'seqNum': 744303, 'timestampRaw': 587315424,
        'timestamp': '2026-08-11 15:10:24-04:00',
        'dailyTotalBasal': 7.0805, 'lastBasalRate': 0.1, 'iob': 3.2631,
        'liPoMV': 3714, 'abc': 20, 'displayInHistory': 0,
    },
    # displayInHistory set mid-afternoon, 1 s before PumpingResumed, no daily reset.
    {
        'raw': b'\x10Q#\x01\xba\xc5\x00\x0b[\x89@\xe2\x93x\x00\x00\x00\x00@;\x81\xed\x0e\xf0\x18\x01',
        'seqNum': 744329, 'timestampRaw': 587315909,
        'timestamp': '2026-08-11 15:18:29-04:00',
        'dailyTotalBasal': 7.0805, 'lastBasalRate': 0.0, 'iob': 2.9298,
        'liPoMV': 3824, 'abc': 24, 'displayInHistory': 1,
    },
    # Charging: higher voltage, lower SoC than the 3900 mV / 55% resting sample.
    {
        'raw': b'\x10Q#\x01\xbd\x85\x00\x0b[\xb1@\xe7\x1c\x02?\x80\x00\x00@\x1eho\x0fX0\x00',
        'seqNum': 744369, 'timestampRaw': 587316613,
        'timestamp': '2026-08-11 15:30:13-04:00',
        'dailyTotalBasal': 7.2222, 'lastBasalRate': 1.0, 'iob': 2.4751,
        'liPoMV': 3928, 'abc': 48, 'displayInHistory': 0,
    },
    {
        'raw': b'\x10Q#\x02\xd6\xc5\x00\x0bl\xf4@\xf6e\x08\x00\x00\x00\x00?\xa9eL\x10"W\x00',
        'seqNum': 748788, 'timestampRaw': 587388613,
        'timestamp': '2026-08-12 11:30:13-04:00',
        'dailyTotalBasal': 7.6998, 'lastBasalRate': 0.0, 'iob': 1.3234,
        'liPoMV': 4130, 'abc': 87, 'displayInHistory': 0,
    },
    # Day rollover: the next record, 00:00:13, has dailyTotalBasal 0.0.
    {
        'raw': b'\x10Q#\x024\x95\x00\x0bbfAIP\x93@ \x00\x00@\xb6\xb7\x17\x0f\x1a=\x01',
        'seqNum': 746086, 'timestampRaw': 587347093,
        'timestamp': '2026-08-11 23:58:13-04:00',
        'dailyTotalBasal': 12.5822, 'lastBasalRate': 2.5, 'iob': 5.7098,
        'liPoMV': 3866, 'abc': 61, 'displayInHistory': 1,
    },
    # The second rollover; three consecutive records carry final=1 here.
    {
        'raw': b'\x10Q#\x00\xe3 \x00\x0bOX@\xfabP\x00\x00\x00\x00AX\x99\xaa\x0e\xd3+\x01',
        'seqNum': 741208, 'timestampRaw': 587260704,
        'timestamp': '2026-08-10 23:58:24-04:00',
        'dailyTotalBasal': 7.8245, 'lastBasalRate': 0.0, 'iob': 13.5375,
        'liPoMV': 3795, 'abc': 43, 'displayInHistory': 1,
    },
]


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
        self.assertEqual(events[0].liPoMV, 3830)
        self.assertEqual(events[0].abc, 55)
        self.assertEqual(events[0].displayInHistory, 0)

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
        self.assertEqual(events[0].liPoMV, 3830)
        self.assertEqual(events[0].abc, 55)
        self.assertEqual(events[0].displayInHistory, 0)

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
        self.assertEqual(events[0].liPoMV, 3830)
        self.assertEqual(events[0].abc, 55)
        self.assertEqual(events[0].displayInHistory, 0)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].liPoMV, 3827)
        self.assertEqual(events[1].abc, 54)
        self.assertEqual(events[1].displayInHistory, 0)

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
        self.assertEqual(events[0].liPoMV, 3830)
        self.assertEqual(events[0].abc, 55)
        self.assertEqual(events[0].displayInHistory, 0)

        self.assertEqual(type(events[1]), eventtypes.LidDailyBasal)
        self.assertEqual(events[1].raw.timestampRaw, 534133823) # 2024-12-04 02:30:23-05:00
        self.assertEqual(events[1].liPoMV, 3827)
        self.assertEqual(events[1].abc, 54)
        self.assertEqual(events[1].displayInHistory, 0)

        self.assertEqual(type(events[2]), eventtypes.LidDailyBasal)
        self.assertEqual(events[2].raw.timestampRaw, 534145823) # 2024-12-04 05:50:23-05:00
        self.assertEqual(events[2].liPoMV, 3822)
        self.assertEqual(events[2].abc, 53)
        self.assertEqual(events[2].displayInHistory, 0)

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
            liPoMV=None,
            abc=None,
            displayInHistory=None,
        )

        p = self.process.process([event], time_start=None, time_end=None)
        self.assertEqual(p, [])

    def test_all_observed_events_parse(self):
        for expected in OBSERVED_EVENTS:
            with self.subTest(seqNum=expected['seqNum']):
                event = Event(expected['raw'])

                self.assertEqual(type(event), eventtypes.LidDailyBasal)
                self.assertEqual(event.eventId, 81)
                self.assertEqual(event.seqNum, expected['seqNum'])
                self.assertEqual(event.raw.timestampRaw, expected['timestampRaw'])
                self.assertEqual(event.eventTimestamp.format(), expected['timestamp'])

                self.assertAlmostEqual(event.dailyTotalBasal, expected['dailyTotalBasal'], places=4)
                self.assertAlmostEqual(event.lastBasalRate, expected['lastBasalRate'], places=4)
                self.assertAlmostEqual(event.iob, expected['iob'], places=4)

                self.assertEqual(event.liPoMV, expected['liPoMV'])
                self.assertEqual(event.abc, expected['abc'])
                self.assertEqual(event.displayInHistory, expected['displayInHistory'])

    def test_all_observed_events_have_sane_battery_fields(self):
        for expected in OBSERVED_EVENTS:
            with self.subTest(seqNum=expected['seqNum']):
                event = Event(expected['raw'])

                self.assertIsInstance(event.abc, int)
                self.assertGreaterEqual(event.abc, 0)
                self.assertLessEqual(event.abc, 100)

                self.assertGreater(event.liPoMV, 3000)
                self.assertLess(event.liPoMV, 4400)

                self.assertIn(event.displayInHistory, (0, 1))

    def test_all_reserialized_ble_events_parse(self):
        for expected in RESERIALIZED_BLE_EVENTS:
            with self.subTest(seqNum=expected['seqNum']):
                event = Event(expected['raw'])

                self.assertEqual(type(event), eventtypes.LidDailyBasal)
                self.assertEqual(event.eventId, 81)
                self.assertEqual(event.seqNum, expected['seqNum'])
                self.assertEqual(event.raw.timestampRaw, expected['timestampRaw'])
                self.assertEqual(event.eventTimestamp.format(), expected['timestamp'])

                self.assertAlmostEqual(event.dailyTotalBasal, expected['dailyTotalBasal'], places=4)
                self.assertAlmostEqual(event.lastBasalRate, expected['lastBasalRate'], places=4)
                self.assertAlmostEqual(event.iob, expected['iob'], places=4)

                self.assertEqual(event.liPoMV, expected['liPoMV'])
                self.assertEqual(event.abc, expected['abc'])
                self.assertEqual(event.displayInHistory, expected['displayInHistory'])

    def test_observed_events_upload_expected_device_status(self):
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        for expected in OBSERVED_EVENTS:
            with self.subTest(seqNum=expected['seqNum']):
                p = self.process.process([Event(expected['raw'])], time_start=None, time_end=None)

                self.assertEqual(len(p), 1)
                self.assertEqual(p[0]['created_at'], expected['timestamp'])
                self.assertEqual(p[0]['pump_event_id'], str(expected['seqNum']))
                self.assertEqual(p[0]['pump']['battery'], {
                    'status': '%d%%' % expected['abc'],
                    'percent': expected['abc'],
                    'voltage': expected['liPoMV'] / 1000,
                })

    def test_final_event_for_day_is_decoded_but_not_acted_on(self):
        # A close-out marker, usually but not only the daily rollover: one
        # capture sets it mid-afternoon, a second before PumpingResumed ends an
        # alarm suspension, with no daily reset. Either way nothing here acts
        # on it, so the device status is the same as for any other record.
        self.nightscout.last_uploaded_devicestatus = lambda *args, **kwargs: None

        event = Event(b'\x00Q \x19U=\x00\x01\x0f\xa8A\xa5\x04V?L\xcc\xcd?s\x83b\x10Pd\x01')
        self.assertEqual(event.displayInHistory, 1)

        p = self.process.process([event], time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['pump']['battery'], {
            'status': '100%',
            'percent': 100,
            'voltage': 4.176,
        })


if __name__ == '__main__':
    unittest.main()