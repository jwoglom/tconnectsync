#!/usr/bin/env python3

import unittest
import random

from tconnectsync.sync.bolus import process_bolus_events
from tconnectsync.parser.tconnect import TConnectEntry

from ..parser.test_tconnect import TestTConnectEntryBolus

class TestBolusSync(unittest.TestCase):

    @staticmethod
    def get_example_csv_bolus_events():
        return [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic,
            TestTConnectEntryBolus.entryStdIncompletePartial
        ]

    def test_process_bolus_events_standard(self):
        bolusData = [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]

        bolusEvents = process_bolus_events(bolusData)
        self.assertEqual(len(bolusEvents), len(bolusData))

        self.assertListEqual(bolusEvents, [
            TConnectEntry.parse_bolus_entry(d) for d in bolusData
        ])

    def test_process_bolus_events_update_partial_description(self):
        stdData = [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]
        partialData = [
            TestTConnectEntryBolus.entryStdIncompletePartial
        ]

        bolusData = stdData + partialData

        bolusEvents = process_bolus_events(bolusData)
        self.assertEqual(len(bolusEvents), len(bolusData))

        partialEntries = [
            TConnectEntry.parse_bolus_entry(e) for e in partialData
        ]

        for e in partialEntries:
            e["description"] += " (%s: requested %s units)" % (e["completion"], e["requested_insulin"])

        self.assertListEqual(bolusEvents, [
            TConnectEntry.parse_bolus_entry(d) for d in stdData
        ] + partialEntries)

    def test_process_bolus_events_skip_zero(self):
        stdData = [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]
        zeroData = [
            TestTConnectEntryBolus.entryStdIncompleteZero
        ]
        bolusData = stdData + zeroData

        bolusEvents = process_bolus_events(bolusData)
        self.assertEqual(len(bolusEvents), len(stdData))

        self.assertListEqual(bolusEvents, [
            TConnectEntry.parse_bolus_entry(d) for d in stdData
        ])

        for d in zeroData:
            self.assertNotIn(TConnectEntry.parse_bolus_entry(d), bolusEvents)

if __name__ == '__main__':
    unittest.main()