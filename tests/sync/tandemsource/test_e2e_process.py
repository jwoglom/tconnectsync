#!/usr/bin/env python3
"""End-to-end integration tests for the Tandem Source -> Nightscout sync flow.

Drives the REAL ProcessTimeRange + process_* handlers and the REAL
TandemSourceApi / NightscoutApi clients, with HTTP mocked only at the transport
layer (requests / base_session). Tandem responses are a small, representative
slice of real captured pump-log events (verbatim, deviceAssignmentId redacted);
the tests assert the exact Nightscout API operations the flow produces.
"""

import hashlib
import json
import unittest

import arrow
import requests as real_requests
from types import SimpleNamespace
from unittest import mock

from tconnectsync.api.tandemsource import TandemSourceApi
from tconnectsync.nightscout import NightscoutApi
from tconnectsync.sync.tandemsource.choose_device import ChooseDevice
from tconnectsync.sync.tandemsource.process import ProcessTimeRange
from tconnectsync import features as F

NS_URL = 'http://ns.example/'
NS_SECRET = 'apisecret'
API_SECRET_HASH = hashlib.sha1(NS_SECRET.encode()).hexdigest()
TIME_START = arrow.get('2026-05-14')
TIME_END = arrow.get('2026-05-19')
FEATURES = [F.BASAL, F.BOLUS, F.CGM, F.PUMP_EVENTS]

# One real pump for device selection (deviceAssignmentId redacted).
PUMPER = {"pumps": [{"assignmentId": "e2e-device-assignment-id", "serialNumber": "1111111", "modelNumber": "0", "modelName": "Tandem Mobi\u2122 System", "softwareVersion": "1.0", "maxDateOfEvents": "2026-05-18T10:19:55", "availableDataRange": {"start": "2026-05-14T00:01:00", "end": "2026-05-18T10:19:55"}}]}

# Representative slice of real captured pump-log events (verbatim, redacted):
# 2 basal (279), a full standard bolus (64/65/66/20 + 55/280), 2 CGM (399),
# cartridge/cannula/tubing (33/61/63), a sleep start/stop pair (229), and a
# resume alarm (5, which must NOT produce a treatment).
PUMP_LOGS = {
    "events": [
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 279, "sequenceGroup": 0, "sequenceNumber": 441311, "pumpDateTime": "2026-05-14T00:01:00", "eventProperties": {"commandedRateSource": 3, "reservedA2": 3, "spareA3": 0, "commandedRate": 1279, "profileBasalRate": 1000, "algorithmRate": 1279, "tempRate": 65535}, "estimatedDateTime": "2026-05-14T00:01:00Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 441314, "pumpDateTime": "2026-05-14T00:01:31", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": -6, "algorithmState": 32, "rssi": -78, "currentGlucoseDisplayValue": 167, "egvTimeStamp": 579571288, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-14T00:01:31Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 279, "sequenceGroup": 0, "sequenceNumber": 441336, "pumpDateTime": "2026-05-14T00:06:00", "eventProperties": {"commandedRateSource": 3, "reservedA2": 3, "spareA3": 0, "commandedRate": 1000, "profileBasalRate": 1000, "algorithmRate": 1000, "tempRate": 65535}, "estimatedDateTime": "2026-05-14T00:06:00Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 399, "sequenceGroup": 0, "sequenceNumber": 441339, "pumpDateTime": "2026-05-14T00:06:31", "eventProperties": {"glucoseValueStatus": 0, "cgmDataType": [0], "rate": -13, "algorithmState": 32, "rssi": -79, "currentGlucoseDisplayValue": 149, "egvTimeStamp": 579571588, "egvInfoBitmask": [0, 5, 6, 7, 8, 11, 12], "interval": 0, "reservedD15": 0}, "estimatedDateTime": "2026-05-14T00:06:31Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 64, "sequenceGroup": 0, "sequenceNumber": 442680, "pumpDateTime": "2026-05-14T11:02:20", "eventProperties": {"bolusId": 1583, "bolusType": 3, "correctionBolusIncluded": 1, "carbAmount": 20, "bg": 116, "iob": 0, "carbRatio": 0}, "estimatedDateTime": "2026-05-14T11:02:20Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 65, "sequenceGroup": 0, "sequenceNumber": 442681, "pumpDateTime": "2026-05-14T11:02:20", "eventProperties": {"bolusId": 1583, "options": 4, "standardPercent": 100, "duration": 0, "spareB6": 0, "isf": 0, "targetBg": 0, "userOverride": 0, "declinedCorrection": 0, "selectedIob": 1}, "estimatedDateTime": "2026-05-14T11:02:20Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 66, "sequenceGroup": 0, "sequenceNumber": 442682, "pumpDateTime": "2026-05-14T11:02:20", "eventProperties": {"bolusId": 1583, "spareA2": 0, "foodBolusSize": 3.33, "correctionBolusSize": 0.2, "totalBolusSize": 3.53}, "estimatedDateTime": "2026-05-14T11:02:20Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 55, "sequenceGroup": 0, "sequenceNumber": 442689, "pumpDateTime": "2026-05-14T11:02:35", "eventProperties": {"bolusId": 1583, "selectedIob": 1, "spareA3": 0, "iob": 0, "bolusSize": 3.53}, "estimatedDateTime": "2026-05-14T11:02:35Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 280, "sequenceGroup": 0, "sequenceNumber": 442690, "pumpDateTime": "2026-05-14T11:02:35", "eventProperties": {"bolusId": 1583, "bolusDeliveryStatus": 1, "bolusType": [0, 3, 4], "bolusSource": 8, "remoteId": 47, "requestedNow": 3530, "requestedLater": 0, "correction": 200, "extendedDurationRequested": 0, "deliveredTotal": 0}, "estimatedDateTime": "2026-05-14T11:02:35Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 280, "sequenceGroup": 0, "sequenceNumber": 442698, "pumpDateTime": "2026-05-14T11:04:18", "eventProperties": {"bolusId": 1583, "bolusDeliveryStatus": 0, "bolusType": [0, 3, 4], "bolusSource": 8, "remoteId": 47, "requestedNow": 3530, "requestedLater": 0, "correction": 200, "extendedDurationRequested": 0, "deliveredTotal": 3530}, "estimatedDateTime": "2026-05-14T11:04:18Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 20, "sequenceGroup": 0, "sequenceNumber": 442700, "pumpDateTime": "2026-05-14T11:04:18", "eventProperties": {"completionStatus": 3, "bolusId": 1583, "iob": 3.53, "insulinDelivered": 3.53, "insulinRequested": 3.53}, "estimatedDateTime": "2026-05-14T11:04:18Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 33, "sequenceGroup": 0, "sequenceNumber": 448073, "pumpDateTime": "2026-05-15T23:50:59", "eventProperties": {"insulinVolume": 180, "v2Volume": 0}, "estimatedDateTime": "2026-05-15T23:50:59Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 63, "sequenceGroup": 0, "sequenceNumber": 448074, "pumpDateTime": "2026-05-15T23:50:59", "eventProperties": {"primeSize": -1, "completionStatus": 3, "position": 547509}, "estimatedDateTime": "2026-05-15T23:50:59Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 5, "sequenceGroup": 0, "sequenceNumber": 448136, "pumpDateTime": "2026-05-16T00:06:00", "eventProperties": {"alarmId": 18, "faultLocatorData": 8311, "param1": 5228339, "param2": 0}, "estimatedDateTime": "2026-05-16T00:06:00Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 61, "sequenceGroup": 0, "sequenceNumber": 448176, "pumpDateTime": "2026-05-16T00:14:09", "eventProperties": {"primeSize": 0.3, "completionStatus": 3, "infusionSetType": 0}, "estimatedDateTime": "2026-05-16T00:14:09Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 229, "sequenceGroup": 0, "sequenceNumber": 456855, "pumpDateTime": "2026-05-18T10:16:00", "eventProperties": {"currentUserMode": 1, "previousUserMode": 0, "requestedAction": 1, "spareA3": 0, "sleepStartedByGui": 1, "activeSleepSchedule": [0], "spareB6": 0, "exerciseStoppedByTimer": 0, "exerciseChoice": 0, "exerciseTime": 0, "eatingSoonStoppedByTimer": 0}, "estimatedDateTime": "2026-05-18T10:16:00Z"},
            {"deviceAssignmentId": "e2e-device-assignment-id", "eventCode": 229, "sequenceGroup": 0, "sequenceNumber": 456952, "pumpDateTime": "2026-05-18T10:19:55", "eventProperties": {"currentUserMode": 0, "previousUserMode": 1, "requestedAction": 2, "spareA3": 0, "sleepStartedByGui": 1, "activeSleepSchedule": [0], "spareB6": 0, "exerciseStoppedByTimer": 0, "exerciseChoice": 0, "exerciseTime": 0, "eatingSoonStoppedByTimer": 0}, "estimatedDateTime": "2026-05-18T10:19:55Z"},
        ],
    "clockChanges": [],
}

# Golden set of Nightscout write operations (entity, payload) the flow emits.
# NOTE: the last Temp Basal's long duration is the real "last basal in the
# window extends to the last event time" behavior with this sparse slice.
EXPECTED_WRITES = [
        ('treatments', {'eventType': 'Temp Basal', 'reason': 'Algorithm', 'duration': 5.0, 'absolute': 1.28, 'rate': 1.28, 'created_at': '2026-05-14 00:01:00-04:00', 'carbs': None, 'insulin': None, 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '441311'}),
        ('treatments', {'eventType': 'Temp Basal', 'reason': 'Algorithm', 'duration': 6373.916666666667, 'absolute': 1.0, 'rate': 1.0, 'created_at': '2026-05-14 00:06:00-04:00', 'carbs': None, 'insulin': None, 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '441336'}),
        ('entries', {'type': 'sgv', 'sgv': 167, 'date': 1778731288000, 'dateString': '2026-05-14T00:01:28-0400', 'device': 'Pump (tconnectsync)', 'pump_event_id': '441314'}),
        ('entries', {'type': 'sgv', 'sgv': 149, 'date': 1778731588000, 'dateString': '2026-05-14T00:06:28-0400', 'device': 'Pump (tconnectsync)', 'pump_event_id': '441339'}),
        ('treatments', {'eventType': 'Combo Bolus', 'created_at': '2026-05-14 11:04:18-04:00', 'carbs': 20, 'insulin': 3.53, 'notes': 'BLE Standard Bolus', 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '442700,442680,442681,442682', 'glucose': '116'}),
        ('treatments', {'eventType': 'Insulin Change', 'reason': 'Cartridge Filled (180u filled)', 'notes': 'Cartridge Filled (180u filled)', 'created_at': '2026-05-15 23:50:59-04:00', 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '448073'}),
        ('treatments', {'eventType': 'Site Change', 'reason': 'Cannula Filled (0.3u primed)', 'notes': 'Cannula Filled (0.3u primed)', 'created_at': '2026-05-16 00:14:09-04:00', 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '448176'}),
        ('treatments', {'eventType': 'Insulin Change', 'reason': 'Tubing Filled', 'notes': 'Tubing Filled', 'created_at': '2026-05-15 23:50:59-04:00', 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '448074'}),
        ('treatments', {'eventType': 'Sleep', 'reason': 'Sleep (Manual)', 'notes': 'Sleep (Manual)', 'duration': 3.9166666666666665, 'created_at': '2026-05-18 10:16:00-04:00', 'enteredBy': 'Pump (tconnectsync)', 'pump_event_id': '456855,456952'}),
    ]


class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = [] if data is None else data
        self.text = json.dumps(self._data)
    def json(self):
        return self._data


class FakeNightscout:
    """Records Nightscout HTTP operations; returns canned lookup results."""
    exceptions = real_requests.exceptions

    def __init__(self, lookup=None):
        self.calls = []          # (method, url, json, headers)
        self.lookup = lookup     # optional fn(is_entries)->dict for dedup tests

    def _entity(self, url):
        return url.split('/api/v1/')[-1].split('?')[0]

    def get(self, url, **kw):
        self.calls.append(('GET', url, kw.get('json'), kw.get('headers')))
        if self.lookup is None:
            return _Resp(200, [])
        return _Resp(200, [self.lookup('entries' in url)])

    def _write(self, method, url, **kw):
        self.calls.append((method, url, kw.get('json'), kw.get('headers')))
        return _Resp(200, {})
    def post(self, url, **kw): return self._write('POST', url, **kw)
    def put(self, url, **kw): return self._write('PUT', url, **kw)
    def delete(self, url, **kw): return self._write('DELETE', url, **kw)

    @property
    def writes(self):
        return [(self._entity(u), j) for m, u, j, h in self.calls if m != 'GET']
    @property
    def write_headers(self):
        return [h for m, u, j, h in self.calls if m != 'GET']
    @property
    def gets(self):
        return [c for c in self.calls if c[0] == 'GET']


class FakeTandemSession:
    def __init__(self, pump_logs):
        self.pump_logs = pump_logs
    def get(self, url, data=None, headers=None):
        if '/reports/bff/pumper/' in url:
            return _Resp(200, PUMPER)
        if '/reports/bff/pump-logs/' in url:
            return _Resp(200, self.pump_logs)
        return _Resp(404, {})


def _fake_login(self, email, password):
    # Skip the real OIDC dance; set the token/pumper fields the client needs.
    self.accessToken = 'fake-token'
    self.pumperId = 'pumper-1'
    self.accountId = 'account-1'
    self.accessTokenExpiresAt = arrow.get().shift(hours=1)
    return True


def run_flow(pretend=False, lookup=None, pump_logs=PUMP_LOGS):
    """Run get_pumper -> ChooseDevice -> ProcessTimeRange under mocked HTTP."""
    rec = FakeNightscout(lookup)
    secret = SimpleNamespace(PUMP_SERIAL_NUMBER='11111111', FETCH_ALL_EVENT_TYPES=False)
    with mock.patch.object(TandemSourceApi, 'login', _fake_login), \
         mock.patch('tconnectsync.api.tandemsource.base_session', lambda: FakeTandemSession(pump_logs)), \
         mock.patch('tconnectsync.nightscout.requests', rec):
        tsapi = TandemSourceApi('email', 'password', 'US')
        tconnect = SimpleNamespace(tandemsource=tsapi)
        nightscout = NightscoutApi(NS_URL, NS_SECRET)
        device = ChooseDevice(secret, tconnect).choose()
        ProcessTimeRange(tconnect, nightscout, device, pretend, secret, features=FEATURES).process(TIME_START, TIME_END)
    return rec


class TestE2EProcessFlow(unittest.TestCase):
    maxDiff = None

    def test_full_sync_posts_expected_nightscout_operations(self):
        rec = run_flow()
        self.assertEqual(rec.writes, EXPECTED_WRITES)

    def test_writes_send_api_secret_header(self):
        rec = run_flow()
        self.assertTrue(rec.write_headers)
        for headers in rec.write_headers:
            self.assertEqual(headers['api-secret'], API_SECRET_HASH)

    def test_resume_alarm_produces_no_treatment(self):
        # The slice contains a resume alarm (code 5, alarmId 18); it must not
        # produce any Nightscout treatment.
        rec = run_flow()
        event_types = [payload.get('eventType') for entity, payload in rec.writes]
        self.assertNotIn('Alarm', event_types)

    def test_dedup_skips_events_at_or_before_last_upload(self):
        # Every dedup lookup reports a last upload at 2026-05-17; only the later
        # sleep event (2026-05-18) should be synced.
        def lookup(is_entries):
            key = 'dateString' if is_entries else 'created_at'
            return {key: '2026-05-17T00:00:00-04:00'}
        rec = run_flow(lookup=lookup)
        self.assertEqual([e for e, j in rec.writes], ['treatments'])
        self.assertEqual(rec.writes[0][1]['eventType'], 'Sleep')

    def test_pretend_mode_issues_no_writes(self):
        rec = run_flow(pretend=True)
        self.assertEqual(rec.writes, [])
        self.assertTrue(rec.gets, "expected dedup lookups to still occur")

    def test_empty_window_produces_no_operations(self):
        rec = run_flow(pump_logs={"events": [], "clockChanges": []})
        self.assertEqual(rec.writes, [])
        self.assertEqual(rec.gets, [])


if __name__ == '__main__':
    unittest.main()
