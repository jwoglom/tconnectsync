import requests
import json
import urllib
import datetime
from bs4 import BeautifulSoup

class TConnectApi:
    API_BASE_URL = 'https://tdcservices.tandemdiabetes.com/tconnect/controliq/api/'
    LOGIN_URL = 'https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f'

    userGuid = None
    accessToken = None
    accessTokenExpiresAt = None

    def login(self, email, password):
        with requests.Session() as s:
            initial = s.get(self.LOGIN_URL)
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
            req = s.post(self.LOGIN_URL, data=data, headers={'Referer': self.LOGIN_URL}, allow_redirects=False)
            if req.status_code != 302:
                return False

            fwd = s.post(urllib.parse.urljoin(self.LOGIN_URL, req.headers['Location']), cookies=req.cookies)
            if fwd.status_code != 200:
                return False

            self.userGuid = req.cookies['UserGUID']
            self.accessToken = req.cookies['accessToken']
            self.accessTokenExpiresAt = req.cookies['accessTokenExpiresAt']
            return True

    def api_headers(self):
        if not self.accessToken:
            raise Exception('No access token provided')
        return {'Authorization': 'Bearer %s' % self.accessToken}

    def api(self, endpoint, query):
        r = requests.get(self.API_BASE_URL + endpoint, query, headers=self.api_headers())
        return r.json()

    def therapy_timeline(self, start=None, end=None):
        startDate = start if type(start) == str else (start or datetime.datetime.now()).strftime('%m-%d-%Y')
        endDate = end if type(end) == str else (end or datetime.datetime.now()).strftime('%m-%d-%Y')

        return self.api('therapytimeline/users/%s' % (self.userGuid), {
            "startDate": startDate,
            "endDate": endDate
        })

