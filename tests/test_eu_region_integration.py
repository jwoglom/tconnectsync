#!/usr/bin/env python3
"""EU region integration tests (issue #152).

Configures the EU region via each supported mechanism (TCONNECT_REGION
environment variable, .env file, --region CLI flag) and runs the real
downstream code against a mocked HTTP layer on which only the EU
endpoints are registered, so any request to a US endpoint fails.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import urllib.parse

import jwt
import requests_mock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

TEST_KID = 'eu-integration-test-key'
PUMPER_ID = 'aaaaaaaa-1111-2222-3333-444444444444'
ACCOUNT_ID = 'bbbbbbbb-5555-6666-7777-888888888888'
DEVICE_ID = '1b493210-9336-4901-a329-a352775738c5'

EU_API = 'https://tdcservices.eu.tandemdiabetes.com/accounts/api'
EU_SOURCE = 'https://source.eu.tandemdiabetes.com/'
EU_CLIENT_ID = '1519e414-eeec-492e-8c5e-97bea4815a10'

EU_LOGIN_URL = EU_API + '/login'
EU_TOKEN_URL = EU_API + '/connect/token'
EU_AUTHORIZE_URL = EU_API + '/connect/authorize'
EU_JWKS_URL = EU_API + '/.well-known/openid-configuration/jwks'
EU_CALLBACK_URL = EU_SOURCE + 'authorize/callback'
EU_PUMPER_URL = EU_SOURCE + 'api/reports/bff/pumper/' + PUMPER_ID
EU_PUMP_LOGS_URL = EU_SOURCE + 'api/reports/bff/pump-logs/' + DEVICE_ID

NS_URL = 'http://nightscout.example.com/'

US_HOSTS = {'tdcservices.tandemdiabetes.com', 'source.tandemdiabetes.com'}

# sso.tandemdiabetes.com hosts the login page for both regions.
ALLOWED_HOSTS = {
    'sso.tandemdiabetes.com',
    'tdcservices.eu.tandemdiabetes.com',
    'source.eu.tandemdiabetes.com',
    'nightscout.example.com',
}

TEST_EMAIL = 'eu-user@example.com'
TEST_PASSWORD = 'eu-password'

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)


def make_id_token():
    """RS256-signed id_token with the EU issuer/audience, so extract_jwt()
    performs full verification against the mocked EU jwks endpoint."""
    now = int(time.time())
    claims = {
        'iss': EU_API,
        'aud': EU_CLIENT_ID,
        'iat': now,
        'nbf': now,
        'exp': now + 3600,
        'sub': 'eu-test-subject',
        'pumperId': PUMPER_ID,
        'accountId': ACCOUNT_ID,
    }
    return jwt.encode(claims, _PRIVATE_PEM, algorithm='RS256', headers={'kid': TEST_KID})


def make_jwks():
    jwk = json.loads(RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key()))
    jwk.update({'kid': TEST_KID, 'use': 'sig', 'alg': 'RS256'})
    return {'keys': [jwk]}


BFF_PUMPER = {
    'firstName': 'Eu',
    'lastName': 'User',
    'name': 'Eu User',
    'country': 'DE',
    'pumps': [
        {
            'algorithm': 'Control-IQ',
            'availableDataRange': {'start': '2026-01-01T00:00:00', 'end': '2026-07-16T10:00:00'},
            'assignmentId': DEVICE_ID,
            'lastUploadDate': '2026-07-16T10:00:00Z',
            'maxDateOfEvents': '2026-07-16T10:00:00',
            'modelNumber': '1000354',
            'modelName': 't:slim X2™ Insulin Pump',
            'partNumber': '1011979',
            'serialNumber': '90556643',
            'softwareVersion': '7.8.0.0',
            'lastUploadClientType': 'mobile_tconnect',
            'settings': None,
        }
    ],
}

PUMP_LOGS = {'events': [], 'clockChanges': []}


def register_eu_endpoints(m):
    """Register only the EU (and region-shared) endpoints; any US request
    raises requests_mock.NoMockAddress."""
    m.get('https://sso.tandemdiabetes.com/', text='')
    m.post(EU_LOGIN_URL, json={'redirectUrl': '/', 'status': 'SUCCESS'})
    m.get(EU_AUTHORIZE_URL, status_code=302,
          headers={'Location': EU_CALLBACK_URL + '?code=eu-test-code'})
    m.get(EU_CALLBACK_URL, text='')
    m.post(EU_TOKEN_URL, json={
        'access_token': 'eu-access-token',
        'id_token': make_id_token(),
        'expires_in': 3600,
    })
    m.get(EU_JWKS_URL, json=make_jwks())
    m.get(EU_PUMPER_URL, json=BFF_PUMPER)
    m.get(EU_PUMP_LOGS_URL, json=PUMP_LOGS)


def register_nightscout_endpoints(m):
    m.get(NS_URL + 'api/v1/status.json', json={'status': 'ok', 'version': '15.0.3'})
    m.get(NS_URL + 'api/v1/treatments', json=[])


class EuRegionTestBase(unittest.TestCase):
    """Runs each test in a scratch cwd with a controlled environment, and
    re-imports tconnectsync so secret.py is loaded from that environment."""
    maxDiff = None

    ENV_KEYS = [
        'TCONNECT_EMAIL', 'TCONNECT_PASSWORD', 'TCONNECT_REGION',
        'CACHE_CREDENTIALS', 'NS_URL', 'NS_SECRET', 'API_SECRET',
        'TIMEZONE_NAME', 'TZ', 'PUMP_SERIAL_NUMBER', 'REQUESTS_PROXY',
    ]

    BASE_ENV = {
        'TCONNECT_EMAIL': TEST_EMAIL,
        'TCONNECT_PASSWORD': TEST_PASSWORD,
        'CACHE_CREDENTIALS': 'false',
        'NS_URL': NS_URL,
        'NS_SECRET': 'ns-secret',
        'TIMEZONE_NAME': 'Europe/Berlin',
    }

    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in self.ENV_KEYS}
        for k in self.ENV_KEYS:
            os.environ.pop(k, None)
        self._old_cwd = os.getcwd()
        self._tmpdir = tempfile.mkdtemp(prefix='tconnectsync-eu-test-')
        os.chdir(self._tmpdir)
        self._purge_modules()

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._purge_modules()

    @staticmethod
    def _purge_modules():
        for name in list(sys.modules):
            if name == 'tconnectsync' or name.startswith('tconnectsync.'):
                del sys.modules[name]

    def import_tconnectsync(self, extra_env=None):
        env = dict(self.BASE_ENV)
        env.update(extra_env or {})
        os.environ.update(env)
        self._purge_modules()
        import tconnectsync
        return tconnectsync

    def called(self, m):
        """(method, url-without-query) pairs for every mocked request."""
        return [(r.method, r.url.split('?')[0]) for r in m.request_history]

    def assert_only_eu_hosts(self, m):
        hosts = {urllib.parse.urlparse(r.url).netloc.lower() for r in m.request_history}
        self.assertTrue(hosts, 'expected at least one HTTP request')
        self.assertFalse(hosts & US_HOSTS,
                         'US endpoints were contacted with EU region configured: %s' % (hosts & US_HOSTS))
        self.assertLessEqual(hosts, ALLOWED_HOSTS,
                             'unexpected hosts contacted: %s' % (hosts - ALLOWED_HOSTS))

    def assert_eu_login_flow(self, m):
        calls = self.called(m)
        self.assertIn(('POST', EU_LOGIN_URL), calls)
        self.assertIn(('GET', EU_AUTHORIZE_URL), calls)
        self.assertIn(('POST', EU_TOKEN_URL), calls)
        self.assertIn(('GET', EU_JWKS_URL), calls)
        self.assert_only_eu_hosts(m)


class TestEuRegionFromEnvironmentVariable(EuRegionTestBase):
    """TCONNECT_REGION=EU set as an environment variable."""

    def test_tconnect_api_without_region_argument_uses_eu(self):
        # The downstream pattern that regressed in #152: TConnectApi built
        # without a region argument.
        self.import_tconnectsync({'TCONNECT_REGION': 'EU'})
        from tconnectsync.api import TConnectApi

        with requests_mock.Mocker() as m:
            register_eu_endpoints(m)

            api = TConnectApi(TEST_EMAIL, TEST_PASSWORD)
            self.assertEqual(api.region, 'EU')

            tandemsource = api.tandemsource
            self.assertEqual(tandemsource.region, 'EU')
            self.assertEqual(tandemsource.LOGIN_API_URL, EU_LOGIN_URL)
            self.assertEqual(tandemsource.SOURCE_URL, EU_SOURCE)
            self.assertEqual(tandemsource.pumperId, PUMPER_ID)
            self.assertEqual(tandemsource.accountId, ACCOUNT_ID)

            pumper = tandemsource.get_pumper()
            self.assertEqual(pumper['pumps'][0]['assignmentId'], DEVICE_ID)

            self.assert_eu_login_flow(m)
            self.assertIn(('GET', EU_PUMPER_URL), self.called(m))

    def test_tandem_source_api_without_region_argument_uses_eu(self):
        self.import_tconnectsync({'TCONNECT_REGION': 'EU'})
        from tconnectsync.api.tandemsource import TandemSourceApi

        with requests_mock.Mocker() as m:
            register_eu_endpoints(m)

            api = TandemSourceApi(TEST_EMAIL, TEST_PASSWORD)
            self.assertEqual(api.region, 'EU')
            self.assertEqual(api.pumperId, PUMPER_ID)
            self.assert_eu_login_flow(m)

    def test_secret_exposes_eu_region(self):
        tconnectsync = self.import_tconnectsync({'TCONNECT_REGION': 'EU'})
        self.assertEqual(tconnectsync.secret.TCONNECT_REGION, 'EU')


class TestEuRegionFromDotEnvFile(EuRegionTestBase):
    """TCONNECT_REGION=EU set through a .env file in the working directory."""

    def test_tconnect_api_without_region_argument_uses_eu(self):
        # secret.py reads $CWD/.env; setUp chdir'd into a scratch directory.
        with open(os.path.join(self._tmpdir, '.env'), 'w') as f:
            for k, v in dict(self.BASE_ENV, TCONNECT_REGION='EU').items():
                f.write('%s=%s\n' % (k, v))

        os.environ.update({'CACHE_CREDENTIALS': 'false'})
        self._purge_modules()
        import tconnectsync  # noqa: F401
        from tconnectsync import secret
        from tconnectsync.api import TConnectApi

        self.assertEqual(secret.TCONNECT_REGION, 'EU')

        with requests_mock.Mocker() as m:
            register_eu_endpoints(m)

            api = TConnectApi(secret.TCONNECT_EMAIL, secret.TCONNECT_PASSWORD)
            self.assertEqual(api.region, 'EU')
            self.assertEqual(api.tandemsource.LOGIN_API_URL, EU_LOGIN_URL)
            self.assert_eu_login_flow(m)


class TestEuRegionThroughMainEntrypoint(EuRegionTestBase):
    """Full `tconnectsync --check-login` runs through main()."""

    def run_check_login(self, tconnectsync, argv):
        with requests_mock.Mocker() as m:
            register_eu_endpoints(m)
            register_nightscout_endpoints(m)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                tconnectsync.main(argv)
        return m, stdout.getvalue()

    def assert_full_eu_check_login(self, m, output):
        self.assert_eu_login_flow(m)
        calls = self.called(m)
        self.assertIn(('GET', EU_PUMPER_URL), calls)
        self.assertIn(('GET', EU_PUMP_LOGS_URL), calls)
        self.assertIn('No API errors returned!', output)
        self.assertNotIn('API errors occurred', output)

    def test_check_login_with_region_from_environment_variable(self):
        tconnectsync = self.import_tconnectsync({'TCONNECT_REGION': 'EU'})
        m, output = self.run_check_login(tconnectsync, ['--check-login'])
        self.assertIn("TCONNECT_REGION='EU'", output)
        self.assert_full_eu_check_login(m, output)

    def test_check_login_with_region_from_cli_flag(self):
        # No TCONNECT_REGION configured: --region EU alone must route
        # everything to the EU endpoints.
        tconnectsync = self.import_tconnectsync()
        self.assertEqual(tconnectsync.secret.TCONNECT_REGION, 'US')
        m, output = self.run_check_login(tconnectsync, ['--check-login', '--region', 'EU'])
        self.assert_full_eu_check_login(m, output)


if __name__ == '__main__':
    unittest.main()
