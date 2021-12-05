#!/usr/bin/env python3

import unittest
from copy import deepcopy

from tconnectsync.sync.basal import process_ciq_basal_events
from tconnectsync.parser.tconnect import TConnectEntry

class TestBasalSync(unittest.TestCase):
    maxDiff = None

    base = {
        "basal": {
            "profileRates": [],
            "tempDeliveryEvents": [],
            "algorithmDeliveryEvents": [],
            "profileDeliveryEvents": []
        },
        "events": [],
        "suspensionDeliveryEvents": [],
        "softwareUpdates": [],
        "pumpFeatures": []
    }

    @staticmethod
    def get_example_ciq_basal_events():
        data = deepcopy(TestBasalSync.base)
        data["basal"]["tempDeliveryEvents"] = [
            {
                "y": 0.8,
                "duration": 1221,
                "x": 1615878000 # 12:00:00
            }
        ]
        data["basal"]["algorithmDeliveryEvents"] = [
            {
                "y": 0.797,
                "duration": 300,
                "x": 1615879521 # 12:25:21
            },
            {
                "y": 0,
                "duration": 2693,
                "x": 1615879821 # 12:30:21
            },
        ]
        data["basal"]["profileDeliveryEvents"] = [
            {
                "y": 0.799,
                "duration": 300,
                "x": 1615879221 # 12:20:21
            }
        ]

        data["suspensionDeliveryEvents"] = [
            {
                "suspendReason": "control-iq",
                "continuation": None,
                "x": 1615879821 # 12:30:21
            },
        ]

        return data

    def test_process_ciq_basal_events(self):
        data = TestBasalSync.get_example_ciq_basal_events()

        basalEvents = process_ciq_basal_events(data)
        self.assertEqual(len(basalEvents), 4)

        self.assertEqual(basalEvents[0], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["tempDeliveryEvents"][0], delivery_type="tempDelivery"))

        self.assertEqual(basalEvents[1], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["profileDeliveryEvents"][0], delivery_type="profileDelivery"))

        self.assertEqual(basalEvents[2], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][0], delivery_type="algorithmDelivery"))

        self.assertEqual(basalEvents[3], TConnectEntry.parse_ciq_basal_entry(
                data["basal"]["algorithmDeliveryEvents"][1],
                delivery_type="algorithmDelivery (control-iq suspension)")
        )
    

    @staticmethod
    def get_example_ciq_basal_events_with_manual_suspension():
        data = deepcopy(TestBasalSync.base)
        data["basal"]["tempDeliveryEvents"] = []
        data["basal"]["algorithmDeliveryEvents"] = [
            {
                "y": 1.14,
                "duration": 300,
                "x": 1635187357 # 11:42:37
            },
            {
                "y": 0.8,
                "duration": 1198,
                "x": 1635187657 # 11:47:37
            },
            {
                "y": 0.8,
                "duration": 599,
                "x": 1635190967 # 12:42:47
            }
        ]
        data["basal"]["profileDeliveryEvents"] = []
        data["suspensionDeliveryEvents"] = [
            {
                "suspendReason": "manual",
                "continuation": None,
                "x": 1635188855 # 12:07:35
            },
            {
                "suspendReason": "manual",
                "continuation": None,
                "x": 1635191566 # 12:52:46
            },
        ]

        return data

    def test_process_ciq_basal_events_with_manual_suspension(self):
        data = TestBasalSync.get_example_ciq_basal_events_with_manual_suspension()
        
        basalEvents = process_ciq_basal_events(data)
        self.assertEqual(len(basalEvents), 4)

        self.assertEqual(basalEvents[0], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][0], delivery_type="algorithmDelivery"))

        self.assertEqual(basalEvents[1], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][1], delivery_type="algorithmDelivery"))

        self.assertEqual(basalEvents[2], TConnectEntry.manual_suspension_to_basal_entry(
            TConnectEntry.parse_suspension_entry(data["suspensionDeliveryEvents"][0]),
            seconds=2112, # 2112 seconds between 12:07:35 and 12:42:47
        ))

        self.assertEqual(basalEvents[3], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][2], delivery_type="algorithmDelivery"))


if __name__ == '__main__':
    unittest.main()