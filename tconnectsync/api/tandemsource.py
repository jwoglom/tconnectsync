import urllib
import arrow
import time
import logging
import json
import base64
import hashlib
import os
import jwt
import pickle

from requests_oidc import make_auth_code_session
from requests_oidc.plugins import OSCachedPlugin
from requests_oidc.utils import ServerDetails
from requests_oauthlib import OAuth2Session
from jwt.algorithms import RSAAlgorithm


from ..util import timeago, cap_length
from .common import parse_ymd_date, base_headers, base_session, ApiException, ApiLoginException
from ..secret import CACHE_CREDENTIALS, CACHE_CREDENTIALS_PATH
from ..eventparser.generic import Events, decode_raw_events, EVENT_LEN

logger = logging.getLogger(__name__)

class TandemSourceApi:
    LOGIN_PAGE_URL = 'https://sso.tandemdiabetes.com/'
    LOGIN_API_URL = 'https://tdcservices.tandemdiabetes.com/accounts/api/login'
    TDC_AUTH_CALLBACK_URL = 'https://sso.tandemdiabetes.com/auth/callback'
    TDC_OAUTH_AUTHORIZE_URL = 'https://tdcservices.tandemdiabetes.com/accounts/api/oauth2/v1/authorize'
    TDC_OIDC_JWKS_URL = 'https://tdcservices.tandemdiabetes.com/accounts/api/.well-known/openid-configuration/jwks'
    TDC_OIDC_ISSUER = 'https://tdcservices.tandemdiabetes.com/accounts/api' # openid_config['issuer']
    TDC_OIDC_CLIENT_ID = '0oa27ho9tpZE9Arjy4h7'
    SOURCE_URL = 'https://source.tandemdiabetes.com/'


    def __init__(self, email, password):
        self.login(email, password)
        self._email = email
        self._password = password

    def login(self, email, password):
        logger.info("Logging in to TandemSourceApi...")
        if self.try_load_cached_creds(email):
            logger.info("Successfully used cached credentials")
            return True

        with base_session() as s:
            initial = s.get(self.LOGIN_PAGE_URL, headers=base_headers())

            data = {
                "username": email,
                "password": password
            }

            req = s.post(self.LOGIN_API_URL, json=data, headers={'Referer': self.LOGIN_PAGE_URL, **base_headers()}, allow_redirects=False)

            logger.debug("1. made POST to LOGIN_API")
            # {"redirectUrl":"/","status":"SUCCESS"}
            if req.status_code != 200:
                raise ApiException(req.status_code, 'Error sending POST to login_api_url: %s' % req.text)

            req_json = req.json()
            login_ok = req_json.get('status', '') == 'SUCCESS'

            if not login_ok:
                raise ApiException(req.status_code, 'Error parsing login_api_url: %s' % json.dumps(req_json))

            logger.debug("2. starting OIDC")

            # oidc
            client_id = self.TDC_OIDC_CLIENT_ID
            redirect_uri = 'https://sso.tandemdiabetes.com/auth/callback' # must be an allowlisted URI
            scope = 'openid profile email'

            token_endpoint = 'https://tdcservices.tandemdiabetes.com/accounts/api/connect/token' #openid_config['token_endpoint']


            def generate_code_verifier():
                """Generates a high-entropy code verifier."""
                code_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode('utf-8').rstrip('=')
                return code_verifier

            def generate_code_challenge(verifier):
                """Generates a code challenge from the code verifier."""
                sha256_digest = hashlib.sha256(verifier.encode('utf-8')).digest()
                code_challenge = base64.urlsafe_b64encode(sha256_digest).decode('utf-8').rstrip('=')
                return code_challenge


            code_verifier = generate_code_verifier()
            code_challenge = generate_code_challenge(code_verifier)

            authorization_endpoint = 'https://tdcservices.tandemdiabetes.com/accounts/api/connect/authorize' #openid_config['authorization_endpoint']

            oidc_step1_params = {
                'client_id': client_id,
                'response_type': 'code',
                'scope': scope,
                'redirect_uri': redirect_uri,
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256',
            }

            logger.debug("3. calling oidc_step1 with %s" % json.dumps(oidc_step1_params))
            oidc_step1 = s.get(
                authorization_endpoint + '?' + urllib.parse.urlencode(oidc_step1_params),
                headers={'Referer': self.LOGIN_PAGE_URL, **base_headers()},
                allow_redirects=True
            )


            if oidc_step1.status_code // 100 != 2:
                raise ApiException(oidc_step1.status_code, 'Got unexpected status code for oidc step1: %s' % oidc_step1.text)

            oidc_step1_loc = oidc_step1.url
            oidc_step1_query = urllib.parse.parse_qs(urllib.parse.urlparse(oidc_step1_loc).query)
            if 'code' not in oidc_step1_query:
                raise ApiException(oidc_step1.status_code, 'No code for oidc step1 ReturnUrl (%s): %s' % (oidc_step1_loc, json.dumps(oidc_step1_query)))

            oidc_step1_callback_code = oidc_step1_query['code'][0]

            oidc_step2_token_data = {
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'code': oidc_step1_callback_code,
                'redirect_uri': redirect_uri,
                'code_verifier': code_verifier,
            }

            logger.debug("4. calling oidc_step2 with %s" % json.dumps(oidc_step2_token_data))

            oidc_step2 = s.post(token_endpoint, data=oidc_step2_token_data, headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                **base_headers()
            })

            if oidc_step2.status_code//100 != 2:
                raise ApiException(oidc_step1.status_code, 'Got unexpected status code for oidc step2: %s' % oidc_step1.text)

            oidc_json = oidc_step2.json()
            logger.debug("5. parsing oidc_step2 json response: %s" % json.dumps(oidc_json))

            if not 'access_token' in oidc_json:
                raise ApiException(oidc_step1.status_code, 'Missing access_token in oidc_step2 json: %s' % json.dumps(oidc_json))

            if not 'id_token' in oidc_json:
                raise ApiException(oidc_step1.status_code, 'Missing id_token in oidc_step2 json: %s' % json.dumps(oidc_json))

            self.loginSession = s
            self.idToken = oidc_json['id_token']
            self.extract_jwt()


            self.accessToken = oidc_json['access_token']
            self.accessTokenExpiresAt = arrow.get(arrow.get().int_timestamp + oidc_json['expires_in'])

            self.cache_creds(email)

            return True

    def extract_jwt(self):
        logger.debug("6. extracting JWT from %s" % self.idToken)
        id_token = self.idToken

        jwks_response = self.loginSession.get(self.TDC_OIDC_JWKS_URL)
        jwks = jwks_response.json()
        public_keys = {}
        for jwk in jwks['keys']:
            kid = jwk['kid']
            public_keys[kid] = RSAAlgorithm.from_jwk(json.dumps(jwk))

        # Get the key ID (kid) from the headers of the ID Token
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header['kid']

        key = public_keys.get(kid)
        if not key:
            raise ApiException(0, 'Public key not found for JWT: %s' % kid)

        audience = self.TDC_OIDC_CLIENT_ID
        issuer = self.TDC_OIDC_ISSUER

        # Decode and verify the ID Token
        id_token_claims = jwt.decode(
            id_token,
            key=key,
            algorithms=['RS256'],
            audience=audience,
            issuer=issuer,
        )

        logger.info("Decoded JWT: %s" % json.dumps(id_token_claims))

        self.jwtData = id_token_claims
        self.pumperId = id_token_claims['pumperId']
        self.accountId = id_token_claims['accountId']

    def try_load_cached_creds(self, email):
        if not CACHE_CREDENTIALS:
            return False

        if not os.path.exists(CACHE_CREDENTIALS_PATH):
            logger.info("No cached credentials exist")
            return False

        _saved_blob = {}
        try:
            with open(CACHE_CREDENTIALS_PATH, 'rb') as f:
                _saved_blob = pickle.load(f)
        except Exception as e:
            logger.warning(f"Could not load cached credentials at {CACHE_CREDENTIALS_PATH}: {e}")
            return False

        if not _saved_blob:
            logger.warning(f"Could not load cached credentials at {CACHE_CREDENTIALS_PATH}: empty dict")
            return False

        if _saved_blob.get('cache_creds_version') != 1.0:
            logger.warning(f"Unexpected cache_creds_version at {CACHE_CREDENTIALS_PATH}: {_saved_blob['cache_creds_version']}, expected 1.0")
            return False

        if _saved_blob.get('cache_creds_email') != email:
            logger.warning(f"Cached credentials are for a different email ({_saved_blob['cache_creds_email']} in cache, but using {email}), skipping")
            return False

        at_expiry = _saved_blob['accessTokenExpiresAt']
        if arrow.get().int_timestamp >= arrow.get(at_expiry).int_timestamp:
            logger.info(f"Cached credentials have expired ({_saved_blob['accessTokenExpiresAt']}), skipping")
            return False

        self.jwtData = _saved_blob['jwtData']
        self.pumperId = _saved_blob['pumperId']
        self.accountId = _saved_blob['accountId']
        self.idToken = _saved_blob['idToken']
        self.accessToken = _saved_blob['accessToken']
        self.accessTokenExpiresAt = _saved_blob['accessTokenExpiresAt']
        self.loginSession = _saved_blob['loginSession']

        def est_time(t):
            now = arrow.get()
            if now < t:
                sec = (t - now).seconds
            else:
                sec = (now - t).seconds
            min = sec//60
            hr = min//60
            min = min % 60
            sec = sec % 60
            r = ''
            if hr:
                r += f'{hr} hr '
            if min:
                r += f'{min} min '
            if sec:
                r += f'{sec} sec '
            if not r:
                return 'now'
            elif now < t:
                return 'in '+r.strip()
            else:
                return r.strip()+' ago'


        sa = _saved_blob['cache_creds_saved_at']
        ex = _saved_blob['accessTokenExpiresAt']
        logger.info(f"Loaded cached credentials from {CACHE_CREDENTIALS_PATH}: saved at {sa} ({est_time(sa)}), access token expiry {ex} ({est_time(ex)})")

        return True


    def cache_creds(self, email):
        if not CACHE_CREDENTIALS:
            logger.info("Credentials caching is disabled, skipping save")
            return

        _saved_blob = {
            'cache_creds_version': 1.0,
            'cache_creds_saved_at': arrow.get(),
            'cache_creds_email': email,
            'jwtData': self.jwtData,
            'pumperId': self.pumperId,
            'accountId': self.accountId,
            'idToken': self.idToken,
            'accessToken': self.accessToken,
            'accessTokenExpiresAt': self.accessTokenExpiresAt,
            'loginSession': self.loginSession
        }

        if not os.path.exists(CACHE_CREDENTIALS_PATH):
            mkdir = os.path.dirname(CACHE_CREDENTIALS_PATH)
            logger.debug(f"Running mkdir on {mkdir}")
            os.makedirs(mkdir, exist_ok=True)

        with open(CACHE_CREDENTIALS_PATH, 'wb') as f:
            pickle.dump(_saved_blob, f)
            logger.info(f"Saved cached credentials to {CACHE_CREDENTIALS_PATH}")


    def needs_relogin(self):
        if not self.accessTokenExpiresAt:
            return False

        diff = (arrow.get(self.accessTokenExpiresAt) - arrow.get())
        return (diff.seconds <= 5 * 60)

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token provided')
        return {
            'Authorization': 'Bearer %s' % self.accessToken,
            'Origin': 'https://tconnect.tandemdiabetes.com',
            'Referer': 'https://tconnect.tandemdiabetes.com/',
            **base_headers()
        }

    def _get(self, endpoint, query):
        r = base_session().get(self.SOURCE_URL + endpoint, data=query, headers=self.api_headers())

        if r.status_code != 200:
            raise ApiException(r.status_code, "TandemSourceApi HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()


    def get(self, endpoint, query, tries=0):
        try:
            return self._get(endpoint, query)
        except ApiException as e:
            logger.warning("Received ApiException in TandemSourceApi with endpoint '%s' (tries %d): %s" % (endpoint, tries, e))
            if tries > 0:
                raise ApiException(e.status_code, "TandemSourceApi HTTP %d on retry #%d: %s", e.status_code, tries, e)

            # Trigger automatic re-login, and try again once
            if e.status_code == 401:
                logger.info("Performing automatic re-login after HTTP 401 for TandemSourceApi")
                self.accessTokenExpiresAt = time.time()
                self.login(self._email, self._password)

                return self.get(endpoint, query, tries=tries+1)

            if e.status_code == 500:
                return self.get(endpoint, query, tries=tries+1)

            raise e

    """
    Returns information about the user and available pumps.
    """
    def pumper_info(self):
        return self.get('api/pumpers/pumpers/%s' % (self.pumperId), {})

    """
    Returns metadata for pump events. Returns a list of dict's per-pump on the account.
    [
        {'tconnectDeviceId', 'serialNumber', 'modelNumber', 'minDateWithEvents', 'maxDateWithEvents', 'lastUpload', 'patientName', 'patientDateOfBirth', 'patientCareGiver', 'softwareVersion', 'partNumber'},
    ]
    """
    def pump_event_metadata(self):
        return self.get('api/reports/reportsfacade/%s/pumpeventmetadata' % (self.pumperId), {})

    DEFAULT_EVENT_IDS = [229,5,28,4,26,99,279,3,16,59,21,55,20,280,64,65,66,61,33,371,171,369,460,172,370,461,372,399,256,213,406,394,212,404,214,405,447,313,60,14,6,90,230,140,12,11,53,13,63,203,307,191]

    """
    Returns raw unparsed string for pump events
    tconnect_device_id is "tconnectDeviceId" from pump_event_metadata()
    """
    def pump_events_raw(self, tconnect_device_id, min_date=None, max_date=None, event_ids_filter=DEFAULT_EVENT_IDS):
        minDate = parse_ymd_date(min_date)
        maxDate = parse_ymd_date(max_date)
        logger.debug(f'pump_events_raw({tconnect_device_id}, {minDate}, {maxDate})')

        # default: 229,5,28,4,26,99,279,3,16,59,21,55,20,280,64,65,66,61,33,371,171,369,460,172,370,461,372,399,256,213,406,394,212,404,214,405,447,313,60,14,6,90,230,140,12,11,53,13,63,203,307,191
        eventIdsFilter = '%2C'.join(map(str, event_ids_filter)) if event_ids_filter else None
        return self.get('api/reports/reportsfacade/pumpevents/%s/%s?minDate=%s&maxDate=%s%s' % (
            self.pumperId,
            tconnect_device_id,
            minDate,
            maxDate,
            '&eventIds=%s' % eventIdsFilter if eventIdsFilter else ''
        ), {})

    """
    Fetch and decode pump events using eventparser.
    Default of fetch_all_events=False will filter to the same eventids used in the Tandem Source backend.
    If fetch_all_events=True, then all event types from the history log will be returned.
    """
    def pump_events(self, tconnect_device_id, min_date=None, max_date=None, fetch_all_event_types=False):
        pump_events_raw = self.pump_events_raw(
            tconnect_device_id,
            min_date,
            max_date,
            event_ids_filter=None if fetch_all_event_types else self.DEFAULT_EVENT_IDS
        )

        pump_events_decoded = decode_raw_events(pump_events_raw)
        logger.info(f"Read {len(pump_events_decoded)} bytes (est. {len(pump_events_decoded)/EVENT_LEN} events)")
        return Events(pump_events_decoded)


