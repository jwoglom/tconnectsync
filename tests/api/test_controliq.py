#!/usr/bin/env python3

import unittest
import itertools
import datetime

from .fake import ControlIQApi

from tconnectsync.api.common import ApiException

class TestControlIQApi(unittest.TestCase):
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

    def test_therapy_timeline_works_after_single_http_500(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        ciq._get = self.fake_get_with_http_code(500, "therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", 1)

        self.assertEqual(
            ciq.therapy_timeline('2021-04-01', '2021-04-02'),
            {
                "faked_json": True
            })

    def test_therapy_timeline_fails_after_two_http_500s(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        ciq._get = self.fake_get_with_http_code(500, "therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", 2)

        ex = self.assertRaises(ApiException, ciq.therapy_timeline, '2021-04-01', '2021-04-02')

    def test_therapy_timeline_triggers_relogin_after_single_http_401(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        ciq._email = 'email'
        ciq._password = 'password'

        hit_login = []
        def stub_login(email, password):
            nonlocal hit_login
            hit_login.append((email, password))

        ciq.login = stub_login

        ciq._get = self.fake_get_with_http_code(401, "therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", 1)

        self.assertEqual(
            ciq.therapy_timeline('2021-04-01', '2021-04-02'),
            {
                "faked_json": True
            })

        self.assertListEqual(hit_login, [
            ('email', 'password')
        ])

    def test_therapy_timeline_fails_after_two_http_401s(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        ciq._email = 'email'
        ciq._password = 'password'

        hit_login = []
        def stub_login(email, password):
            nonlocal hit_login
            hit_login.append((email, password))

        ciq.login = stub_login

        ciq._get = self.fake_get_with_http_code(401, "therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", 2)

        ex = self.assertRaises(ApiException, ciq.therapy_timeline, '2021-04-01', '2021-04-02')

        self.assertListEqual(hit_login, [
            ('email', 'password')
        ])

    def test_therapy_timeline_parses_date(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        def fake_get(endpoint, query):
            self.assertTrue(endpoint.endswith("therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            self.assertEqual(query, {
                "startDate": "04-01-2021",
                "endDate": "04-02-2021"
            })

            return {"faked_json": True}

        ciq._get = fake_get

        self.assertEqual(
            ciq.therapy_timeline(datetime.date(2021, 4, 1), datetime.date(2021, 4, 2)),
            {
                "faked_json": True
            })

    def test_dashboard_summary_parses_date(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        def fake_get(endpoint, query):
            self.assertTrue(endpoint.endswith("summary/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            self.assertEqual(query, {
                "startDate": "04-01-2021",
                "endDate": "04-02-2021"
            })

            return {"faked_json": True}

        ciq._get = fake_get

        self.assertEqual(
            ciq.dashboard_summary(datetime.date(2021, 4, 1), datetime.date(2021, 4, 2)),
            {
                "faked_json": True
            })

if __name__ == '__main__':
    unittest.main()