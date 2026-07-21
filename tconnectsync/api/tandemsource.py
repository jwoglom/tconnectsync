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

from typing import Any, Dict, Iterator, List, Optional, Tuple
try:
    from typing import TypedDict
except ImportError:  # Python 3.7
    from typing_extensions import TypedDict

from requests_oidc import make_auth_code_session
from requests_oidc.plugins import OSCachedPlugin
from requests_oidc.utils import ServerDetails
from requests_oauthlib import OAuth2Session
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey


from ..util import timeago, cap_length
from .common import parse_ymd_date, base_headers, base_session, ApiException, ApiLoginException
from .. import secret
from ..secret import CACHE_CREDENTIALS, CACHE_CREDENTIALS_PATH, TIMEZONE_NAME
from ..eventparser.generic import Events

logger = logging.getLogger(__name__)


def naive_local_to_utc(value: Optional[str]) -> Optional[str]:
    """Normalize a BFF pump-local naive wall-clock timestamp to a true UTC
    ISO-8601 string.

    The BFF sends maxDateOfEvents / availableDataRange.start with no tz
    (e.g. "2022-02-16T22:45:58") even though they are the pump's local
    wall-clock time. Downstream consumers parse them with arrow.get(...),
    which assumes UTC, and compare against arrow.utcnow() / time.time()
    (real UTC), so we shift them here by interpreting the naive value in the
    configured TIMEZONE_NAME and converting to UTC. Values that already
    carry a tz (defensive; not seen for these two fields) are passed
    through unchanged so we never double-shift. None passes through as None
    (never-uploaded pumps).
    """
    if not value:
        return value
    # If the string already carries a tz (a trailing 'Z' or a +HH:MM /
    # -HH:MM offset after the time portion), trust it and never double-shift.
    # Otherwise it's a naive pump-local wall-clock value: interpret it in the
    # configured TIMEZONE_NAME. (Per the BFF data these two fields are always
    # naive; the has-tz branch is purely defensive.)
    time_part = value.split('T', 1)[-1]
    has_tz = value.endswith('Z') or '+' in time_part or '-' in time_part
    if has_tz:
        parsed = arrow.get(value)
    else:
        parsed = arrow.get(value, tzinfo=TIMEZONE_NAME)
    return parsed.to('UTC').isoformat()


class JwtClaims(TypedDict, total=False):
    """Decoded OIDC id_token claims stored on TandemSourceApi.jwtData.

    pumperId and accountId are UUID strings (not ints); the *time/iat/exp/nbf
    fields are unix timestamps.
    """
    iss: str
    nbf: int
    iat: int
    exp: int
    aud: str
    amr: List[str]
    at_hash: str
    sid: str
    sub: str
    auth_time: int
    idp: str
    email: str
    tandem_roles: List[str]
    roles: List[str]
    accountId: str
    pumperId: str
    countrySubdivision: str
    preferredLanguage: str
    family_name: str
    given_name: str
    preferred_username: str
    name: str
    email_verified: bool


class AvailableDataRange(TypedDict):
    """`availableDataRange` on a BffPump. start/end are ISO-8601 datetime
    strings, or null for a pump that has never uploaded."""
    start: Optional[str]
    end: Optional[str]


class PumpSettingsEnvelope(TypedDict):
    """`settings` on a BffPump. `details` is the full pump settings blob,
    parsed by tconnectsync.domain.tandemsource.pump_settings.PumpSettings."""
    id: str
    deviceAssignmentId: str
    uploadedTimeStamp: str
    settingsHash: str
    uploadId: str
    details: dict


class BffPumpRequired(TypedDict):
    """Fields always present on a BffPump, even for a never-uploaded pump
    (verified against a real captured GET api/reports/bff/pumper/{pumperId}
    response).

    `assignmentId` is the pump's UUID device id used as the path segment for
    the pump-logs endpoint (replaces the old numeric tconnectDeviceId).
    """
    assignmentId: str
    serialNumber: str
    modelNumber: str
    modelName: str
    softwareVersion: str


class BffPump(BffPumpRequired, total=False):
    """One element of BffPumper.pumps, from GET api/reports/bff/pumper/{pumperId}.

    Extends BffPumpRequired with fields that are null or absent for
    never-uploaded or retired pumps (settings, *Date*, lastUploadClientType,
    glucoseUnit, availableDataRange.start/end), hence total=False. `algorithm`
    is optional in the canonical BFF source (PumpAlgorithm | undefined) and so
    must be accessed defensively.
    """
    algorithm: Optional[str]
    availableDataRange: AvailableDataRange
    glucoseUnit: Optional[str]
    lastUploadDate: Optional[str]
    maxDateOfEvents: Optional[str]
    partNumber: str
    lastUploadClientType: Optional[str]
    settings: Optional[PumpSettingsEnvelope]


class BffPumper(TypedDict, total=False):
    """Response of GET api/reports/bff/pumper/{pumperId} (the BFF device list
    that replaces pumpeventmetadata)."""
    firstName: str
    lastName: str
    name: str
    dateOfBirth: str
    lowGlucoseThreshold: int
    highGlucoseThreshold: int
    country: str
    pumps: List[BffPump]


class PumpLogEvent(TypedDict):
    """One entry in a PumpLogsResponse (events[] or clockChanges[]) from
    GET api/reports/bff/pump-logs/{deviceAssignmentId}. The server pre-decodes
    each event, so eventProperties holds already-decoded per-event fields
    (values are int/float/list/str keyed by camelCase field name).

    pumpDateTime is the pump's local wall-clock time (ISO-8601, no tz);
    estimatedDateTime is the same value with a 'Z' suffix. eventCode matches
    the numeric event id in EVENT_IDS; sequenceNumber is the old seqNum.
    """
    deviceAssignmentId: str
    eventCode: int
    sequenceGroup: int
    sequenceNumber: int
    pumpDateTime: str
    eventProperties: Dict[str, Any]
    estimatedDateTime: str


class PumpLogsResponse(TypedDict):
    """Response of GET api/reports/bff/pump-logs/{deviceAssignmentId}. Replaces
    the old base64 reportsfacade/pumpevents payload. clockChanges (eventCodes
    13/14) are returned separately and span the device's full history."""
    events: List[PumpLogEvent]
    clockChanges: List[PumpLogEvent]


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
        'TDC_OIDC_CLIENT_ID': '0oa4wnbvtladeyVZX4h7',
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

    def __init__(self, email: str, password: str, region: Optional[str] = None) -> None:
        # No region means "use the configured TCONNECT_REGION": a hardcoded
        # US default would send EU accounts to the US endpoints (#152).
        if not region:
            region = secret.TCONNECT_REGION
        self.region = region.upper()
        if self.region not in ['US', 'EU']:
            raise ValueError(f"Invalid region '{region}'. Must be 'US' or 'EU'.")
        
        self._region_urls = self._US_URLS if self.region == 'US' else self._EU_URLS
        
        self.login(email, password)
        self._email = email
        self._password = password

    @property
    def LOGIN_API_URL(self) -> str:
        return self._region_urls['LOGIN_API_URL']

    @property
    def TDC_OAUTH_AUTHORIZE_URL(self) -> str:
        return self._region_urls['TDC_OAUTH_AUTHORIZE_URL']

    @property
    def TDC_OIDC_JWKS_URL(self) -> str:
        return self._region_urls['TDC_OIDC_JWKS_URL']

    @property
    def TDC_OIDC_ISSUER(self) -> str:
        return self._region_urls['TDC_OIDC_ISSUER']

    @property
    def TDC_OIDC_CLIENT_ID(self) -> str:
        return self._region_urls['TDC_OIDC_CLIENT_ID']

    @property
    def SOURCE_URL(self) -> str:
        return self._region_urls['SOURCE_URL']

    def login(self, email: str, password: str) -> bool:
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

            def generate_code_verifier() -> str:
                """Generates a high-entropy code verifier."""
                code_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode('utf-8').rstrip('=')
                return code_verifier

            def generate_code_challenge(verifier: str) -> str:
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

    def extract_jwt(self) -> None:
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
        # A JWKS endpoint publishes public keys; from_jwk() is typed as possibly
        # returning a private key, so narrow it before passing to jwt.decode().
        if not isinstance(key, RSAPublicKey):
            raise ApiException(0, 'JWK is not an RSA public key for JWT: %s' % kid)

        audience = self.TDC_OIDC_CLIENT_ID
        issuer = self.TDC_OIDC_ISSUER

        # Decode and verify the ID Token. Per OIDC the id_token's `aud` equals
        # the client_id, so validate it. But if Tandem ever issues an id_token
        # with a different audience, fall back to skipping only the audience
        # check (signature + issuer are still verified) rather than failing
        # login outright.
        id_token_claims: JwtClaims
        try:
            id_token_claims = jwt.decode(
                id_token,
                key=key,
                algorithms=['RS256'],
                audience=audience,
                issuer=issuer,
            )
        except jwt.InvalidAudienceError:
            logger.warning(
                "id_token audience did not match client_id %s; decoding without audience verification",
                audience,
            )
            id_token_claims = jwt.decode(
                id_token,
                key=key,
                algorithms=['RS256'],
                issuer=issuer,
                options={"verify_aud": False},
            )

        logger.info("Decoded JWT: %s" % json.dumps(id_token_claims))

        self.jwtData: JwtClaims = id_token_claims
        self.pumperId: str = id_token_claims['pumperId']
        self.accountId: str = id_token_claims['accountId']

    def try_load_cached_creds(self, email: str) -> bool:
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

        def est_time(t: arrow.Arrow) -> str:
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


    def cache_creds(self, email: str) -> None:
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


    def needs_relogin(self) -> bool:
        if not self.accessTokenExpiresAt:
            return False

        diff = (arrow.get(self.accessTokenExpiresAt) - arrow.get())
        return (diff.seconds <= 5 * 60)

    def api_headers(self) -> Dict[str, str]:
        if not self.accessToken:
            raise Exception('No access token provided')
        return {
            'Authorization': 'Bearer %s' % self.accessToken,
            # The WAF enforces same-origin: Origin/Referer must match SOURCE_URL
            # (source.tandemdiabetes.com / source.eu.tandemdiabetes.com), otherwise
            # it returns HTTP 403 ("The request is blocked").
            'Origin': self.SOURCE_URL.rstrip('/'),
            'Referer': self.SOURCE_URL,
            **base_headers()
        }

    def _get(self, endpoint: str, query: dict) -> Any:
        r = base_session().get(self.SOURCE_URL + endpoint, data=query, headers=self.api_headers())

        if r.status_code != 200:
            raise ApiException(r.status_code, "TandemSourceApi HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()


    def get(self, endpoint: str, query: dict, tries: int = 0) -> Any:
        try:
            return self._get(endpoint, query)
        except ApiException as e:
            logger.warning("Received ApiException in TandemSourceApi with endpoint '%s' (tries %d): %s" % (endpoint, tries, e))
            if tries > 0:
                raise ApiException(e.status_code, "TandemSourceApi HTTP %d on retry #%d: %s", e.status_code, tries, e)

            # Trigger automatic re-login, and try again once
            if e.status_code == 401:
                logger.info("Performing automatic re-login after HTTP 401 for TandemSourceApi")
                self.accessTokenExpiresAt = arrow.get()
                self.login(self._email, self._password)

                return self.get(endpoint, query, tries=tries+1)

            if e.status_code == 500:
                return self.get(endpoint, query, tries=tries+1)

            raise e

    """
    Returns information about the user and available pumps.
    """
    # Response shape is undocumented and unused by callers, so it stays Any.
    def pumper_info(self) -> Any:
        return self.get('api/pumpers/pumpers/%s' % (self.pumperId), {})

    def get_pumper(self) -> BffPumper:
        """Returns the pumper's profile plus the list of pumps on the account
        (BffPumper.pumps) from the new BFF endpoint. Replaces the old
        reportsfacade pump-event-metadata endpoint: pumps[].assignmentId is the
        UUID device id used by the pump-logs endpoint, and
        pumps[].settings.details carries the pump settings blob."""
        return self.get('api/reports/bff/pumper/%s' % (self.pumperId), {})

    # Matches the Tandem Source web app's getLogIDList() (55 IDs) as observed in
    # the live GET api/reports/bff/pump-logs request. Includes FSL3 ids 477/480/486.
    DEFAULT_EVENT_IDS: List[int] = [229,5,28,4,26,99,279,3,16,59,21,55,20,280,64,65,66,61,33,371,171,369,460,172,370,461,372,480,399,256,213,406,477,394,212,404,214,405,486,447,313,60,14,6,90,230,140,12,11,53,13,63,203,307,191]

    def get_pump_logs(self, device_id: str, min_date: Optional[str] = None, max_date: Optional[str] = None, event_ids_filter: Optional[List[int]] = DEFAULT_EVENT_IDS) -> PumpLogsResponse:
        """Fetch pre-decoded pump events for a single date window from the BFF
        endpoint GET api/reports/bff/pump-logs/{device_id}. device_id is the
        UUID assignmentId (BffPump.assignmentId from get_pumper()). Returns
        {events, clockChanges}.
        The server caps the window at ~4 weeks; callers needing a longer range
        must page by date window (see pump_events).

        Note: the server currently ignores eventIds and returns every event in
        the window regardless of the filter (verified against live accounts), so
        the effective filtering happens client-side via EventClass dispatch. We
        still send eventIds to mirror the web app and stay forward-compatible."""
        minDate = parse_ymd_date(min_date)
        maxDate = parse_ymd_date(max_date)
        logger.debug(f'get_pump_logs({device_id}, {minDate}, {maxDate})')

        query = urllib.parse.urlencode({
            'pumperId': self.pumperId,
            'startDate': '%sT00:00:00Z' % minDate,
            'endDate': '%sT23:59:59Z' % maxDate,
            'eventIds': ','.join(map(str, event_ids_filter)) if event_ids_filter else '',
        })
        return self.get('api/reports/bff/pump-logs/%s?%s' % (device_id, query), {})

    # The pump-logs endpoint caps each request at roughly four weeks, so a
    # longer range is paged in windows no larger than this.
    PUMP_LOGS_WINDOW_DAYS = 28

    @classmethod
    def _pump_log_windows(cls, min_date: Optional[str], max_date: Optional[str]) -> List[Tuple[str, str]]:
        """Split the (min_date, max_date) range into inclusive date windows no
        larger than PUMP_LOGS_WINDOW_DAYS. A None bound defaults to today (via
        parse_ymd_date), so an unset range yields a single one-day window."""
        start = arrow.get(parse_ymd_date(min_date))
        end = arrow.get(parse_ymd_date(max_date))
        if end < start:
            start, end = end, start

        windows = []
        cur = start
        while cur <= end:
            win_end = min(cur.shift(days=cls.PUMP_LOGS_WINDOW_DAYS - 1), end)
            windows.append((cur.format('YYYY-MM-DD'), win_end.format('YYYY-MM-DD')))
            cur = win_end.shift(days=1)
        return windows

    """
    Fetch and parse pump events from the pump-logs endpoint.
    Default of fetch_all_event_types=False will filter to the same event ids used in the Tandem Source backend.
    If fetch_all_event_types=True, then all event types from the history log will be returned.
    tconnect_device_id is the UUID assignmentId from get_pumper() pumps (BffPump.assignmentId).
    """
    def pump_events(self, tconnect_device_id: str, min_date: Optional[str] = None, max_date: Optional[str] = None, fetch_all_event_types: bool = False) -> Iterator:
        event_ids_filter = None if fetch_all_event_types else self.DEFAULT_EVENT_IDS

        # Page across date windows, deduplicating events that appear in more
        # than one window by their (sequenceGroup, sequenceNumber) identity.
        seen = set()
        events = []
        clock_change_count = 0
        for window_start, window_end in self._pump_log_windows(min_date, max_date):
            resp = self.get_pump_logs(tconnect_device_id, window_start, window_end, event_ids_filter)
            clock_change_count += len(resp.get('clockChanges') or [])
            for event in resp.get('events') or []:
                key = (event.get('sequenceGroup'), event.get('sequenceNumber'))
                if key in seen:
                    continue
                seen.add(key)
                events.append(event)

        # clockChanges (LID_TIME_CHANGED/LID_DATE_CHANGED) are not consumed by any
        # processor, so they are counted for visibility but not parsed.
        logger.info(f"Read {len(events)} events ({clock_change_count} clock changes skipped)")
        return Events(events)

    def pump_clock_changes(self, tconnect_device_id: str, min_date: Optional[str] = None, max_date: Optional[str] = None) -> Iterator:
        """Fetch the pump-logs clockChanges (LID_TIME_CHANGED/LID_DATE_CHANGED)
        across the date range, deduplicated by (sequenceGroup, sequenceNumber).
        tconnect_device_id is the UUID assignmentId from get_pumper() pumps."""
        seen = set()
        clock_changes = []
        for window_start, window_end in self._pump_log_windows(min_date, max_date):
            resp = self.get_pump_logs(tconnect_device_id, window_start, window_end)
            for event in resp.get('clockChanges') or []:
                key = (event.get('sequenceGroup'), event.get('sequenceNumber'))
                if key in seen:
                    continue
                seen.add(key)
                clock_changes.append(event)

        logger.info(f"Read {len(clock_changes)} clock changes")
        return Events(clock_changes)


