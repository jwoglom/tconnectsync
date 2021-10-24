#!/usr/bin/env python3

import unittest
import random


from tconnectsync.sync.bolus import process_bolus_events
from tconnectsync.parser.tconnect import TConnectEntry
from tconnectsync.parser.nightscout import NightscoutEntry

from ..parser.test_tconnect import TestTConnectEntryBolus, TestTConnectEntryCGM, TestTConnectEntryReading

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

    def test_process_bolus_events_cgmevents_not_matching(self):
        bolusData = [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]

        cgmEvents = [
            TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry1),
            TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry2),
            TConnectEntry.parse_reading_entry(TestTConnectEntryReading.entry3)
        ]

        bolusEvents = process_bolus_events(bolusData, cgmEvents=cgmEvents)
        self.assertEqual(len(bolusEvents), len(bolusData))

        def set_bg_type(entry, type):
            entry["bg_type"] = type
            return entry

        # Expect FINGER for bolus entries with a BG because there's no matching event with the same BG
        expected = [
            set_bg_type(TConnectEntry.parse_bolus_entry(bolusData[0]), NightscoutEntry.FINGER),
            set_bg_type(TConnectEntry.parse_bolus_entry(bolusData[1]), NightscoutEntry.FINGER),
            # No BG specified for the automatic bolus
            TConnectEntry.parse_bolus_entry(bolusData[2])
        ]

        self.assertListEqual(bolusEvents, expected)

    def test_process_bolus_events_cgmevents_matches(self):
        bolusData = [
            TestTConnectEntryBolus.entryStdCorrection,
            TestTConnectEntryBolus.entryStd,
            TestTConnectEntryBolus.entryStdAutomatic
        ]

        cgmEvents = [
            {
                "time": "2021-04-01 12:45:30-04:00",
                "bg": "100",
                "type": "EGV"
            },
            # Matches entryStdCorrection time but with wrong BG
            {
                "time": "2021-04-01 12:50:30-04:00",
                "bg": "105",
                "type": "EGV"
            },
            {
                "time": "2021-04-01 13:00:30-04:00",
                "bg": "110",
                "type": "EGV"
            },
            {
                "time": "2021-04-01 23:15:30-04:00",
                "bg": "150",
                "type": "EGV"
            },
            # Matches entryStd time with correct BG
            {
                "time": "2021-04-01 23:20:30-04:00",
                "bg": "159",
                "type": "EGV"
            },
            {
                "time": "2021-04-01 23:25:30-04:00",
                "bg": "160",
                "type": "EGV"
            },
        ]

        bolusEvents = process_bolus_events(bolusData, cgmEvents=cgmEvents)
        self.assertEqual(len(bolusEvents), len(bolusData))

        def set_bg_type(entry, type):
            entry["bg_type"] = type
            return entry

        expected = [
            # Time found but BG doesn't match
            set_bg_type(TConnectEntry.parse_bolus_entry(bolusData[0]), NightscoutEntry.FINGER),
            # Time found and BG matches
            set_bg_type(TConnectEntry.parse_bolus_entry(bolusData[1]), NightscoutEntry.SENSOR),
            # No BG specified for the automatic bolus
            TConnectEntry.parse_bolus_entry(bolusData[2])
        ]

        self.assertListEqual(bolusEvents, expected)

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