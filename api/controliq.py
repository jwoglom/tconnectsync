import requests
import urllib
import datetime
from bs4 import BeautifulSoup

from .common import parse_date, base_headers, ApiException

class ControlIQApi:
    BASE_URL = 'https://tdcservices.tandemdiabetes.com/tconnect/controliq/api/'
    LOGIN_URL = 'https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f'

    userGuid = None
    accessToken = None
    accessTokenExpiresAt = None

    def __init__(self, email, password):
        if not self.login(email, password):
            raise Exception('Unable to authenticate')

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
                return False

            fwd = s.post(urllib.parse.urljoin(self.LOGIN_URL, req.headers['Location']), cookies=req.cookies, headers=base_headers())
            if fwd.status_code != 200:
                return False

            self.userGuid = req.cookies['UserGUID']
            self.accessToken = req.cookies['accessToken']
            self.accessTokenExpiresAt = req.cookies['accessTokenExpiresAt']
            return True

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token provided')
        return {'Authorization': 'Bearer %s' % self.accessToken, **base_headers()}

    def get(self, endpoint, query):
        r = requests.get(self.BASE_URL + endpoint, query, headers=self.api_headers())
        if r.status_code != 200:
            raise ApiException(r.status_code, "ControlIQ API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    def therapy_timeline(self, start=None, end=None):
        startDate = parse_date(start)
        endDate = parse_date(end)

        return self.get('therapytimeline/users/%s' % (self.userGuid), {
            "startDate": startDate,
            "endDate": endDate
        })
