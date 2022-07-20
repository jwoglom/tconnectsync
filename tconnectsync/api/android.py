import requests
import json
import urllib
import datetime
import csv
import base64
import arrow
import time
import logging

from bs4 import BeautifulSoup

from ..util import timeago
from .common import ApiException, ApiLoginException, parse_date, base_session

logger = logging.getLogger(__name__)

"""
The AndroidApi class contains methods which are queried in the t:connect
Android application. These methods are a part of the tdc API which require
Android specific credentials.
"""
class AndroidApi:
    BASE_URL = 'https://tdcservices.tandemdiabetes.com/'
    OAUTH_TOKEN_PATH = 'cloud/oauth2/token'
    OAUTH_SCOPES = 'cloud.account cloud.upload cloud.accepttcpp cloud.email cloud.password'

    # These credentials are found in source code
    ANDROID_API_USERNAME = base64.b64decode('QzIzMzFDRDYtRDQ1MC00OTVFLTlDMTktNjcyMTUyMzBDODVD').decode()
    ANDROID_API_PASSWORD = base64.b64decode('dHo0MzNLVzVRREM5VjdmIXo2QF4ybyZZNlNHR1lo').decode()

    ANDROID_USER_AGENT = 'Dalvik/2.1.0 (Linux; U; Android 12; Pixel 4a Build/SP2A.220305.012)'

    # These tokens are separate from the "standard" tdcservices API
    accessToken = None
    accessTokenExpiresAt = None
    refreshToken = None
    refreshTokenExpiresAt = None
    userId = None
    patientObjectId = None

    def __init__(self, email, password):
        self.session = base_session()
        self.login(email, password)
        self._email = email
        self._password = password

    def login(self, email, password):
        r = self.session.post(
            self.BASE_URL + self.OAUTH_TOKEN_PATH,
            {
                'username': email,
                'password': password,
                'grant_type': 'password',
                'scope': self.OAUTH_SCOPES
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': self.ANDROID_USER_AGENT
            },
            auth=requests.auth.HTTPBasicAuth(self.ANDROID_API_USERNAME, self.ANDROID_API_PASSWORD)
        )

        if r.status_code != 200:
            raise ApiLoginException(r.status_code, 'Received HTTP %s during login: %s' % (r.status_code, r.text))

        j = r.json()
        if "user" not in j or not j["user"]:
            raise ApiException(r.status_code, 'No user details present in AndroidApi oauth response: %s' % r.text)

        self.accessToken = j["accessToken"]
        self.accessTokenExpiresAt = j["accessTokenExpiresAt"]
        # NOTE: the refresh token is currently unused, instead a new access
        # token is obtained from scratch by re-logging in when it expires.
        self.refreshToken = j["refreshToken"]
        self.refreshTokenExpiresAt = j["refreshTokenExpiresAt"]
        self.userId = j["user"]["id"]

        logger.info("Logged in to AndroidApi successfully (expiration: %s, %s)" % (self.accessTokenExpiresAt, timeago(self.accessTokenExpiresAt)))

    def needs_relogin(self):
        diff = (arrow.get(self.accessTokenExpiresAt) - arrow.get())
        return (diff.seconds <= 5 * 60)

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token')
        return {'Authorization': 'Bearer %s' % self.accessToken}

    def _get(self, endpoint, query={}, **kwargs):
        r = self.session.get(self.BASE_URL + endpoint, data=query, headers={
            'User-Agent': self.ANDROID_USER_AGENT,
            'Content-Type': 'application/json',
            **self.api_headers()
        }, **kwargs)

        if r.status_code != 200:
            raise ApiException(r.status_code, "Android API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    def get(self, endpoint, query={}, tries=0, **kwargs):
        try:
            return self._get(endpoint, query, **kwargs)
        except ApiException as e:
            if tries > 0:
                raise ApiException(e.status_code, "Android API HTTP %s on retry #%d: %s" % (e.status_code, tries, e))

            # Trigger automatic re-login, and try again once
            if e.status_code == 401:
                self.accessTokenExpiresAt = time.time()
                self.login(self._email, self._password)

                return self.get(endpoint, query, tries=tries+1, **kwargs)

            if e.status_code == 500:
                return self.get(endpoint, query, tries=tries+1, **kwargs)

            raise e


    def post(self, endpoint, query={}, **kwargs):
        r = self.session.post(self.BASE_URL + endpoint, query, headers=self.api_headers(), **kwargs)
        if r.status_code != 200:
            raise ApiException(r.status_code, "Internal API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    """
    Returns the most recent event ID that was uploaded for the given pump.
    {'maxPumpEventIndex': <integer>, 'processingStatus': 1}
    """
    def last_event_uploaded(self, pump_serial_number):
        return self.get('cloud/upload/getlasteventuploaded?sn=%d' % pump_serial_number)

    """
    Returns user login information about a tconnect account.
    {'firstName': <string>, 'lastName': <string>, 'birthDate': 'YYYY-MM-DDT00:00:00.000Z',
     'emailAddress': <string>, 'secretQuestion': <string>, 'secretAnswer': <string>,
     'secretQuestionId': <integer>}
    """
    def patient_info(self):
        return self.get('cloud/account/patient_info')


    # TODO: these methods are used in the web app, not the Android app,
    # but support the same auth tokens and are on this domain. They should
    # be moved to a new Api class.
    # 3/17/2022: the API appears to be more stringently checking scopes,
    # and some of these endpoints no longer work with the API token scoped
    # to the Android app.

    """
    Returns BG and pump threshold values.
    {'targetBGHigh': <integer>, 'targetBGLow': <integer>, 'hypoThreshold': <integer>,
     'hyperThreshold': <integer>, 'siteChangeThreshold': <integer>,
     'cartridgeChangeThreshold': <integer>, 'tubingChangeThreshold': <integer>}
    """
    def therapy_thresholds(self):
        return self.get('cloud/usersettings/api/therapythresholds?userId=%s' % self.userId)

    """
    Returns therapy-related user information about a tconnect account.
    {'userID': <string>, 'targetBgHigh': <integer>, 'targetBgLow': <integer>,
     'hypoThreshold': <integer>, 'hyperThreshold': <integer>,
     'dateOfBirth': 'YYYY-MM-DDT00:00:00', 'age': <integer>,
     'patientFullName': <string>, 'caregiverDateOfBirth': <string>,
     'hasCGM': <bool>, 'hasBASALIQ': <bool>, 'hasControlIQ': <bool>}
    """
    def user_profile(self):
        return self.get('cloud/usersettings/api/UserProfile?userId=%s' % self.userId)
