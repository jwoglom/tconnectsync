#!/usr/bin/env python3

import unittest

from tconnectsync.sync.cgm import find_event_at, process_cgm_events
from tconnectsync.parser.tconnect import TConnectEntry

from ..parser.test_tconnect import TestTConnectEntryReading

class TestProcessCGMEvents(unittest.TestCase):
    def test_process_cgm_events(self):
        rawReadings = [
            TestTConnectEntryReading.entry1,
            TestTConnectEntryReading.entry2,
            TestTConnectEntryReading.entry3,
            TestTConnectEntryReading.entry4
        ]
        self.assertListEqual(
            process_cgm_events(rawReadings),
            [TConnectEntry.parse_reading_entry(r) for r in rawReadings]
        )

class TestFindEventAt(unittest.TestCase):
    readingData = [
        TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry1),
        TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry2),
        TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry3),
        TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry4)
    ]

    def test_find_event_at_exact(self):
        for r in self.readingData:
            self.assertEqual(find_event_at(self.readingData, r["time"]), r)

    def test_find_event_at_before_not_found(self):
        self.assertEqual(find_event_at(self.readingData, "2021-10-22 10:30:00-04:00"), None)

    def test_find_event_at_large_gap(self):
        self.assertEqual(find_event_at(self.readingData, "2021-10-23 13:30:00-04:00"), self.readingData[0])

    def test_find_event_at_between_close(self):
        self.assertEqual(find_event_at(self.readingData, "2021-10-23 16:17:52-04:00"), self.readingData[1])
        self.assertEqual(find_event_at(self.readingData, "2021-10-23 16:21:52-04:00"), self.readingData[2])
        self.assertEqual(find_event_at(self.readingData, "2021-10-23 16:25:59-04:00"), self.readingData[3])

    def test_find_event_at_most_recent(self):
        self.assertEqual(find_event_at(self.readingData, "2021-10-23 18:00:00-04:00"), self.readingData[3])
        

if __name__ == '__main__':
    unittest.main()