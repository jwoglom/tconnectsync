import requests
import urllib
import datetime
import arrow
import time

from bs4 import BeautifulSoup

from .common import parse_date, base_headers, ApiException, ApiLoginException

class ControlIQApi:
    BASE_URL = 'https://tdcservices.tandemdiabetes.com/tconnect/controliq/api/'
    LOGIN_URL = 'https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f'

    userGuid = None
    accessToken = None
    accessTokenExpiresAt = None

    def __init__(self, email, password):
        self.login(email, password)
        self._email = email
        self._password = password

    def login(self, email, password):
        with requests.Session() as s:
            initial = s.get(self.LOGIN_URL, headers=base_headers())
            soup = BeautifulSoup(initial.content, features='lxml')
            data = {
                "__LASTFOCUS": "",
                "__EVENTTARGET": "ctl00$ContentBody$LoginControl$linkLogin",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": soup.select_one("#__VIEWSTATE")["value"],
                "__VIEWSTATEGENERATOR": soup.select_one("#__VIEWSTATEGENERATOR")["value"],
                "__EVENTVALIDATION": soup.select_one("#__EVENTVALIDATION")["value"],
                "ctl00$ContentBody$LoginControl$txtLoginEmailAddress": email,
                "txtLoginEmailAddress_ClientState": '{"enabled":true,"emptyMessage":"","validationText":"%s","valueAsString":"%s","lastSetTextBoxValue":"%s"}' % (email, email, email),
                "ctl00$ContentBody$LoginControl$txtLoginPassword": password,
                "txtLoginPassword_ClientState": '{"enabled":true,"emptyMessage":"","validationText":"%s","valueAsString":"%s","lastSetTextBoxValue":"%s"}' % (password, password, password)
            }
            req = s.post(self.LOGIN_URL, data=data, headers={'Referer': self.LOGIN_URL, **base_headers()}, allow_redirects=False)
            if req.status_code != 302:
                raise ApiLoginException(req.status_code, 'Error logging in to t:connect. Check your login credentials.')


            fwd = s.post(urllib.parse.urljoin(self.LOGIN_URL, req.headers['Location']), cookies=req.cookies, headers=base_headers())
            if fwd.status_code != 200:
                raise ApiException(fwd.status_code, 'Error retrieving t:connect login cookies.')

            self.userGuid = req.cookies['UserGUID']
            self.accessToken = req.cookies['accessToken']
            self.accessTokenExpiresAt = req.cookies['accessTokenExpiresAt']
            return True

    def needs_relogin(self):
        diff = (arrow.get(self.accessTokenExpiresAt) - arrow.get())
        return (diff.seconds <= 5 * 60)

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token provided')
        return {'Authorization': 'Bearer %s' % self.accessToken, **base_headers()}

    def _get(self, endpoint, query):
        r = requests.get(self.BASE_URL + endpoint, query, headers=self.api_headers())

        if r.status_code != 200:
            raise ApiException(r.status_code, "ControlIQ API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()


    def get(self, endpoint, query, tries=0):
        try:
            return self._get(endpoint, query)
        except ApiException as e:
            if tries > 0:
                raise ApiException(e.status_code, "ControlIQ API HTTP %d on retry #%d: %s", e.status_code, tries, e)

            # Trigger automatic re-login, and try again once
            if e.status_code == 401:
                self.accessTokenExpiresAt = time.time()
                self.login(self._email, self._password)

                return self.get(endpoint, query, tries=tries+1)

            if e.status_code == 500:
                return self.get(endpoint, query, tries=tries+1)

            raise e

    """
    Returns detailed basal event information and reasons for delivery suspension.
    """
    def therapy_timeline(self, start=None, end=None):
        startDate = parse_date(start)
        endDate = parse_date(end)

        return self.get('therapytimeline/users/%s' % (self.userGuid), {
            "startDate": startDate,
            "endDate": endDate
        })

    """
    Returns a summary of pump and cgm activity.
    {'averageReading': <integer>, 'timeInUseMinutes': <integer>, 'controlIqSetToOffMinutes': <integer>,
    'cgmInactiveMinutes': <integer>, 'pumpInactiveMinutes': <integer>, 'averageDailySleepMinutes': <integer>,
    'weeklyExerciseEvents': <integer>, 'timeInUsePercent': <integer>, 'controlIqOffPercent': <integer>,
    'cgmInactivePercent': <integer>, 'pumpInactivePercent': <integer>, 'totalDays': <integer>}
    """
    def dashboard_summary(self, start, end):
        startDate = parse_date(start)
        endDate = parse_date(end)

        return self.get('summary/users/%s' % (self.userGuid), {
            "startDate": startDate,
            "endDate": endDate
        })
