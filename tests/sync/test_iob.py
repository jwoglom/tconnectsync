#!/usr/bin/env python3

import unittest

from tconnectsync.sync.iob import process_iob_events
from tconnectsync.parser.tconnect import TConnectEntry

from ..parser.test_tconnect import TestTConnectEntryIOB

class TestIOBSync(unittest.TestCase):

    @staticmethod
    def get_example_csv_iob_events():
        return [
            TestTConnectEntryIOB.entry1,
            TestTConnectEntryIOB.entry2,
        ]

    def test_process_iob_events(self):
        iobData = TestIOBSync.get_example_csv_iob_events()

        iobEvents = process_iob_events(iobData)
        self.assertEqual(len(iobEvents), len(iobData))

        self.assertListEqual(iobEvents, [
            TConnectEntry.parse_iob_entry(d) for d in iobData
        ])

if __name__ == '__main__':
    unittest.main()