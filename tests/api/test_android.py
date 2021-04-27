#!/usr/bin/env python3

import unittest
import itertools
import datetime

from .fake import AndroidApi

from tconnectsync.api.common import ApiException

class TestAndroidApi(unittest.TestCase):
    def fake_get_with_http_code(self, http_code, expected_endpoint, num_times):
        tries = 0
        def fake_get(endpoint, query):
            nonlocal http_code, expected_endpoint, num_times, tries
            if endpoint.endswith(expected_endpoint):
                if tries < num_times:
                    tries += 1
                    raise ApiException(http_code, "fake HTTP %d" % http_code)

                return {"faked_json": True}

            raise NotImplementedError

        return fake_get

    def test_last_event_uploaded_works_after_single_http_500(self):
        android = AndroidApi()

        android._get = self.fake_get_with_http_code(500, "cloud/upload/getlasteventuploaded?sn=1111111", 1)

        self.assertEqual(
            android.last_event_uploaded(1111111),
            {
                "faked_json": True
            })

    def test_last_event_uploaded_fails_after_two_http_500s(self):
        android = AndroidApi()

        android._get = self.fake_get_with_http_code(500, "cloud/upload/getlasteventuploaded?sn=1111111", 2)

        self.assertRaises(ApiException, android.last_event_uploaded, 1111111)

    def test_last_event_uploaded_triggers_relogin_after_single_http_401(self):
        android = AndroidApi()
        android._email = 'email'
        android._password = 'password'

        hit_login = []
        def stub_login(email, password):
            nonlocal hit_login
            hit_login.append((email, password))

        android.login = stub_login

        android._get = self.fake_get_with_http_code(401, "cloud/upload/getlasteventuploaded?sn=1111111", 1)

        self.assertEqual(
            android.last_event_uploaded(1111111),
            {
                "faked_json": True
            })

        self.assertListEqual(hit_login, [
            ('email', 'password')
        ])

    def test_last_event_uploaded_fails_after_two_http_401s(self):
        android = AndroidApi()
        android._email = 'email'
        android._password = 'password'

        hit_login = []
        def stub_login(email, password):
            nonlocal hit_login
            hit_login.append((email, password))

        android.login = stub_login

        android._get = self.fake_get_with_http_code(401, "cloud/upload/getlasteventuploaded?sn=1111111", 2)

        self.assertRaises(ApiException, android.last_event_uploaded, 1111111)

        self.assertListEqual(hit_login, [
            ('email', 'password')
        ])

if __name__ == '__main__':
    unittest.main()