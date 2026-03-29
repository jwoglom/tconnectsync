#!/usr/bin/env python3

import unittest
import arrow

from tconnectsync.sync.tandemsource.process import ProcessTimeRange
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.generic import Event

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

    def pump_event_metadata(self):
        """Return empty metadata for testing"""
        return {}

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
            'tconnectDeviceId': 'test-device-123',
            'maxDateWithEvents': '2025-11-18T13:00:00-05:00'
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
        basal_2 = self.nightscout.uploaded_entries['treatments'][1]
        self.assertEqual(basal_2['eventType'], 'Temp Basal')
        self.assertEqual(basal_2['created_at'], '2025-11-18 13:17:40-05:00')
        self.assertAlmostEqual(basal_2['duration'], 11.33, places=2)

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
        self.assertEqual(basal_2['duration'], 5.0)

    def test_single_basal_event_duration(self):
        """Test that a single basal event gets a proper duration (min 5 min) even if it's the only event in the batch"""
        # Create one basal event
        basal_event = Event(BASAL_EVENT_1)  # 2025-11-18 13:12:40

        # Set up the fake API
        self.tconnect._tandemsource.events = [basal_event]

        # time_end is 13:22:40 (10 minutes after event)
        time_start = arrow.get('2025-11-18T13:00:00-05:00')
        time_end = arrow.get('2025-11-18T13:22:40-05:00')

        # Process the events
        self.process.process(time_start, time_end)

        # Verify that basal event was uploaded
        self.assertEqual(len(self.nightscout.uploaded_entries['treatments']), 1)
        basal = self.nightscout.uploaded_entries['treatments'][0]

        # Duration is 10.0 because it's max(actual_end_time - start, 5 min)
        # actual_end_time is time_end (13:22:40) because time_end > start
        self.assertEqual(basal['duration'], 10.0)


if __name__ == '__main__':
    unittest.main()
