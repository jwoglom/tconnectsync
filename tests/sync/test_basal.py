#!/usr/bin/env python3

import unittest
from tconnectsync.sync.basal import process_ciq_basal_events
from tconnectsync.parser.tconnect import TConnectEntry

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
        data = self.base.copy()
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
            },
            {
                "y": 0,
                "duration": 2693,
                "x": 1615879821
            },
        ]
        data["basal"]["profileDeliveryEvents"] = [
            {
                "y": 0.799,
                "duration": 300,
                "x": 1615879221
            }
        ]

        data["suspensionDeliveryEvents"] = [
            {
                "suspendReason": "control-iq",
                "continuation": None,
                "x": 1615879821
            },
        ]

        basalEvents = process_ciq_basal_events(data)
        self.assertEqual(len(basalEvents), 4)

        self.assertEqual(basalEvents[0], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["tempDeliveryEvents"][0], delivery_type="tempDelivery"))

        self.assertEqual(basalEvents[1], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["profileDeliveryEvents"][0], delivery_type="profileDelivery"))

        self.assertEqual(basalEvents[2], TConnectEntry.parse_ciq_basal_entry(
            data["basal"]["algorithmDeliveryEvents"][0], delivery_type="algorithmDelivery"))

        self.assertEqual(basalEvents[3], {
            "suspendReason": "control-iq",
            **TConnectEntry.parse_ciq_basal_entry(
                data["basal"]["algorithmDeliveryEvents"][1],
                delivery_type="algorithmDelivery")
        })


if __name__ == '__main__':
    unittest.main()