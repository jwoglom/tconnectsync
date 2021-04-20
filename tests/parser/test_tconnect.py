#!/usr/bin/env python3

import unittest
from tconnectsync.parser.tconnect import TConnectEntry

class TestTConnectEntry(unittest.TestCase):
    def test_parse_ciq_basal_entry(self):
        self.assertEqual(
            TConnectEntry.parse_ciq_basal_entry({
                "y": 0.8,
                "duration": 1221,
                "x": 1615878000
            }),
            {
                "time": "2021-03-16 00:00:00-04:00",
                "delivery_type": "",
                "duration_mins": 1221/60,
                "basal_rate": 0.8,
            }
        )

        self.assertEqual(
            TConnectEntry.parse_ciq_basal_entry({
                "y": 0.797,
                "duration": 300,
                "x": 1615879521
            }, delivery_type="algorithmDelivery"),
            {
                "time": "2021-03-16 00:25:21-04:00",
                "delivery_type": "algorithmDelivery",
                "duration_mins": 5,
                "basal_rate": 0.797,
            }
        )



if __name__ == '__main__':
    unittest.main()