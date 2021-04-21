#!/usr/bin/env python3

import unittest
from tconnectsync.parser.nightscout import NightscoutEntry

class TestNightscoutEntry(unittest.TestCase):
    def test_basal(self):
        self.assertEqual(
            NightscoutEntry.basal(
                value=1.05,
                duration_mins=30,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "eventType": "Temp Basal",
                "reason": "",
                "duration": 30,
                "absolute": 1.05,
                "created_at": "2021-03-16 00:25:21-04:00",
                "carbs": None,
                "insulin": None,
                "enteredBy": "Pump (tconnectsync)"
            }
        )

        self.assertEqual(
            NightscoutEntry.basal(
                value=0.95,
                duration_mins=5,
                created_at="2021-03-16 12:25:21-04:00",
                reason="Correction"),
            {
                "eventType": "Temp Basal",
                "reason": "Correction",
                "duration": 5,
                "absolute": 0.95,
                "created_at": "2021-03-16 12:25:21-04:00",
                "carbs": None,
                "insulin": None,
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    def test_bolus(self):
        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=7.5,
                carbs=45,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 00:25:21-04:00",
                "carbs": 45,
                "insulin": 7.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=0.5,
                carbs=5,
                created_at="2021-03-16 12:25:21-04:00"),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 12:25:21-04:00",
                "carbs": 5,
                "insulin": 0.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    def test_iob(self):
        self.assertEqual(
            NightscoutEntry.iob(
                iob=2.05,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "activityType": "tconnect_iob",
                "iob": 2.05,
                "created_at": "2021-03-16 00:25:21-04:00",
                "enteredBy": "Pump (tconnectsync)"
            }
        )


if __name__ == '__main__':
    unittest.main()