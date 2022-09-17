import requests
import datetime
import csv
import logging
import time
import json

from .common import base_session, parse_date, base_headers, ApiException

logger = logging.getLogger(__name__)

class WS2Api:
    BASE_URL = 'https://tconnectws2.tandemdiabetes.com/'

    MAX_RETRIES = 2
    SLEEP_SECONDS_INCREMENT = 60

    userGuid = None

    def __init__(self, userGuid):
        self.userGuid = userGuid
        self.session = base_session()

    def get(self, endpoint, **kwargs):
        r = self.session.get(self.BASE_URL + endpoint, headers=base_headers(), **kwargs)
        if r.status_code != 200:
            raise ApiException(r.status_code, "WS2 API HTTP %s response: %s" % (str(r.status_code), r.text))
        return r.text

    def get_jsonp(self, endpoint, **kwargs):
        r = self.session.get(self.BASE_URL + endpoint + '?callback=cb', headers=base_headers(), **kwargs)
        if r.status_code != 200:
            raise ApiException(r.status_code, "WS2 API HTTP %s response: %s" % (str(r.status_code), r.text))

        t = r.text.strip()
        if t.startswith('cb('):
            t = t[3:]
        if t.endswith(')'):
            t = t[:-1]

        return json.loads(t)

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


    """
    Returns information on therapy, displayed in the therapy timeline on the
    t:connect website.
    Contains BG reading (CGM), IOB, basal, and bolus data.
    
    Basal data does NOT appear for the specified time range if using Control-IQ.
    The ControlIQ API endpoints must be used for basal data instead.
    However, all other fields are still accessed via this endpoint.

    This has its own built-in retry logic because Tandem's frontend serving
    the API returns 500s when its backend times out.
    """
    def therapy_timeline_csv(self, start=None, end=None, tries=0):
        startDate = parse_date(start)
        endDate = parse_date(end)

        try:
            req_text = self.get('therapytimeline2csv/%s/%s/%s?format=csv' % (self.userGuid, startDate, endDate), timeout=10)
        except ApiException as e:
            # This seems to occur as some kind of soft rate-limit.
            logger.warning("Received ApiException in therapy_timeline_csv: (retry count %d) %s" % (tries, e))
            if e.status_code == 500:
                sleep_seconds = (tries+1) * self.SLEEP_SECONDS_INCREMENT
                logger.error("Retrying in %d seconds after HTTP 500 in therapy_timeline_csv (retry count %d): %s" % (sleep_seconds, tries, e))
                time.sleep(sleep_seconds)
                if tries < self.MAX_RETRIES:
                    return self.therapy_timeline_csv(start, end, tries+1)
            raise e

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
    
    """
    Returns information on basal suspension. The filterbasal option only returns site/cartridge changes.
    SuspendReason values are:
     - "site-cart"
     - "basal-profile"
     - "manual"
     - "previous"
     - "alarm"
    
    End-date inclusive: Returns data from 00:00 on start date to 23:59 on end date.

    {"BasalSuspension":[{"EventDateTime":"/Date(EPOCH_MS-0000)/", "SuspendReason": "reason"}]}
    """
    def basalsuspension(self, start=None, end=None, filterbasal=False):
        startDate = parse_date(start)
        endDate = parse_date(end)
        arg = "filterbasal/1" if filterbasal else ""

        return self.get_jsonp('basalsuspension/%s/%s/%s/%s' % (self.userGuid, startDate, endDate, arg), timeout=10)

    """
    Returns info on BasalIQ in JSONP format.
    """
    def basaliqtech(self, start=None, end=None):
        startDate = parse_date(start)
        endDate = parse_date(end)

        return self.get_jsonp('basaliqtech/%s/%s/%s' % (self.userGuid, startDate, endDate), timeout=10)