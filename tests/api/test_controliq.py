#!/usr/bin/env python3

import unittest
import itertools
import datetime
import json
import requests_mock

from bs4 import BeautifulSoup

from .fake import ControlIQApi

from tconnectsync.api.controliq import ControlIQApi as RealControlIQApi
from tconnectsync.api.common import ApiException, ApiLoginException, base_headers

class TestControlIQApi(unittest.TestCase):
    LOGIN_HTML = """
<html>
<body>
    <form method="post" action="./login.aspx?ReturnUrl=%2f" onsubmit="javascript:return WebForm_OnSubmit();" id="form1">
        <div class="aspNetHidden">
            <input type="hidden" name="__LASTFOCUS" id="__LASTFOCUS" value="" />
            <input type="hidden" name="__EVENTTARGET" id="__EVENTTARGET" value="" />
            <input type="hidden" name="__EVENTARGUMENT" id="__EVENTARGUMENT" value="" />
            <input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="AAAAA" />
        </div>
        <div class="aspNetHidden">
            <input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="BBBBB" />
            <input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="CCCCC" />
        </div>
    </form>
</body>
</html>
    """

    LOGIN_POST_DATA = {
        "__LASTFOCUS": "",
        "__EVENTTARGET": "ctl00$ContentBody$LoginControl$linkLogin",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": "AAAAA",
        "__VIEWSTATEGENERATOR": "BBBBB",
        "__EVENTVALIDATION": "CCCCC",
        "ctl00$ContentBody$LoginControl$txtLoginEmailAddress": "email@email.com",
        "txtLoginEmailAddress_ClientState": '{"enabled":true,"emptyMessage":"","validationText":"%s","valueAsString":"%s","lastSetTextBoxValue":"%s"}' % ("email@email.com", "email@email.com", "email@email.com"),
        "ctl00$ContentBody$LoginControl$txtLoginPassword": "password",
        "txtLoginPassword_ClientState": '{"enabled":true,"emptyMessage":"","validationText":"%s","valueAsString":"%s","lastSetTextBoxValue":"%s"}' % ("password", "password", "password")
    }

    def test_build_login_data(self):
        ciq = ControlIQApi()
        soup = BeautifulSoup(self.LOGIN_HTML, features='lxml')

        self.assertDictEqual(
            ciq._build_login_data('email@email.com', 'password', soup),
            self.LOGIN_POST_DATA)

    def test_login_successful(self):
        ciq = ControlIQApi()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: RealControlIQApi.login(ciq, email, password)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers=base_headers(),

                text=self.LOGIN_HTML)

            def post_callback(request, context):
                context.status_code = 302
                context.headers['Location'] = '/newlocation'
                context.cookies['UserGUID'] = 'user_guid'
                context.cookies['accessToken'] = 'access_tok'
                context.cookies['accessTokenExpiresAt'] = '2021-05-04T11:18:08.381Z'
                return ''

            m.post('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers={'Referer': ciq.LOGIN_URL, **base_headers()},

                text=post_callback)

            m.post('https://tconnect.tandemdiabetes.com/newlocation',
                cookies={'cookie': 'value'},
                headers=base_headers(),

                status_code=200)

            self.assertTrue(ciq.login('email@email.com', 'password'))

            self.assertEqual(ciq.userGuid, 'user_guid')
            self.assertEqual(ciq.accessToken, 'access_tok')
            self.assertEqual(ciq.accessTokenExpiresAt, '2021-05-04T11:18:08.381Z')


    def test_login_invalid_credentials(self):
        ciq = ControlIQApi()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: RealControlIQApi.login(ciq, email, password)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers=base_headers(),

                text=self.LOGIN_HTML)

            def post_callback(request, context):
                context.status_code = 200
                return '<html><body>...</body></html>'

            m.post('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers={'Referer': ciq.LOGIN_URL, **base_headers()},

                text=post_callback)

            self.assertRaisesRegex(ApiLoginException, 'Error logging in to t:connect: Check your login credentials.', ciq.login, 'email@email.com', 'password')

            self.assertIsNone(ciq.userGuid)
            self.assertIsNone(ciq.accessToken)
            self.assertIsNone(ciq.accessTokenExpiresAt)

    def test_login_invalid_credentials_parsed_message(self):
        ciq = ControlIQApi()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: RealControlIQApi.login(ciq, email, password)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers=base_headers(),

                text=self.LOGIN_HTML)

            def post_callback(request, context):
                context.status_code = 200
                return '<html><body><div class="notice_error" id="literalMessage" style="">The email address or password you entered is invalid. Please re-enter and try again.</div></body></html>'

            m.post('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers={'Referer': ciq.LOGIN_URL, **base_headers()},

                text=post_callback)

            self.assertRaisesRegex(ApiLoginException, 'Error logging in to t:connect: The email address or password you entered is invalid. Please re-enter and try again.', ciq.login, 'email@email.com', 'password')

            self.assertIsNone(ciq.userGuid)
            self.assertIsNone(ciq.accessToken)
            self.assertIsNone(ciq.accessTokenExpiresAt)

    def test_login_unexpected_http_code(self):
        ciq = ControlIQApi()
        ciq.LOGIN_URL = RealControlIQApi.LOGIN_URL
        ciq.login = lambda email, password: RealControlIQApi.login(ciq, email, password)

        with requests_mock.Mocker() as m:
            m.get('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers=base_headers(),

                text=self.LOGIN_HTML)

            def post_callback(request, context):
                context.status_code = 500
                return '<html><body>...</body></html>'

            m.post('https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f',
                request_headers={'Referer': ciq.LOGIN_URL, **base_headers()},

                text=post_callback)

            self.assertRaisesRegex(ApiLoginException, 'Error logging in to t:connect \(HTTP 500\)', ciq.login, 'email@email.com', 'password')

            self.assertIsNone(ciq.userGuid)
            self.assertIsNone(ciq.accessToken)
            self.assertIsNone(ciq.accessTokenExpiresAt)


    def fake_get_with_http_code(self, http_code, expected_endpoint, num_times):
        tries = 0
        def fake_get(endpoint, query):
            nonlocal http_code, expected_endpoint, num_times, tries
            if endpoint.split("?")[0].endswith(expected_endpoint):
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

        self.assertRaises(ApiException, ciq.therapy_timeline, '2021-04-01', '2021-04-02')

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

        self.assertRaises(ApiException, ciq.therapy_timeline, '2021-04-01', '2021-04-02')

        self.assertListEqual(hit_login, [
            ('email', 'password')
        ])

    def test_therapy_timeline_parses_date(self):
        ciq = ControlIQApi()
        ciq.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        def fake_get(raw_endpoint, ignored_query):
            endpoint, query = raw_endpoint.split("?")
            self.assertTrue(endpoint.endswith("therapytimeline/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            self.assertEqual(query, "startDate=04-01-2021&endDate=04-02-2021")

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

        def fake_get(raw_endpoint, ignored_query):
            endpoint, query = raw_endpoint.split("?")
            self.assertTrue(endpoint.endswith("summary/users/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            self.assertEqual(query, "startDate=04-01-2021&endDate=04-02-2021")

            return {"faked_json": True}

        ciq._get = fake_get

        self.assertEqual(
            ciq.dashboard_summary(datetime.date(2021, 4, 1), datetime.date(2021, 4, 2)),
            {
                "faked_json": True
            })

if __name__ == '__main__':
    unittest.main()