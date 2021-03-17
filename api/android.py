import requests
import json
import urllib
import datetime
import csv
import base64
import arrow

from bs4 import BeautifulSoup

from .common import ApiException, ApiLoginException

class AndroidApi:
    BASE_URL = 'https://tdcservices.tandemdiabetes.com/'
    OAUTH_TOKEN_PATH = 'cloud/oauth2/token'
    OAUTH_SCOPES = 'cloud.account cloud.upload cloud.accepttcpp cloud.email cloud.password'

    # These credentials are found in source code
    ANDROID_API_USERNAME = base64.b64decode('QzIzMzFDRDYtRDQ1MC00OTVFLTlDMTktNjcyMTUyMzBDODVD').decode()
    ANDROID_API_PASSWORD = base64.b64decode('dHo0MzNLVzVRREM5VjdmIXo2QF4ybyZZNlNHR1lo').decode()

    # These tokens are separate from the "standard" tdcservices API
    accessToken = None
    accessTokenExpiresAt = None
    refreshToken = None
    refreshTokenExpiresAt = None
    userId = None
    patientObjectId = None

    def __init__(self, email, password):
        self.login(email, password)

    def login(self, email, password):
        r = requests.post(
            self.BASE_URL + self.OAUTH_TOKEN_PATH,
            {
                'username': email,
                'password': password,
                'grant_type': 'password',
                'scope': self.OAUTH_SCOPES
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=requests.auth.HTTPBasicAuth(self.ANDROID_API_USERNAME, self.ANDROID_API_PASSWORD)
        )

        if r.status_code != 200:
            raise ApiLoginException(r.status_code, 'Received HTTP %s during login: %s' % (r.status_code, r.text))

        j = r.json()
        if "user" not in j or not j["user"]:
            raise ApiException(r.status_code, 'No user details present in AndroidApi oauth response')

        self.accessToken = j["accessToken"]
        self.accessTokenExpiresAt = j["accessTokenExpiresAt"]
        self.refreshToken = j["refreshToken"]
        self.refreshTokenExpiresAt = j["refreshTokenExpiresAt"]
        self.userId = j["user"]["id"]
        self.patientObjectId = j["user"]["patientObjectId"]

    def needs_relogin(self):
        diff = (arrow.get(self.refreshTokenExpiresAt) - arrow.get())
        return (diff.seconds <= 5 * 60)

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token')
        return {'Authorization': 'Bearer %s' % self.accessToken}

    def get(self, endpoint, query={}, **kwargs):
        r = requests.get(self.BASE_URL + endpoint, query, headers=self.api_headers(), **kwargs)
        if r.status_code != 200:
            raise ApiException(r.status_code, "Internal API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    def post(self, endpoint, query={}, **kwargs):
        r = requests.post(self.BASE_URL + endpoint, query, headers=self.api_headers(), **kwargs)
        if r.status_code != 200:
            raise ApiException(r.status_code, "Internal API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    """
    Returns the most recent event ID that was uploaded for the given pump.
    {'maxPumpEventIndex': <integer>, 'processingStatus': 1}
    """
    def last_event_uploaded(self, pump_serial_number):
        return self.get('cloud/upload/getlasteventuploaded?sn=%d' % pump_serial_number)
