import requests
import json
import urllib
import datetime
import csv
from bs4 import BeautifulSoup

class TConnectApi:
    CONTROLIQ_BASE_URL = 'https://tdcservices.tandemdiabetes.com/tconnect/controliq/api/'
    WS2_BASE_URL = 'https://tconnectws2.tandemdiabetes.com/'
    LOGIN_URL = 'https://tconnect.tandemdiabetes.com/login.aspx?ReturnUrl=%2f'

    userGuid = None
    accessToken = None
    accessTokenExpiresAt = None

    def __init__(self, email, password):
        if not self.login(email, password):
            raise Exception('Unable to authenticate')

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

    def controliq_api(self, endpoint, query):
        r = requests.get(self.CONTROLIQ_BASE_URL + endpoint, query, headers=self.api_headers())
        if r.status_code != 200:
            raise ApiException(r.status_code, "ControlIQ API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.json()

    def ws2_api(self, endpoint, query):
        r = requests.get(self.WS2_BASE_URL + endpoint, query, headers=self.api_headers())
        if r.status_code != 200:
            raise ApiException(r.status_code, "WS2 API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.text

    def _parse_date(self, date):
        if type(date) == str:
            return date
        return (date or datetime.datetime.now()).strftime('%m-%d-%Y')

    def therapy_timeline(self, start=None, end=None):
        startDate = self._parse_date(start)
        endDate = self._parse_date(end)

        return self.controliq_api('therapytimeline/users/%s' % (self.userGuid), {
            "startDate": startDate,
            "endDate": endDate
        })

    def _split_empty_sections(self, text):
        sections = [[]]
        sectionIndex = 0
        for line in text.splitlines():
            if len(line.strip()) > 0:
                sections[sectionIndex].append(line)
            else:
                sections.append([])
                sectionIndex += 1

        return sections + [None] * (4 - len(sections))

    def _csv_to_dict(self, rawdata):
        data = []
        if not rawdata or len(rawdata) == 0:
            return data
        headers = rawdata[0].split(",")
        for row in csv.reader(rawdata[1:]):
            data.append({headers[i]: row[i] for i in range(len(row)) if i < len(headers)})

        return data


    def therapy_timeline_csv(self, start=None, end=None):
        startDate = self._parse_date(start)
        endDate = self._parse_date(end)

        req_text = self.ws2_api('therapytimeline2csv/%s/%s/%s' % (self.userGuid, startDate, endDate), {})

        sections = self._split_empty_sections(req_text)

        readingData = None
        iobData = None
        basalData = None
        bolusData = None

        for s in sections:
            if s and len(s) > 2:
                firstrow = s[1].replace('"', '').strip()
                if firstrow.startswith("t:slim X2 Insulin Pump"):
                    readingData = s
                elif firstrow.startswith("IOB"):
                    iobData = s
                elif firstrow.startswith("Basal"):
                    basalData = s
                elif firstrow.startswith("Bolus"):
                    bolusData = s


        return {
            "readingData": self._csv_to_dict(readingData),
            "iobData": self._csv_to_dict(iobData),
            "basalData": self._csv_to_dict(basalData),
            "bolusData": self._csv_to_dict(bolusData)
        }

class ApiException(Exception):
    def __init__(self, status_code, text, *args, **kwargs):
        self.status_code = status_code
        super().__init__(text, *args, **kwargs)
