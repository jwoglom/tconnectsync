#!/usr/bin/env python3

import unittest

from .fake import WS2Api

from tconnectsync.api.common import ApiException

class TestWS2Api(unittest.TestCase):
    def fake_get_with_http_500(self, num_times):
        tries = 0
        def fake_get(endpoint, query):
            nonlocal tries, num_times
            if "therapytimeline2csv" in endpoint:
                if tries < num_times:
                    tries += 1
                    raise ApiException(500, "fake HTTP 500")

                return ""
            raise NotImplementedError

        return fake_get

    def test_therapy_timeline_csv_works_after_two_retries(self):
        ws2 = WS2Api()

        ws2.get = self.fake_get_with_http_500(2)

        self.assertEqual(
            ws2.therapy_timeline_csv('2021-04-01', '2021-04-02'),
            {
                "readingData": [],
                "iobData": [],
                "basalData": [],
                "bolusData": []
            })

    def test_therapy_timeline_csv_fails_after_three_retries(self):
        ws2 = WS2Api()

        ws2.get = self.fake_get_with_http_500(3)

        self.assertRaises(ApiException, ws2.therapy_timeline_csv, '2021-04-01', '2021-04-02')

if __name__ == '__main__':
    unittest.main()