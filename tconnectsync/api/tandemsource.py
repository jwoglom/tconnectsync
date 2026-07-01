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
from ..eventparser.json_events import build_events_from_json

logger = logging.getLogger(__name__)


def _bff_transform_settings(pump):
    """Reshape a BFF pump's ``settings.details`` into the legacy ``settings``
    dict consumed by ``UpdateProfiles`` / ``domain.tandemsource.PumpSettings``.

    The BFF renamed ``tDependentSegs`` -> ``timeDependentSegments`` and flattened
    the CGM alert thresholds; the per-segment fields are otherwise unchanged.
    """
    details = (pump.get('settings') or {}).get('details') or {}
    profiles = details.get('profiles') or {}
    cgm = details.get('cgmSettings') or {}

    def segment(seg):
        return {
            'startTime': seg.get('startTime', 0),
            'basalRate': seg.get('basalRate', 0),   # milliunits/hr
            'isf': seg.get('isf', 0),
            'carbRatio': seg.get('carbRatio', 0),    # milli-grams/unit
            'targetBg': seg.get('targetBg', 0),
        }

    def profile(prof):
        return {
            'name': prof.get('name'),
            'idp': prof.get('idp', 0),
            'insulinDuration': prof.get('insulinDuration', 300),
            'carbEntry': 1 if prof.get('carbEntry') else 0,
            'maxBolus': prof.get('maxBolus', 0),
            'tDependentSegs': [segment(s) for s in (prof.get('timeDependentSegments') or [])],
        }

    def alert(prefix):
        return {
            'mgPerDl': cgm.get(prefix + 'MgPerDl', 0),
            'enabled': 1 if cgm.get(prefix + 'Enabled') else 0,
            'duration': cgm.get(prefix + 'DurationMin', 0),
            'status': 0,
        }

    return {
        'profiles': {
            'activeIdp': profiles.get('activeIdp', 0),
            'profile': [profile(p) for p in (profiles.get('profile') or [])],
        },
        'cgmSettings': {
            'highGlucoseAlert': alert('highGlucoseAlert'),
            'lowGlucoseAlert': alert('lowGlucoseAlert'),
        },
    }


def _bff_remap_pump(pump):
    """Remap one BFF ``pumper`` pump entry to the legacy pumpeventmetadata dict."""
    data_range = pump.get('availableDataRange') or {}
    return {
        'tconnectDeviceId': pump.get('assignmentId'),
        'serialNumber': pump.get('serialNumber'),
        'modelNumber': pump.get('modelNumber'),
        'softwareVersion': pump.get('softwareVersion'),
        'maxDateWithEvents': pump.get('maxDateOfEvents'),
        'minDateWithEvents': data_range.get('start'),
        # The legacy consumer reads settings from lastUpload['settings'].
        'lastUpload': {'settings': _bff_transform_settings(pump)},
        'lastUploadDate': pump.get('lastUploadDate'),
    }


def _bff_select_active_pumps(pumps):
    """The BFF lists every pump ever associated with the account (including some
    with null/placeholder dates). Return only pump(s) uploaded within the last 30
    days, falling back to the single most-recently-uploaded pump."""
    def uploaded_recently(pump):
        try:
            return bool(pump['lastUploadDate']) and \
                (arrow.utcnow() - arrow.get(pump['lastUploadDate'])).days <= 30
        except (TypeError, ValueError, arrow.parser.ParserError):
            return False

    recent = [p for p in pumps if uploaded_recently(p)]
    if recent:
        return recent
    dated = [p for p in pumps if p.get('lastUploadDate')]
    if dated:
        return [max(dated, key=lambda p: arrow.get(p['lastUploadDate']))]
    return pumps


class TandemSourceApi:
    # Common URLs that are shared between regions
    LOGIN_PAGE_URL = 'https://sso.tandemdiabetes.com/'
    TDC_AUTH_CALLBACK_URL = 'https://sso.tandemdiabetes.com/auth/callback'
    
    # US Region URLs (default)
    _US_URLS = {
        'LOGIN_API_URL': 'https://tdcservices.tandemdiabetes.com/accounts/api/login',
        'TDC_OAUTH_AUTHORIZE_URL': 'https://tdcservices.tandemdiabetes.com/accounts/api/oauth2/v1/authorize',
        'TDC_OIDC_JWKS_URL': 'https://tdcservices.tandemdiabetes.com/accounts/api/.well-known/openid-configuration/jwks',
        'TDC_OIDC_ISSUER': 'https://tdcservices.tandemdiabetes.com/accounts/api',
        'TDC_OIDC_CLIENT_ID': '0oa27ho9tpZE9Arjy4h7',
        'SOURCE_URL': 'https://source.tandemdiabetes.com/',
        'REDIRECT_URI': 'https://sso.tandemdiabetes.com/auth/callback',
        'TOKEN_ENDPOINT': 'https://tdcservices.tandemdiabetes.com/accounts/api/connect/token',
        'AUTHORIZATION_ENDPOINT': 'https://tdcservices.tandemdiabetes.com/accounts/api/connect/authorize'
    }
    
    # EU Region URLs
    _EU_URLS = {
        'LOGIN_API_URL': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api/login',
        'TDC_OAUTH_AUTHORIZE_URL': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api/oauth2/v1/authorize',
        'TDC_OIDC_JWKS_URL': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api/.well-known/openid-configuration/jwks',
        'TDC_OIDC_ISSUER': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api',
        'TDC_OIDC_CLIENT_ID': '1519e414-eeec-492e-8c5e-97bea4815a10',
        'SOURCE_URL': 'https://source.eu.tandemdiabetes.com/',
        'REDIRECT_URI': 'https://source.eu.tandemdiabetes.com/authorize/callback',
        'TOKEN_ENDPOINT': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api/connect/token',
        'AUTHORIZATION_ENDPOINT': 'https://tdcservices.eu.tandemdiabetes.com/accounts/api/connect/authorize'
    }

    def __init__(self, email, password, region='US'):
        self.region = region.upper()
        if self.region not in ['US', 'EU']:
            raise ValueError(f"Invalid region '{region}'. Must be 'US' or 'EU'.")
        
        self._region_urls = self._US_URLS if self.region == 'US' else self._EU_URLS
        
        self.login(email, password)
        self._email = email
        self._password = password

    @property
    def LOGIN_API_URL(self):
        return self._region_urls['LOGIN_API_URL']
    
    @property
    def TDC_OAUTH_AUTHORIZE_URL(self):
        return self._region_urls['TDC_OAUTH_AUTHORIZE_URL']
    
    @property
    def TDC_OIDC_JWKS_URL(self):
        return self._region_urls['TDC_OIDC_JWKS_URL']
    
    @property
    def TDC_OIDC_ISSUER(self):
        return self._region_urls['TDC_OIDC_ISSUER']
    
    @property
    def TDC_OIDC_CLIENT_ID(self):
        return self._region_urls['TDC_OIDC_CLIENT_ID']
    
    @property
    def SOURCE_URL(self):
        return self._region_urls['SOURCE_URL']

    def login(self, email, password):
        logger.info(f"Logging in to TandemSourceApi ({self.region} region)...")
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
            redirect_uri = self._region_urls['REDIRECT_URI']
            scope = 'openid profile email'

            token_endpoint = self._region_urls['TOKEN_ENDPOINT']

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

            authorization_endpoint = self._region_urls['AUTHORIZATION_ENDPOINT']

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

        # Check if cached region matches current region
        cached_region = _saved_blob.get('cache_creds_region', 'US')  # Default to US for backward compatibility
        if cached_region != self.region:
            logger.warning(f"Cached credentials are for a different region ({cached_region} in cache, but using {self.region}), skipping")
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
            'cache_creds_region': self.region,  # Store the region in cache
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
            # The BFF endpoints are served from source.tandemdiabetes.com and the
            # WAF rejects (HTTP 403) requests carrying the legacy tconnect origin.
            'Origin': 'https://source.tandemdiabetes.com',
            'Referer': 'https://source.tandemdiabetes.com/',
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
        # Tandem retired api/reports/reportsfacade/{pumperId}/pumpeventmetadata on
        # 2026-06-30 (issue #146); pump metadata now comes from the BFF pumper
        # endpoint, which we remap to the legacy per-pump dict shape.
        body = self.get('api/reports/bff/pumper/%s' % (self.pumperId), {})
        pumps = [_bff_remap_pump(p) for p in body.get('pumps', [])]
        return _bff_select_active_pumps(pumps)

    DEFAULT_EVENT_IDS = [229,5,28,4,26,99,279,3,16,59,21,55,20,280,64,65,66,61,33,371,171,369,460,172,370,461,372,399,256,213,406,394,212,404,214,405,447,313,60,14,6,90,230,140,12,11,53,13,63,203,307,191]

    """
    Returns the raw BFF pump-logs response (JSON) for pump events.
    tconnect_device_id is "tconnectDeviceId" from pump_event_metadata()
    """
    def pump_events_raw(self, tconnect_device_id, min_date=None, max_date=None, event_ids_filter=DEFAULT_EVENT_IDS):
        # The BFF pump-logs endpoint takes ISO-8601 start/end datetimes (rather
        # than the old YYYY-MM-DD minDate/maxDate) and returns structured JSON.
        start = arrow.get(min_date).format('YYYY-MM-DD') + 'T00:00:00Z' if min_date else arrow.utcnow().shift(days=-1).format('YYYY-MM-DD') + 'T00:00:00Z'
        end = arrow.get(max_date).shift(days=1).format('YYYY-MM-DD') + 'T00:00:00Z' if max_date else arrow.utcnow().shift(days=1).format('YYYY-MM-DD') + 'T00:00:00Z'
        logger.debug(f'pump_events_raw({tconnect_device_id}, {start}, {end})')

        eventIdsFilter = '%2C'.join(map(str, event_ids_filter)) if event_ids_filter else None
        return self.get('api/reports/bff/pump-logs/%s?pumperId=%s&startDate=%s&endDate=%s%s' % (
            tconnect_device_id,
            self.pumperId,
            start,
            end,
            '&eventIds=%s' % eventIdsFilter if eventIdsFilter else ''
        ), {})

    """
    Fetch and decode pump events from the BFF pump-logs endpoint.
    Default of fetch_all_events=False will filter to the same eventids used in the Tandem Source backend.
    If fetch_all_events=True, then all event types from the history log will be returned.
    """
    def pump_events(self, tconnect_device_id, min_date=None, max_date=None, fetch_all_event_types=False):
        body = self.pump_events_raw(
            tconnect_device_id,
            min_date,
            max_date,
            event_ids_filter=None if fetch_all_event_types else self.DEFAULT_EVENT_IDS
        )

        events = build_events_from_json(body)
        logger.info(f"Read {len(events)} events from BFF pump-logs")
        return events


