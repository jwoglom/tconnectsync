#!/usr/bin/env python3

import unittest
import arrow
from unittest.mock import patch

from tconnectsync.api.tandemsource import TandemSourceApi
from tconnectsync.features import DEFAULT_FEATURES, DEVICE_STATUS
from tconnectsync.sync.tandemsource.process import ProcessTimeRange
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event, Events

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi
from ...secrets import build_secrets

# Raw event bytes for testing
# LidBasalDelivery (id=279) at 2025-11-18 13:12:40-05:00, rate=800 milliunits
BASAL_EVENT_1 = b'\x01\x17!\xa2\xeeH\x00\x01\x86\xa1\x00\x00\x00\x03\x03 \x03 \x00\x00\x03 \x00\x00\x00\x00'

# LidBasalDelivery (id=279) at 2025-11-18 13:17:40-05:00, rate=800 milliunits
BASAL_EVENT_2 = b'\x01\x17!\xa2\xeft\x00\x01\x86\xa2\x00\x00\x00\x03\x03 \x03 \x00\x00\x03 \x00\x00\x00\x00'

# LidCgmDataG7 (id=399) at 2025-11-19 03:00:00-05:00 (future timestamp for testing clock drift)
CGM_EVENT_FUTURE = b'\x01\x8f!\xa3\xb00\x00\x03\rA\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

# LidCgmDataG7 (id=399) at 2025-11-18 13:22:40-05:00 (normal timestamp)
CGM_EVENT_NORMAL = b'\x01\x8f!\xa2\xf0\xa0\x00\x03\rB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


class FakeTandemSourceApi:
    """Fake TandemSource API for testing"""
    def __init__(self):
        self.events = []

    def pump_events(self, device_id, time_start, time_end, fetch_all_event_types=False):
        return self.events

    def get_pumper(self):
        """Return empty pumper for testing"""
        return {'pumps': []}

    def needs_relogin(self):
        return False


class TestProcessTimeRangeBasalDuration(unittest.TestCase):
    """Test that basal duration calculation caps events_last_time at time_end"""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.tconnect._tandemsource = FakeTandemSourceApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        self.tconnectDevice = {
            'assignmentId': 'test-device-123',
            'maxDateOfEvents': '2025-11-18T13:00:00-05:00'
        }

        self.secret = build_secrets(
            FETCH_ALL_EVENT_TYPES=False
        )

        self.process = ProcessTimeRange(
            self.tconnect,
            self.nightscout,
            self.tconnectDevice,
            pretend=False,
            secret=self.secret
        )

    def test_basal_duration_capped_when_future_event_timestamp(self):
        """Test that basal duration is capped at time_end when last event is in the future"""

        # Create events from raw bytes
        basal_event_1 = Event(BASAL_EVENT_1)  # 2025-11-18 13:12:40-05:00
        basal_event_2 = Event(BASAL_EVENT_2)  # 2025-11-18 13:17:40-05:00
        future_cgm_event = Event(CGM_EVENT_FUTURE)  # 2025-11-19 03:00:00-05:00 (future)

        self.assertEqual(type(basal_event_1), eventtypes.LidBasalDelivery)
        self.assertEqual(type(basal_event_2), eventtypes.LidBasalDelivery)
        self.assertEqual(type(future_cgm_event), eventtypes.LidCgmDataG7)

        # Set up the fake API to return these events
        self.tconnect._tandemsource.events = [basal_event_1, basal_event_2, future_cgm_event]

        # time_end is "now" at 13:29:00
        time_start = arrow.get('2025-11-18T13:00:00-05:00')
        time_end = arrow.get('2025-11-18T13:29:00-05:00')

        # Process the events
        count, last_seqnum = self.process.process(time_start, time_end)

        # Verify that basal events were uploaded
        self.assertEqual(len(self.nightscout.uploaded_entries['treatments']), 2)

        # First basal: from 13:12:40 to 13:17:40 = 5 minutes
        basal_1 = self.nightscout.uploaded_entries['treatments'][0]
        self.assertEqual(basal_1['eventType'], 'Temp Basal')
        self.assertEqual(basal_1['created_at'], '2025-11-18 13:12:40-05:00')
        self.assertEqual(basal_1['duration'], 5.0)

        # Second basal: from 13:17:40 to time_end (13:29:00) = 11.333... minutes
        # NOT from 13:17:40 to future_cgm_event (03:00:00) which would be ~822 minutes
        basal_2 = self.nightscout.uploaded_entries['treatments'][1]
        self.assertEqual(basal_2['eventType'], 'Temp Basal')
        self.assertEqual(basal_2['created_at'], '2025-11-18 13:17:40-05:00')
        # Duration should be capped at time_end, not extended to future CGM event
        expected_duration = (time_end - arrow.get('2025-11-18T13:17:40-05:00')).seconds / 60
        self.assertAlmostEqual(basal_2['duration'], expected_duration, places=2)
        # Verify it's NOT the inflated duration to the future event
        self.assertLess(basal_2['duration'], 100)  # Should be ~11 min, not ~822 min

    def test_basal_duration_normal_when_all_events_in_past(self):
        """Test that basal duration uses events_last_time when it's <= time_end"""

        # Create events from raw bytes
        basal_event_1 = Event(BASAL_EVENT_1)  # 2025-11-18 13:12:40-05:00
        basal_event_2 = Event(BASAL_EVENT_2)  # 2025-11-18 13:17:40-05:00
        cgm_event = Event(CGM_EVENT_NORMAL)  # 2025-11-18 13:22:40-05:00 (normal)

        self.assertEqual(type(basal_event_1), eventtypes.LidBasalDelivery)
        self.assertEqual(type(basal_event_2), eventtypes.LidBasalDelivery)
        self.assertEqual(type(cgm_event), eventtypes.LidCgmDataG7)

        # Set up the fake API to return these events
        self.tconnect._tandemsource.events = [basal_event_1, basal_event_2, cgm_event]

        time_start = arrow.get('2025-11-18T13:00:00-05:00')
        time_end = arrow.get('2025-11-18T13:29:00-05:00')

        # Process the events
        count, last_seqnum = self.process.process(time_start, time_end)

        # Verify that basal events were uploaded
        self.assertEqual(len(self.nightscout.uploaded_entries['treatments']), 2)

        # First basal: from 13:12:40 to 13:17:40 = 5 minutes
        basal_1 = self.nightscout.uploaded_entries['treatments'][0]
        self.assertEqual(basal_1['duration'], 5.0)

        # Second basal: should use events_last_time (13:22:40) not time_end (13:29:00)
        # Duration: 13:17:40 to 13:22:40 = 5 minutes
        basal_2 = self.nightscout.uploaded_entries['treatments'][1]
        expected_duration = (arrow.get('2025-11-18T13:22:40-05:00') - arrow.get('2025-11-18T13:17:40-05:00')).seconds / 60
        self.assertAlmostEqual(basal_2['duration'], expected_duration, places=2)
        self.assertEqual(basal_2['duration'], 5.0)


BASAL_JSON_1 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 279, "sequenceGroup": 0, "sequenceNumber": 417004, "pumpDateTime": "2026-05-07T00:01:11", "eventProperties": {"commandedRateSource": 3, "reservedA2": 3, "spareA3": 0, "commandedRate": 1000, "profileBasalRate": 1000, "algorithmRate": 1000, "tempRate": 65535}, "estimatedDateTime": "2026-05-07T00:01:11Z"}
BASAL_JSON_2 = {"deviceAssignmentId": "00000000-0000-0000-0000-000000000000", "eventCode": 279, "sequenceGroup": 0, "sequenceNumber": 417029, "pumpDateTime": "2026-05-07T00:06:12", "eventProperties": {"commandedRateSource": 3, "reservedA2": 0, "spareA3": 0, "commandedRate": 1000, "profileBasalRate": 1000, "algorithmRate": 1000, "tempRate": 65535}, "estimatedDateTime": "2026-05-07T00:06:12Z"}


class TestProcessTimeRangeJsonBasal(unittest.TestCase):
    """Basal delivery events processed via real pump-logs JSON (production path)."""
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.tconnect._tandemsource = FakeTandemSourceApi()
        self.nightscout = NightscoutApi()
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        self.secret = build_secrets(
            FETCH_ALL_EVENT_TYPES=False
        )

        self.tconnectDevice = {
            'assignmentId': 'test',
            'maxDateOfEvents': '2026-05-07T00:20:00-04:00'
        }

        self.process = ProcessTimeRange(
            self.tconnect,
            self.nightscout,
            self.tconnectDevice,
            pretend=False,
            secret=self.secret
        )

        self.tconnect._tandemsource.events = list(Events([dict(BASAL_JSON_1), dict(BASAL_JSON_2)]))

    def test_basal_events_via_json(self):
        time_start = arrow.get('2026-05-07T00:00:00-04:00')
        time_end = arrow.get('2026-05-07T00:11:12-04:00')

        count, last_seqnum = self.process.process(time_start, time_end)

        self.assertEqual(count, 2)
        self.assertEqual(last_seqnum, 417029)

        treatments = self.nightscout.uploaded_entries['treatments']
        self.assertEqual(len(treatments), 2)

        self.assertDictEqual(treatments[0], {
            "eventType": "Temp Basal",
            "reason": "Algorithm",
            "duration": 5.016666666666667,
            "absolute": 1.0,
            "rate": 1.0,
            "created_at": "2026-05-07 00:01:11-04:00",
            "carbs": None,
            "insulin": None,
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": "417004"
        })

        self.assertDictEqual(treatments[1], {
            "eventType": "Temp Basal",
            "reason": "Algorithm",
            "duration": None,
            "absolute": 1.0,
            "rate": 1.0,
            "created_at": "2026-05-07 00:06:12-04:00",
            "carbs": None,
            "insulin": None,
            "enteredBy": "Pump (tconnectsync)",
            "pump_event_id": "417029"
        })


class TestProcessTimeRangePumpLogsQuery(unittest.TestCase):
    """FETCH_ALL_EVENT_TYPES or the DEVICE_STATUS feature must drop eventCodes
    from the pump-logs request entirely, rather than sending eventCodes=."""

    def _requested_endpoints(self, fetch_all_event_types, features):
        api = TandemSourceApi.__new__(TandemSourceApi)
        api.pumperId = "PUMPER123"
        api.needs_relogin = lambda: False
        tconnect = TConnectApi()
        tconnect._tandemsource = api
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = lambda *args, **kwargs: None

        process = ProcessTimeRange(
            tconnect,
            nightscout,
            {'assignmentId': 'test-device-123', 'maxDateOfEvents': '2025-11-18T13:00:00-05:00'},
            pretend=False,
            secret=build_secrets(FETCH_ALL_EVENT_TYPES=fetch_all_event_types),
            features=features,
        )

        with patch.object(TandemSourceApi, "get", return_value={"events": [], "clockChanges": []}) as mock_get:
            process.process(arrow.get('2025-11-18T00:00:00-05:00'), arrow.get('2025-11-18T23:00:00-05:00'))

        return [c.args[0] for c in mock_get.call_args_list
                if c.args[0].startswith('api/reports/bff/pump-logs/')]

    def test_device_status_feature_omits_event_ids(self):
        endpoints = self._requested_endpoints(False, DEFAULT_FEATURES + [DEVICE_STATUS])
        self.assertEqual(len(endpoints), 1)
        self.assertNotIn("eventCodes", endpoints[0])

    def test_fetch_all_event_types_secret_omits_event_ids(self):
        endpoints = self._requested_endpoints(True, DEFAULT_FEATURES)
        self.assertEqual(len(endpoints), 1)
        self.assertNotIn("eventCodes", endpoints[0])

    def test_default_sends_event_ids(self):
        endpoints = self._requested_endpoints(False, DEFAULT_FEATURES)
        self.assertEqual(len(endpoints), 1)
        self.assertIn("eventCodes=", endpoints[0])


if __name__ == '__main__':
    unittest.main()
