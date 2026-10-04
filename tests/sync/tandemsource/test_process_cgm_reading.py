#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process_cgm_reading import ProcessCGMReading
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event, Events

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

# timestamp 2025-12-13T18:16:44-0500, value 80
G7_EVENT_1 = b'\x01\x8f!\xc4+\x0f\x00\x07\xb8\r\xf7\x01\x00\x00\x00P\xc7 !\xc4+\x0c\x00\x00\x19\xe1'
# timestamp 2025-12-13T18:21:44-0500, value 71
G7_EVENT_2 = b'\x01\x8f!\xc4,;\x00\x07\xb8\x1a\xf4\x01\x00\x00\x00G\xc1 !\xc4,8\x00\x00\x19\xe1'
# timestamp 2025-12-13T18:46:44-0500, value 119
G7_EVENT_3 = b'\x01\x8f!\xc42\x17\x00\x07\xb8\xd6\x13\x01\x00\x00\x00w\xc1 !\xc42\x14\x00\x00\x19\xe1'
# timestamp 2025-12-13T18:51:44-0500, value 105
G7_EVENT_4 = b'\x01\x8f!\xc43C\x00\x07\xb8\xea\x13\x01\x00\x00\x00\x81\xbf !\xc43@\x00\x00\x19\xe1'
# timestamp 2025-12-13T18:56:44-0500, value 98
G7_EVENT_5 = b"\x01\x8f!\xc45\x9b\x00\x07\xb9\'\x11\x01\x00\x00\x00\x92\xbb !\xc45\x98\x00\x00\x19\xe1"


class TestProcessCGMReadingG7(unittest.TestCase):
    """Test with only G7 reading data"""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone='America/New_York')

    def test_single_g7_reading_no_last_uploaded(self):
        """Test processing a single G7 CGM reading with no prior uploads"""
        events = [Event(G7_EVENT_1)]

        self.assertEqual(type(events[0]), eventtypes.LidCgmDataG7)
        self.assertEqual(events[0].raw.timestampRaw, 566504207)
        self.assertEqual(events[0].egvTimeStamp, 566504204)
        self.assertEqual(events[0].seqNum, 505869)
        self.assertEqual(events[0].currentGlucoseDisplayValue, 80)
        self.assertEqual(events[0].rate, -9)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertIn('sgv', p[0])
        self.assertEqual(p[0]['sgv'], 80)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:16:44-0500')

    def test_multiple_g7_readings(self):
        """Test processing multiple G7 CGM readings"""
        events = [
            Event(G7_EVENT_1),
            Event(G7_EVENT_2),
            Event(G7_EVENT_3)
        ]

        # Verify all events are LidCgmDataG7
        for event in events:
            self.assertEqual(type(event), eventtypes.LidCgmDataG7)

        self.assertEqual(events[0].currentGlucoseDisplayValue, 80)
        self.assertEqual(events[1].currentGlucoseDisplayValue, 71)
        self.assertEqual(events[2].currentGlucoseDisplayValue, 119)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 3)

        # Check glucose values
        self.assertEqual(p[0]['sgv'], 80)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:16:44-0500')
        self.assertEqual(p[1]['sgv'], 71)
        self.assertEqual(p[1]['dateString'], '2025-12-13T18:21:44-0500')
        self.assertEqual(p[2]['sgv'], 119)
        self.assertEqual(p[2]['dateString'], '2025-12-13T18:46:44-0500')

    def test_g7_reading_with_last_uploaded(self):
        """Test that already uploaded readings are skipped"""
        events = [
            Event(G7_EVENT_1),
            Event(G7_EVENT_2),
            Event(G7_EVENT_3)
        ]

        # Set last upload time to be between event 1 and event 2
        event_1_time = self.process.timestamp_for(events[0])
        event_2_time = self.process.timestamp_for(events[1])

        # Set last upload to event 1's timestamp
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: {
            'dateString': event_1_time.format()
        }

        p = self.process.process(events, time_start=None, time_end=None)

        # Only events 2 and 3 should be processed (after the last upload time)
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0]['sgv'], 71)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:21:44-0500')
        self.assertEqual(p[1]['sgv'], 119)
        self.assertEqual(p[1]['dateString'], '2025-12-13T18:46:44-0500')


# timestamp 2022-01-28T00:01:09, value 75
G6_EVENT_1 = b'\x01\x00\x1ay\xaf\xc5\x00\x02\x00m\xfc\x01\x00\x00\x00K\xaf\x06\x1ay\xaf\xc5\x01\x00\x01\xe1'

# timestamp 2022-01-28T00:06:08, value 77
G6_EVENT_2 = b'\x01\x00\x1ay\xb0\xf0\x00\x02\x00v\xfd\x01\x00\x00\x00M\xa8\x06\x1ay\xb0\xf0\x01\x00\x01\xe1'

# timestamp 2022-01-28T01:51:07, value 76, BACKFILL
G6_EVENT_3 = b'\x01\x00\x1ay\xca\xb7\x00\x02\x01>\x00\x02\x00\x00\x00L\xb5\x06\x1ay\xc9\x8b\x00\x01\x01\xe2'

# timestamp 2022-01-28T01:56:07, value 75
G6_EVENT_4 = b'\x01\x00\x1ay\xca\xb7\x00\x02\x01=\x01\x01\x00\x00\x00K\xb5\x06\x1ay\xca\xb7\x02\x00\x01\xe1'

# timestamp 2022-01-28T02:01:06, value 74
G6_EVENT_5 = b'\x01\x00\x1ay\xcb\xe2\x00\x02\x01G\x00\x01\x00\x00\x00J\xb5\x06\x1ay\xcb\xe2\x01\x00\x01\xe1'

class TestProcessCGMReadingG6(unittest.TestCase):
    """Test with only G6 reading data"""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone='America/New_York')

    def test_single_g6_reading_no_last_uploaded(self):
        """Test processing a single G6 CGM reading with no prior uploads"""
        events = [Event(G6_EVENT_1)]

        # timestamp 2022-01-28T00:01:09 confirmed w/ tandem csv export
        self.assertEqual(type(events[0]), eventtypes.LidCgmDataGxb)
        self.assertEqual(events[0].raw.timestampRaw, 444182469)
        self.assertEqual(events[0].egvTimeStamp, 444182469)
        self.assertEqual(events[0].currentGlucoseDisplayValue, 75)
        self.assertEqual(events[0].rate, -4)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertIn('sgv', p[0])
        self.assertEqual(p[0]['sgv'], 75)
        self.assertEqual(p[0]['dateString'], '2022-01-28T00:01:09-0500')

    def test_multiple_g6_readings(self):
        """Test processing multiple G6 CGM readings"""
        events = [
            Event(G6_EVENT_1),
            Event(G6_EVENT_2),
            Event(G6_EVENT_3)
        ]

        # Verify all events are LidCgmDataGxb
        for event in events:
            self.assertEqual(type(event), eventtypes.LidCgmDataGxb)

        self.assertEqual(events[0].currentGlucoseDisplayValue, 75)
        self.assertEqual(events[1].currentGlucoseDisplayValue, 77)
        self.assertEqual(events[2].currentGlucoseDisplayValue, 76)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 3)

        self.assertEqual(p[0]['sgv'], 75)
        self.assertEqual(p[0]['dateString'], '2022-01-28T00:01:09-0500')
        self.assertEqual(p[1]['sgv'], 77)
        self.assertEqual(p[1]['dateString'], '2022-01-28T00:06:08-0500')
        self.assertEqual(p[2]['sgv'], 76)
        self.assertEqual(p[2]['dateString'], '2022-01-28T01:51:07-0500')

    def test_multiple_g6_readings_with_backfill(self):
        """Test processing multiple G6 CGM readings"""
        events = [
            Event(G6_EVENT_1),
            Event(G6_EVENT_2),
            Event(G6_EVENT_3),
            Event(G6_EVENT_4),
            Event(G6_EVENT_5)
        ]

        # Verify all events are LidCgmDataGxb
        for event in events:
            self.assertEqual(type(event), eventtypes.LidCgmDataGxb)

        self.assertEqual(events[0].currentGlucoseDisplayValue, 75)
        self.assertEqual(events[1].currentGlucoseDisplayValue, 77)
        self.assertEqual(events[2].currentGlucoseDisplayValue, 76) # backfill
        self.assertEqual(events[3].currentGlucoseDisplayValue, 75)
        self.assertEqual(events[4].currentGlucoseDisplayValue, 74)

        self.assertEqual(events[0].raw.timestampRaw, 444182469)
        self.assertEqual(events[1].raw.timestampRaw, 444182768)
        self.assertEqual(events[2].raw.timestampRaw, 444189367)
        self.assertEqual(events[3].raw.timestampRaw, 444189367)
        self.assertEqual(events[4].raw.timestampRaw, 444189666)

        self.assertEqual(events[0].egvTimeStamp, 444182469)
        self.assertEqual(events[1].egvTimeStamp, 444182768)
        self.assertEqual(events[2].egvTimeStamp, 444189067)
        self.assertEqual(events[3].egvTimeStamp, 444189367)
        self.assertEqual(events[4].egvTimeStamp, 444189666)


        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 5)

        self.assertEqual(p[0]['sgv'], 75)
        self.assertEqual(p[0]['dateString'], '2022-01-28T00:01:09-0500')
        self.assertEqual(p[1]['sgv'], 77)
        self.assertEqual(p[1]['dateString'], '2022-01-28T00:06:08-0500')
        self.assertEqual(p[2]['sgv'], 76)
        self.assertEqual(p[2]['dateString'], '2022-01-28T01:51:07-0500')
        self.assertEqual(p[3]['sgv'], 75)
        self.assertEqual(p[3]['dateString'], '2022-01-28T01:56:07-0500')
        self.assertEqual(p[4]['sgv'], 74)
        self.assertEqual(p[4]['dateString'], '2022-01-28T02:01:06-0500')


    def test_g6_reading_with_last_uploaded(self):
        """Test that already uploaded G6 readings are skipped"""
        events = [
            Event(G6_EVENT_1),
            Event(G6_EVENT_2),
            Event(G6_EVENT_3)
        ]

        # Set last upload time using 'date' field (milliseconds)
        event_1_time = self.process.timestamp_for(events[0])
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: {
            'date': event_1_time.timestamp() * 1000
        }

        p = self.process.process(events, time_start=None, time_end=None)

        # Only events 2 and 3 should be processed
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0]['sgv'], 77)
        self.assertEqual(p[1]['sgv'], 76)


class TestProcessCGMReadingWrite(unittest.TestCase):
    """Tests for writing CGM readings to Nightscout"""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.tconnect_device_id = 'abcdef'

    def test_write_entries_pretend_mode(self):
        """Test that pretend mode doesn't actually upload"""
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=True, timezone='America/New_York')

        events = [Event(G7_EVENT_1)]

        ns_entries = process.process(events, time_start=None, time_end=None)
        count = process.write(ns_entries)

        self.assertEqual(count, 1)
        # In pretend mode, nothing should be uploaded
        self.assertEqual(len(self.nightscout.uploaded_entries.get('entries', [])), 0)

    def test_write_entries_real_mode(self):
        """Test that real mode uploads entries"""
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone='America/New_York')

        events = [Event(G7_EVENT_1)]

        ns_entries = process.process(events, time_start=None, time_end=None)
        count = process.write(ns_entries)

        self.assertEqual(count, 1)
        # In real mode, entries should be uploaded
        self.assertEqual(len(self.nightscout.uploaded_entries['entries']), 1)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][0]['sgv'], 80)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][0]['dateString'], '2025-12-13T18:16:44-0500')

    def test_write_mixed_g6_and_g7(self):
        """Test writing a mix of G6 and G7 readings"""
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone='America/New_York')

        events = [
            Event(G6_EVENT_1),
            Event(G6_EVENT_2),
            Event(G7_EVENT_1),
            Event(G7_EVENT_2)
        ]

        ns_entries = process.process(events, time_start=None, time_end=None)
        count = process.write(ns_entries)

        self.assertEqual(count, 4)
        self.assertEqual(len(self.nightscout.uploaded_entries['entries']), 4)
        # g6
        self.assertEqual(self.nightscout.uploaded_entries['entries'][0]['sgv'], 75)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][0]['dateString'], '2022-01-28T00:01:09-0500')
        self.assertEqual(self.nightscout.uploaded_entries['entries'][1]['sgv'], 77)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][1]['dateString'], '2022-01-28T00:06:08-0500')
        # g7
        self.assertEqual(self.nightscout.uploaded_entries['entries'][2]['sgv'], 80)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][2]['dateString'], '2025-12-13T18:16:44-0500')
        self.assertEqual(self.nightscout.uploaded_entries['entries'][3]['sgv'], 71)
        self.assertEqual(self.nightscout.uploaded_entries['entries'][3]['dateString'], '2025-12-13T18:21:44-0500')


class TestProcessCGMReadingMultipleTimezones(unittest.TestCase):
    """Test timezone processing across TIMEZONE_NAME values."""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.tconnect_device_id = 'abcdef'

    def test_America_New_York(self):
        timezone = 'America/New_York'

        events = [Event(G7_EVENT_1)]
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone=timezone)
        p = process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:16:44-0500')

    def test_America_Chicago(self):
        timezone = 'America/Chicago'

        events = [Event(G7_EVENT_1)]
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone=timezone)
        p = process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:16:44-0600')

    def test_GMT(self):
        timezone = 'Etc/GMT'

        events = [Event(G7_EVENT_1)]
        process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone=timezone)
        p = process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['dateString'], '2025-12-13T18:16:44+0000')


# FSL3 events (real data from pump sync)
# timestamp 2026-03-15T13:12:57-05:00, seqNum=785470, sgv=149
FSL3_DATA_EVENT_1 = b'\x01\xe0"=-\xd9\x00\x0b\xfc>\x00\x00 \x00\x00\x95\xb5d"=-\xd9\x00\x00#\xe0'
# timestamp 2026-03-15T13:13:56-05:00, seqNum=785472, sgv=161
FSL3_DATA_EVENT_2 = b'\x01\xe0"=.\x14\x00\x0b\xfc@\x00\x00 \x00\x00\x95\xb5d"=.\x14\x00\x00#\xe0'
# timestamp 2026-03-09T17:39:22-05:00, seqNum=749962 (JOIN event)
FSL3_JOIN_EVENT_1 = b'\x01\xdd"5\x83J\x00\x0bq\x8ai\xaf\x05\xc1i\xaf\x05\xc8\x00\x00\t\x0f\x00\x13\xc6\x80'


class TestProcessCGMReadingFSL3(unittest.TestCase):
    """Test with FSL3 reading data"""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.tconnect_device_id = 'abcdef'
        self.process = ProcessCGMReading(self.tconnect, self.nightscout, self.tconnect_device_id, pretend=False, timezone='America/New_York')

    def test_single_fsl3_reading_no_last_uploaded(self):
        """Test processing a single FSL3 CGM reading with no prior uploads"""
        events = [Event(FSL3_DATA_EVENT_1)]

        self.assertEqual(type(events[0]), eventtypes.LidCgmDataFsl3)
        self.assertEqual(events[0].seqNum, 785470)
        self.assertEqual(events[0].currentGlucoseDisplayValue, 149)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 1)
        self.assertIn('sgv', p[0])
        self.assertEqual(p[0]['sgv'], 149)

    def test_multiple_fsl3_readings(self):
        """Test processing multiple FSL3 CGM readings"""
        events = [
            Event(FSL3_DATA_EVENT_1),
            Event(FSL3_DATA_EVENT_2)
        ]

        # Verify all events are LidCgmDataFsl3
        for event in events:
            self.assertEqual(type(event), eventtypes.LidCgmDataFsl3)

        self.assertEqual(events[0].currentGlucoseDisplayValue, 149)
        self.assertEqual(events[1].currentGlucoseDisplayValue, 149)

        p = self.process.process(events, time_start=None, time_end=None)

        self.assertEqual(len(p), 2)

        # Check glucose values
        self.assertEqual(p[0]['sgv'], 149)
        self.assertEqual(p[1]['sgv'], 149)

    def test_fsl3_join_event_parses(self):
        """Test that FSL3 JOIN event parses correctly"""
        events = [Event(FSL3_JOIN_EVENT_1)]

        self.assertEqual(type(events[0]), eventtypes.LidCgmJoinSessionFsl3)
        self.assertEqual(events[0].seqNum, 749962)


# Real LID_CGM_DATA_G7 pump-logs JSON events captured from a live Mobi account
# (deviceAssignmentId redacted). These exercise the production path
# (Events -> ProcessCGMReading) rather than the binary decoder.
G7_JSON_1 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 416999, "pumpDateTime": "2026-05-07T00:01:04", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 8, "algorithmState": 32, "rssi": -59, "currentGlucoseDisplayValue": 249, "egvTimeStamp": 578966461, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-07T00:01:04Z"}
G7_JSON_2 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 417212, "pumpDateTime": "2026-05-07T01:06:04", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": -12, "algorithmState": 32, "rssi": -57, "currentGlucoseDisplayValue": 193, "egvTimeStamp": 578970361, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-07T01:06:04Z"}
G7_JSON_3 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 417300, "pumpDateTime": "2026-05-07T01:51:04", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": -10, "algorithmState": 32, "rssi": -51, "currentGlucoseDisplayValue": 118, "egvTimeStamp": 578973061, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-07T01:51:04Z"}
G7_JSON_4 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 440616, "pumpDateTime": "2026-05-13T19:46:30", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 5, "algorithmState": 32, "rssi": -67, "currentGlucoseDisplayValue": 321, "egvTimeStamp": 579555987, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-13T19:46:30Z"}
G7_JSON_5 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 450283, "pumpDateTime": "2026-05-16T15:34:52", "eventProperties": {"glucoseValueStatus": 2, "cgmDataType": [0], "rate": -5, "algorithmState": 32, "rssi": -52, "currentGlucoseDisplayValue": 38, "egvTimeStamp": 579800089, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-16T15:34:52Z"}
G7_JSON_6 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 483972, "pumpDateTime": "2026-05-25T22:14:11", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 15, "algorithmState": 32, "rssi": -79, "currentGlucoseDisplayValue": 361, "egvTimeStamp": 580601648, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-25T22:14:11Z"}


class TestProcessCGMReadingG7Json(unittest.TestCase):
    """Same processor exercised via real pump-logs JSON (production path)."""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.process = ProcessCGMReading(self.tconnect, self.nightscout, 'abcdef', pretend=False, timezone='America/New_York')

    def test_single_g7_json_reading(self):
        events = list(Events([dict(G7_JSON_1)]))
        self.assertEqual(type(events[0]), eventtypes.LidCgmDataG7)
        self.assertEqual(events[0].egvTimeStamp, 578966461)

        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['sgv'], 249)
        self.assertEqual(p[0]['dateString'], '2026-05-07T00:01:01-0400')
        self.assertEqual(p[0]['pump_event_id'], '416999')

    def test_diverse_glucose_range(self):
        events = list(Events([
            dict(G7_JSON_1), dict(G7_JSON_2), dict(G7_JSON_3),
            dict(G7_JSON_4), dict(G7_JSON_5), dict(G7_JSON_6)
        ]))
        p = self.process.process(events, time_start=None, time_end=None)
        # The SpecialLow reading (raw 38) is reported as the LOW sentinel 39.
        self.assertEqual([e['sgv'] for e in p], [249, 193, 118, 321, 39, 361])
        self.assertEqual([e['dateString'] for e in p], [
            '2026-05-07T00:01:01-0400',
            '2026-05-07T01:06:01-0400',
            '2026-05-07T01:51:01-0400',
            '2026-05-13T19:46:27-0400',
            '2026-05-16T15:34:49-0400',
            '2026-05-25T22:14:08-0400',
        ])
        self.assertEqual([e['pump_event_id'] for e in p], [
            '416999', '417212', '417300', '440616', '450283', '483972'
        ])

    def test_special_low_reading(self):
        # glucoseValueStatus SpecialLow reports the LOW sentinel (39), not the
        # raw below-range display value (38).
        events = list(Events([dict(G7_JSON_5)]))
        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['sgv'], 39)

    def test_skips_readings_at_or_before_last_upload(self):
        # Only readings strictly after the last Nightscout upload are returned.
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: {'dateString': '2026-05-07T01:06:01-0400'}
        events = list(Events([dict(G7_JSON_1), dict(G7_JSON_2), dict(G7_JSON_3)]))
        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual([e['sgv'] for e in p], [118])


# Real LID_CGM_DATA_GXB (Dexcom G6, eventCode 256) pump-logs JSON events captured
# from a live t:slim X2 account (early 2023, deviceAssignmentId redacted). These
# exercise the production path (Events -> ProcessCGMReading) for G6, in contrast
# to the binary-decoded G6 events above.
# steady, in-range (rate 0), sgv 106
G6_JSON_1 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 256, "sequenceGroup": 0, "sequenceNumber": 1079439, "pumpDateTime": "2023-01-08T09:08:34", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 0, "algorithmState": 6, "rssi": -61, "currentGlucoseDisplayValue": 106, "egvTimeStamp": 474023314, "egvInfoBitmask": [0, 5, 6, 7, 8, 11], "interval": 0, "reservedD15": 1}, "estimatedDateTime": "2023-01-08T09:08:34Z"}
# rising fast (rate 127), sgv 197
G6_JSON_2 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 256, "sequenceGroup": 0, "sequenceNumber": 1083284, "pumpDateTime": "2023-01-09T14:28:40", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 127, "algorithmState": 6, "rssi": -76, "currentGlucoseDisplayValue": 197, "egvTimeStamp": 474128920, "egvInfoBitmask": [0, 5, 6, 7, 8, 11], "interval": 0, "reservedD15": 1}, "estimatedDateTime": "2023-01-09T14:28:40Z"}
# high, sgv 316
G6_JSON_3 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 256, "sequenceGroup": 0, "sequenceNumber": 1108047, "pumpDateTime": "2023-01-18T02:43:48", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": 7, "algorithmState": 6, "rssi": -82, "currentGlucoseDisplayValue": 316, "egvTimeStamp": 474864228, "egvInfoBitmask": [0, 5, 6, 7, 8, 11], "interval": 0, "reservedD15": 1}, "estimatedDateTime": "2023-01-18T02:43:48Z"}
# SpecialLow (glucoseValueStatus 2): raw display 0, reported as the LOW sentinel 39
G6_JSON_4 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 256, "sequenceGroup": 0, "sequenceNumber": 1113165, "pumpDateTime": "2023-01-19T20:30:24", "eventProperties": {"glucoseValueStatus": 2, "cgmDataType": [0], "rate": -11, "algorithmState": 6, "rssi": -79, "currentGlucoseDisplayValue": 0, "egvTimeStamp": 475014624, "egvInfoBitmask": [0, 5, 6, 7, 8, 11], "interval": 0, "reservedD15": 1}, "estimatedDateTime": "2023-01-19T20:30:24Z"}
# falling fast (rate -45), sgv 174
G6_JSON_5 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 256, "sequenceGroup": 0, "sequenceNumber": 1125216, "pumpDateTime": "2023-01-23T16:41:42", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": -45, "algorithmState": 6, "rssi": -56, "currentGlucoseDisplayValue": 174, "egvTimeStamp": 475346502, "egvInfoBitmask": [0, 5, 6, 7, 8, 11], "interval": 0, "reservedD15": 1}, "estimatedDateTime": "2023-01-23T16:41:42Z"}


class TestProcessCGMReadingG6Json(unittest.TestCase):
    """G6 processor exercised via real pump-logs JSON (production path)."""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: None
        self.process = ProcessCGMReading(self.tconnect, self.nightscout, 'abcdef', pretend=False, timezone='America/New_York')

    def test_single_g6_json_reading(self):
        events = list(Events([dict(G6_JSON_1)]))
        self.assertEqual(type(events[0]), eventtypes.LidCgmDataGxb)
        self.assertEqual(events[0].egvTimeStamp, 474023314)

        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['sgv'], 106)
        self.assertEqual(p[0]['dateString'], '2023-01-08T09:08:34-0500')
        self.assertEqual(p[0]['pump_event_id'], '1079439')

    def test_diverse_glucose_range(self):
        events = list(Events([
            dict(G6_JSON_1), dict(G6_JSON_2), dict(G6_JSON_3),
            dict(G6_JSON_4), dict(G6_JSON_5)
        ]))
        p = self.process.process(events, time_start=None, time_end=None)
        # Sorted chronologically; the SpecialLow reading (raw display 0) is
        # reported as the LOW sentinel 39.
        self.assertEqual([e['sgv'] for e in p], [106, 197, 316, 39, 174])
        self.assertEqual([e['dateString'] for e in p], [
            '2023-01-08T09:08:34-0500',
            '2023-01-09T14:28:40-0500',
            '2023-01-18T02:43:48-0500',
            '2023-01-19T20:30:24-0500',
            '2023-01-23T16:41:42-0500',
        ])
        self.assertEqual([e['pump_event_id'] for e in p], [
            '1079439', '1083284', '1108047', '1113165', '1125216'
        ])

    def test_special_low_reading(self):
        # glucoseValueStatus SpecialLow reports the LOW sentinel (39), not the
        # raw below-range display value (0).
        events = list(Events([dict(G6_JSON_4)]))
        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['sgv'], 39)

    def test_skips_readings_at_or_before_last_upload(self):
        # Only readings strictly after the last Nightscout upload are returned.
        self.nightscout.last_uploaded_bg_entry = lambda *args, **kwargs: {'dateString': '2023-01-09T14:28:40-0500'}
        events = list(Events([dict(G6_JSON_1), dict(G6_JSON_2), dict(G6_JSON_3)]))
        p = self.process.process(events, time_start=None, time_end=None)
        self.assertEqual([e['sgv'] for e in p], [316])


if __name__ == '__main__':
    unittest.main()
