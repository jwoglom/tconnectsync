#!/usr/bin/env python3

import unittest

from tconnectsync.sync.bolus import process_bolus_events
from tconnectsync.parser.tconnect import TConnectEntry

from ..parser.test_tconnect import TestTConnectEntryBolus

class TestBolusSync(unittest.TestCase):

    @staticmethod
    def get_example_csv_bolus_events():
        return [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]

    def test_process_bolus_events(self):
        bolusData = TestBolusSync.get_example_csv_bolus_events()

        bolusEvents = process_bolus_events(bolusData)
        self.assertEqual(len(bolusEvents), 3)

        self.assertListEqual(bolusEvents, [
            TConnectEntry.parse_bolus_entry(bolusData[0]),
            TConnectEntry.parse_bolus_entry(bolusData[1]),
            TConnectEntry.parse_bolus_entry(bolusData[2])
        ])


if __name__ == '__main__':
    unittest.main()