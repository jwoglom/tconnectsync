#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process_cgm_reading import ProcessCGMReading
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event

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


class TestProcessCGMReadingG7_USEastern(unittest.TestCase):
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
        self.assertEqual(events[0].egvTimestamp, 566504204)
        self.assertEqual(events[0].seqNum, 505869)
        self.assertEqual(events[0].currentglucosedisplayvalue, 80)
        self.assertEqual(events[0].rateRaw, -9)

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

        self.assertEqual(events[0].currentglucosedisplayvalue, 80)
        self.assertEqual(events[1].currentglucosedisplayvalue, 71)
        self.assertEqual(events[2].currentglucosedisplayvalue, 119)

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
        self.assertEqual(events[0].egvTimestamp, 444182469)
        self.assertEqual(events[0].currentglucosedisplayvalue, 75)
        self.assertEqual(events[0].rateRaw, -4)

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

        self.assertEqual(events[0].currentglucosedisplayvalue, 75)
        self.assertEqual(events[1].currentglucosedisplayvalue, 77)
        self.assertEqual(events[2].currentglucosedisplayvalue, 76)

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

        self.assertEqual(events[0].currentglucosedisplayvalue, 75)
        self.assertEqual(events[1].currentglucosedisplayvalue, 77)
        self.assertEqual(events[2].currentglucosedisplayvalue, 76) # backfill
        self.assertEqual(events[3].currentglucosedisplayvalue, 75)
        self.assertEqual(events[4].currentglucosedisplayvalue, 74)

        self.assertEqual(events[0].raw.timestampRaw, 444182469)
        self.assertEqual(events[1].raw.timestampRaw, 444182768)
        self.assertEqual(events[2].raw.timestampRaw, 444189367)
        self.assertEqual(events[3].raw.timestampRaw, 444189367)
        self.assertEqual(events[4].raw.timestampRaw, 444189666)

        self.assertEqual(events[0].egvTimestamp, 444182469)
        self.assertEqual(events[1].egvTimestamp, 444182768)
        self.assertEqual(events[2].egvTimestamp, 444189067)
        self.assertEqual(events[3].egvTimestamp, 444189367)
        self.assertEqual(events[4].egvTimestamp, 444189666)


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


if __name__ == '__main__':
    unittest.main()
