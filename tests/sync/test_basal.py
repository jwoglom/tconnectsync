#!/usr/bin/env python3

import unittest
from tconnectsync.sync.basal import process_ciq_basal_events
from tconnectsync.parser import TConnectEntry

class TestBasalSync(unittest.TestCase):
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

    def test_process_ciq_basal_events(self):
        data = {**self.base}
        data["basal"]["tempDeliveryEvents"] = [
            {
                "y": 0.8,
                "duration": 1221,
                "x": 1615878000
            }
        ]
        data["basal"]["algorithmDeliveryEvents"] = [
            {
                "y": 0.797,
                "duration": 300,
                "x": 1615879521
            }
        ]
        data["basal"]["profileDeliveryEvents"] = [
            {
                "y": 0.799,
                "duration": 300,
                "x": 1615879221
            }
        ]

        basalEvents = process_ciq_basal_events(self.base)
        self.assertEqual(len(basalEvents), 3)

        self.assertEqual(basalEvents[0], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["tempDeliveryEvents"][0], delivery_type="tempDelivery"))

        self.assertEqual(basalEvents[1], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["profileDeliveryEvents"][0], delivery_type="profileDelivery"))
        
        self.assertEqual(basalEvents[2], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][0], delivery_type="algorithmDelivery"))


if __name__ == '__main__':
    unittest.main()