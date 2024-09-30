#!/usr/bin/env python3

import unittest
import datetime
import pprint
import copy
from unittest.mock import patch

from tconnectsync.process import process_time_range
from tconnectsync.parser.nightscout import EXERCISE_EVENTTYPE, IOB_ACTIVITYTYPE, SLEEP_EVENTTYPE, NightscoutEntry
from tconnectsync.features import BASAL, BOLUS, IOB, PROFILES, PUMP_EVENTS, PUMP_EVENTS_BASAL_SUSPENSION
from tconnectsync.domain.device_settings import Device
from tests.secrets import build_secrets
from tests.sync.test_profile import DEVICE_PROFILE_A, DEVICE_PROFILE_B, DEVICE_SETTINGS, NS_PROFILE_A, NS_PROFILE_B, build_ns_profile


from .api.fake import TConnectApi
from .nightscout_fake import NightscoutApi
from .sync.test_basal import TestBasalSync
from .sync.test_bolus import TestBolusSync
from .sync.test_iob import TestIOBSync
from .domain.test_therapy_event import BOLUS_FULL_EXAMPLES, TestCGMTherapyEvent

class TestProcessTimeRange(unittest.TestCase):
    maxDiff = None

    def stub_therapy_timeline(self, time_start, time_end):
        return copy.deepcopy(TestBasalSync.base)

    def stub_ciq_therapy_events(self, time_start, time_end):
        return {
            "event": []
        }

    def stub_therapy_timeline_csv(self, time_start, time_end):
        return {
            "readingData": [],
            "iobData": [],
            "basalData": [],
            "bolusData": []
        }

    def stub_ws2_basalsuspension(self, time_start, time_end):
        return {"BasalSuspension": []}

    def stub_last_uploaded_entry(self, event_type, **kwargs):
        return None

    def stub_last_uploaded_activity(self, activity_type, **kwargs):
        return None

    """No data in Nightscout. Uploads all basal data from tconnect."""
    def test_new_ciq_basal_data(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return TestBasalSync.get_example_ciq_basal_events()

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 4)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.basal(0.8, 20.35, "2021-03-16 00:00:00-04:00", reason="tempDelivery"),
                NightscoutEntry.basal(0.799, 5.0, "2021-03-16 00:20:21-04:00", reason="profileDelivery"),
                NightscoutEntry.basal(0.797, 5.0, "2021-03-16 00:25:21-04:00", reason="algorithmDelivery"),
                NightscoutEntry.basal(0, 2693/60, "2021-03-16 00:30:21-04:00", reason="algorithmDelivery (control-iq suspension)")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 4)

    """No data in Nightscout. Nothing should be updated in Nightscout without the BASAL feature."""
    def test_basal_data_not_updated_without_feature(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return TestBasalSync.get_example_ciq_basal_events()

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, IOB])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)

    """Two basal entries in Nightscout. Two new basal entries in tconnect."""
    def test_partial_ciq_basal_data(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return TestBasalSync.get_example_ciq_basal_events()

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        nightscout = NightscoutApi()

        def fake_last_uploaded_entry(event_type, **kwargs):
            if event_type == "Temp Basal":
                return {
                    "created_at": "2021-03-16 00:20:21-04:00",
                    "duration": 5
                }

        nightscout.last_uploaded_entry = fake_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 2)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.basal(0.797, 5.0, "2021-03-16 00:25:21-04:00", reason="algorithmDelivery"),
                NightscoutEntry.basal(0, 2693/60, "2021-03-16 00:30:21-04:00", reason="algorithmDelivery (control-iq suspension)")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 2)


    """
    Two basal entries in Nightscout, the latter which needs to be updated
    with a longer duration. Two entirely new entries in tconnect."""
    def test_with_updated_duration_ciq_basal_data(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return TestBasalSync.get_example_ciq_basal_events()

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        nightscout = NightscoutApi()

        def fake_last_uploaded_entry(event_type, **kwargs):
            if event_type == "Temp Basal":
                return {
                    "created_at": "2021-03-16 00:20:21-04:00",
                    "duration": 3,
                    "_id": "nightscout_id"
                }

        nightscout.last_uploaded_entry = fake_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 2)
        self.assertDictEqual(nightscout.uploaded_entries, {
            "treatments": [
                NightscoutEntry.basal(0.797, 5.0, "2021-03-16 00:25:21-04:00", reason="algorithmDelivery"),
                NightscoutEntry.basal(0, 2693/60, "2021-03-16 00:30:21-04:00", reason="algorithmDelivery (control-iq suspension)")
        ]})
        self.assertEqual(len(nightscout.put_entries["treatments"]), 1)
        self.assertDictEqual(dict(nightscout.put_entries), {
            "treatments": [
                {
                    "_id": "nightscout_id",
                    **NightscoutEntry.basal(0.799, 5.0, "2021-03-16 00:20:21-04:00", reason="profileDelivery")
                }
            ]
        })
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 3)

    """No data in Nightscout. Uploads all bolus data from tconnect via the WS2 API."""
    def test_new_ciq_bolus_data_from_ws2(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events

        bolusData = TestBolusSync.get_example_csv_bolus_events()
        def fake_therapy_timeline_csv(time_start, time_end):
            return {
                **self.stub_therapy_timeline_csv(time_start, time_end),
                "bolusData": bolusData,
            }

        tconnect.ws2.therapy_timeline_csv = fake_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL])

        pprint.pprint(nightscout.uploaded_entries)
        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), len(bolusData))
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.bolus(13.53, 75, "2021-04-01 12:58:26-04:00", notes="Standard/Correction"),
                NightscoutEntry.bolus(1.25, 0, "2021-04-01 23:23:17-04:00", notes="Standard (Override)"),
                NightscoutEntry.bolus(1.7, 0, "2021-04-02 01:00:47-04:00", notes="Automatic Bolus/Correction"),
                NightscoutEntry.bolus(1.82, 0, "2021-09-06 12:24:47-04:00", notes="Standard/Correction (Terminated by Alarm: requested 2.63 units)"),
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 4)

    """No data in Nightscout. Uploads all bolus data from tconnect via CIQ therapy_events."""
    def test_new_ciq_bolus_data_from_ciq_therapy_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2022, 8, 9, 12, 0)
        end = datetime.datetime(2021, 8, 10, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline

        def fake_ciq_therapy_events(time_start, time_end):
            return {
                "event": BOLUS_FULL_EXAMPLES
            }
        tconnect.controliq.therapy_events = fake_ciq_therapy_events

        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL])

        pprint.pprint(nightscout.uploaded_entries)
        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), len(BOLUS_FULL_EXAMPLES))
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                # BGs are excluded because BG is not enabled in features for this test
                NightscoutEntry.bolus(2.9, 0, "2022-07-21 11:55:24-04:00", notes="Automatic Bolus/Correction"),
                NightscoutEntry.bolus(4.17, 25, "2022-07-21 12:29:21-04:00", notes="Standard"),
                # NOTE: the extended bolus is 0.2+0.2 but we currently only surface standard
                # BUG: inconsistency: we use the completion timestamp as the event timestamp for standard boluses,
                # but the standard strand time for extended
                NightscoutEntry.bolus(0.2, 0, "2022-08-09 23:20:04-04:00", notes="Extended 50.00%/0.00 (Override) (Extended)"),
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 3)

    """No data in Nightscout. Nothing should be updated in Nightscout without the BOLUS feature."""
    def test_bolus_data_not_updated_without_feature(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline

        bolusData = TestBolusSync.get_example_csv_bolus_events()
        def fake_therapy_timeline_csv(time_start, time_end):
            return {
                **self.stub_therapy_timeline_csv(time_start, time_end),
                "bolusData": bolusData,
            }

        tconnect.ws2.therapy_timeline_csv = fake_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BASAL, IOB])

        pprint.pprint(nightscout.uploaded_entries)
        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)

    """No data in Nightscout. Uploads new iob reading from tconnect."""
    def test_new_ciq_iob_data(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events

        iobData = TestIOBSync.get_example_csv_iob_events()
        def fake_therapy_timeline_csv(time_start, time_end):
            return {
                **self.stub_therapy_timeline_csv(time_start, time_end),
                "iobData": iobData,
            }

        tconnect.ws2.therapy_timeline_csv = fake_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL, IOB])

        pprint.pprint(nightscout.uploaded_entries)
        self.assertEqual(len(nightscout.uploaded_entries["activity"]), 1)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "activity": [
                # the most recent IOB entry is added
                NightscoutEntry.iob(6.80, "2021-10-12 00:10:30-04:00")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 1)

    """No data in Nightscout. Nothing should be updated in Nightscout without the IOB feature."""
    def test_iob_data_not_updated_without_feature(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events

        iobData = TestIOBSync.get_example_csv_iob_events()
        def fake_therapy_timeline_csv(time_start, time_end):
            return {
                **self.stub_therapy_timeline_csv(time_start, time_end),
                "iobData": iobData,
            }

        tconnect.ws2.therapy_timeline_csv = fake_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BASAL, BOLUS])

        self.assertEqual(len(nightscout.uploaded_entries["activity"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)

    """Existing IOB in Nightscout. Uploads new iob reading and deletes old IOB."""
    def test_updates_ciq_iob_data(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 4, 20, 12, 0)
        end = datetime.datetime(2021, 4, 21, 12, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline

        iobData = TestIOBSync.get_example_csv_iob_events()
        iobData[0]["created_at"] = start
        iobData[0]["_id"] = "sentinel_existing_iob_id"

        def fake_therapy_timeline_csv(time_start, time_end):
            return {
                **self.stub_therapy_timeline_csv(time_start, time_end),
                "iobData": iobData,
            }

        tconnect.ws2.therapy_timeline_csv = fake_therapy_timeline_csv

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry

        def fake_last_uploaded_activity(activityType, **kwargs):
            if activityType == IOB_ACTIVITYTYPE:
                return iobData[0]
            return self.stub_last_uploaded_activity(activityType)

        nightscout.last_uploaded_activity = fake_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[IOB])

        pprint.pprint(nightscout.uploaded_entries)
        self.assertEqual(len(nightscout.uploaded_entries["activity"]), 1)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "activity": [
                # the most recent IOB entry is added
                NightscoutEntry.iob(6.80, "2021-10-12 00:10:30-04:00")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [
            "activity/sentinel_existing_iob_id"
        ])
        self.assertEqual(count, 1)

    """No pump activity events in Nightscout. New CIQ activity events."""
    def test_new_ciq_activity_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {
                **TestBasalSync.base,
                "events": [{
                    "duration": 1200,
                    "eventType": 2, # Exercise
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619901912 # 2021-05-01 13:45:12-04:00
                }, {
                    "duration": 30661,
                    "eventType": 1, # Sleep
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619992000 # 2021-05-02 14:46:40-04:00
                }]
            }

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv
        tconnect.ws2.basalsuspension = self.stub_ws2_basalsuspension

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PUMP_EVENTS])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 2)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.activity(created_at="2021-05-01 13:45:12-04:00", duration=20, reason="Exercise", event_type=EXERCISE_EVENTTYPE),
                NightscoutEntry.activity(created_at="2021-05-02 14:46:40-04:00", duration=30661/60, reason="Sleep", event_type=SLEEP_EVENTTYPE),
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 2)

    """No pump activity events in Nightscout. New CIQ activity events, but feature is disabled."""
    def test_no_ciq_activity_events_without_feature(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {
                **TestBasalSync.base,
                "events": [{
                    "duration": 1200,
                    "eventType": 2, # Exercise
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619901912 # 2021-05-01 13:45:12-04:00
                }, {
                    "duration": 30661,
                    "eventType": 1, # Sleep
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619992000 # 2021-05-02 14:46:40-04:00
                }]
            }

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.controliq.therapy_events = self.stub_ciq_therapy_events
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv
        tconnect.ws2.basalsuspension = self.stub_ws2_basalsuspension

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[BOLUS, BASAL, IOB])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)


    """
    Existing Sleep event in Nightscout with shorter duration than current, as well as a past Exercise event.
    Ensures that the old sleep event is deleted and a new one is created with the correct duration."""
    def test_existing_ciq_activity_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        def fake_therapy_timeline(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {
                **TestBasalSync.base,
                "events": [{
                    "duration": 1200,
                    "eventType": 2, # Exercise
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619901912 # 2021-05-01 13:45:12-04:00
                }, {
                    "duration": 4200, # Currently 60 mins (3600), changing to 70 mins (4200)
                    "eventType": 1, # Sleep
                    "continuation": None,
                    "timeZoneId": "America/Los_Angeles",
                    "x": 1619992000 # 2021-05-02 14:46:40-04:00
                }]
            }

        tconnect.controliq.therapy_timeline = fake_therapy_timeline
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv
        tconnect.ws2.basalsuspension = self.stub_ws2_basalsuspension

        nightscout = NightscoutApi()

        def fake_last_uploaded_entry(event_type, **kwargs):
            if event_type == "Sleep":
                return {
                    "created_at": "2021-05-02 14:46:40-04:00",
                    "duration": 60,
                    "_id": "old_sleep"
                }
            elif event_type == "Exercise":
                return {
                    "created_at": "2021-05-01 13:45:12-04:00",
                    "duration": 20,
                    "_id": "exercise"
                }
            return self.stub_last_uploaded_entry(**kwargs)

        nightscout.last_uploaded_entry = fake_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PUMP_EVENTS])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 1)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                # Already exists:
                # NightscoutEntry.activity(created_at="2021-05-01 13:45:12-04:00", duration=20, reason="Exercise", event_type=EXERCISE_EVENTTYPE),
                # Updated event duration:
                NightscoutEntry.activity(created_at="2021-05-02 14:46:40-04:00", duration=70, reason="Sleep", event_type=SLEEP_EVENTTYPE),
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertEqual(len(nightscout.deleted_entries), 1)
        self.assertListEqual(nightscout.deleted_entries, [
            "treatments/old_sleep"
        ])
        self.assertEqual(count, 1)

    """No pump activity events in Nightscout. New WS2 activity events."""
    def test_new_ws2_activity_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        def fake_basalsuspension(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {"BasalSuspension": [
                {
                    'EventDateTime': '/Date(1638663490000-0000)/',
                    'SuspendReason': 'site-cart'
                },
                {
                    'EventDateTime': '/Date(1637863616000-0000)/',
                    'SuspendReason': 'alarm'
                },
                {
                    'EventDateTime': '/Date(1638662852000-0000)/',
                    'SuspendReason': 'manual'
                }
            ]}

        tconnect.ws2.basalsuspension = fake_basalsuspension

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PUMP_EVENTS, PUMP_EVENTS_BASAL_SUSPENSION])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 3)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.sitechange(created_at="2021-12-04 16:18:10-05:00", reason="Site/Cartridge Change"),
                NightscoutEntry.basalsuspension(created_at="2021-11-25 10:06:56-05:00", reason="Empty Cartridge/Pump Shutdown"),
                NightscoutEntry.basalsuspension(created_at="2021-12-04 16:07:32-05:00", reason="User Suspended")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 3)

    """Existing pump activity events in Nightscout. New WS2 activity events. Only adds new events."""
    def test_existing_ws2_activity_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        def fake_basalsuspension(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {"BasalSuspension": [
                {
                    'EventDateTime': '/Date(1638663490000-0000)/',
                    'SuspendReason': 'site-cart'
                },
                {
                    'EventDateTime': '/Date(1637863616000-0000)/',
                    'SuspendReason': 'alarm'
                },
                {
                    'EventDateTime': '/Date(1638662852000-0000)/',
                    'SuspendReason': 'manual'
                },
                # This event is new:
                {
                    'EventDateTime': '/Date(1638672852000-0000)/',
                    'SuspendReason': 'manual'
                }
            ]}

        tconnect.ws2.basalsuspension = fake_basalsuspension

        nightscout = NightscoutApi()

        def fake_last_uploaded_entry(event_type, **kwargs):
            if event_type == "Site Change":
                return {
                    "created_at": "2021-12-04 16:18:10-05:00"
                }
            elif event_type == "Basal Suspension":
                return {
                    "created_at": "2021-12-04 16:07:32-05:00"
                }
            return self.stub_last_uploaded_entry(**kwargs)

        nightscout.last_uploaded_entry = fake_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PUMP_EVENTS, PUMP_EVENTS_BASAL_SUSPENSION])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 1)
        self.assertDictEqual(dict(nightscout.uploaded_entries), {
            "treatments": [
                NightscoutEntry.basalsuspension(created_at="2021-12-04 18:54:12-05:00", reason="User Suspended")
        ]})
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 1)

    """No pump activity events in nightscout. New WS2 activity events, but only of skipped types. None should be added."""
    def test_skipped_ws2_activity_events(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        tconnect.controliq.therapy_timeline = self.stub_therapy_timeline
        tconnect.ws2.therapy_timeline_csv = self.stub_therapy_timeline_csv

        def fake_basalsuspension(time_start, time_end):
            self.assertEqual(time_start, start)
            self.assertEqual(time_end, end)

            return {"BasalSuspension": [
                {
                    'EventDateTime': '/Date(1638659343000-0000)/',
                    'SuspendReason': 'basal-profile',
                },
                {
                    'Continuation': 'continuation',
                    'EventDateTime': '/Date(1638604800000-0000)/',
                    'SuspendReason': 'previous',
                },
                {
                    'EventDateTime': '/Date(1638659343000-0000)/',
                    'SuspendReason': 'basal-profile',
                }
            ]}

        tconnect.ws2.basalsuspension = fake_basalsuspension

        nightscout = NightscoutApi()

        nightscout.last_uploaded_entry = self.stub_last_uploaded_entry
        nightscout.last_uploaded_activity = self.stub_last_uploaded_activity

        count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PUMP_EVENTS])

        self.assertEqual(len(nightscout.uploaded_entries["treatments"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)

    """Profile present on pump and not in Nightscout with PROFILES feature enabled, adds profile."""
    def test_pump_profile_added(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        pump_guid = '00000000-0000-0000-0000-000000000001'
        serial_number = '12345'

        def fake_my_devices():
            return {
                serial_number: Device(
                    name='test',
                    model_number=serial_number,
                    status='OK',
                    guid=pump_guid)
            }
        tconnect.webui.my_devices = fake_my_devices

        def fake_device_settings_from_guid(guid):
            if guid != pump_guid:
                raise RuntimeError('invalid guid')
            return [DEVICE_PROFILE_A.activeProfile()], DEVICE_SETTINGS

        tconnect.webui.device_settings_from_guid = fake_device_settings_from_guid

        nightscout = NightscoutApi()

        def fake_current_profile(time_start=None, time_end=None):
            return build_ns_profile({}, '')

        nightscout.current_profile = fake_current_profile

        count = None
        with patch("tconnectsync.sync.profile._get_default_upload_mode") as mock_upload_mode, \
             patch("tconnectsync.sync.profile._get_default_serial_number") as mock_serial_number:
            mock_upload_mode.return_value = 'add'
            mock_serial_number.return_value = serial_number

            count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PROFILES])

        self.assertEqual(len(nightscout.uploaded_entries["profile"]), 1)
        self.assertDictEqual(nightscout.uploaded_entries["profile"][0]['store']['A'], NS_PROFILE_A)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 1)

    """Profile present on pump and in Nightscout with PROFILES feature enabled, does not add profile."""
    def test_pump_profile_not_updated(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        pump_guid = '00000000-0000-0000-0000-000000000001'
        serial_number = '12345'

        def fake_my_devices():
            return {
                serial_number: Device(
                    name='test',
                    model_number=serial_number,
                    status='OK',
                    guid=pump_guid)
            }
        tconnect.webui.my_devices = fake_my_devices

        def fake_device_settings_from_guid(guid):
            if guid != pump_guid:
                raise RuntimeError('invalid guid')
            return [DEVICE_PROFILE_A.activeProfile()], DEVICE_SETTINGS

        tconnect.webui.device_settings_from_guid = fake_device_settings_from_guid

        nightscout = NightscoutApi()

        def fake_current_profile(time_start=None, time_end=None):
            return build_ns_profile({'A': NS_PROFILE_A}, 'A')

        nightscout.current_profile = fake_current_profile

        count = None
        with patch("tconnectsync.sync.profile._get_default_upload_mode") as mock_upload_mode, \
             patch("tconnectsync.sync.profile._get_default_serial_number") as mock_serial_number:
            mock_upload_mode.return_value = 'add'
            mock_serial_number.return_value = serial_number

            count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PROFILES])

        self.assertEqual(len(nightscout.uploaded_entries["profile"]), 0)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 0)

    """Profile present on pump and in Nightscout with PROFILES feature enabled, with changes on pump, adds new profile object."""
    def test_pump_profile_new_entry_added(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        pump_guid = '00000000-0000-0000-0000-000000000001'
        serial_number = '12345'

        def fake_my_devices():
            return {
                serial_number: Device(
                    name='test',
                    model_number=serial_number,
                    status='OK',
                    guid=pump_guid)
            }
        tconnect.webui.my_devices = fake_my_devices

        def fake_device_settings_from_guid(guid):
            if guid != pump_guid:
                raise RuntimeError('invalid guid')
            return [DEVICE_PROFILE_A, DEVICE_PROFILE_B.activeProfile()], DEVICE_SETTINGS

        tconnect.webui.device_settings_from_guid = fake_device_settings_from_guid

        nightscout = NightscoutApi()

        def fake_current_profile(time_start=None, time_end=None):
            return build_ns_profile({'A': NS_PROFILE_A}, 'A')

        nightscout.current_profile = fake_current_profile

        count = None
        with patch("tconnectsync.sync.profile._get_default_upload_mode") as mock_upload_mode, \
             patch("tconnectsync.sync.profile._get_default_serial_number") as mock_serial_number:
            mock_upload_mode.return_value = 'add'
            mock_serial_number.return_value = serial_number

            count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PROFILES])

        self.assertEqual(len(nightscout.uploaded_entries["profile"]), 1)
        self.assertEqual(len(nightscout.uploaded_entries["profile"][0]['store']), 2)
        self.assertDictEqual(nightscout.uploaded_entries["profile"][0]['store']['A'], NS_PROFILE_A)
        self.assertDictEqual(nightscout.uploaded_entries["profile"][0]['store']['B'], NS_PROFILE_B)
        self.assertDictEqual(nightscout.put_entries, {})
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 1)

    """
    Profile present on pump and in Nightscout with PROFILES feature enabled, with changes on pump,
    replaces existing profile object with NIGHTSCOUT_PROFILE_UPLOAD_MODE=replace.
    """
    def test_pump_profile_new_entry_replaced(self):
        tconnect = TConnectApi()

        # datetimes are unused by the API fake
        start = datetime.datetime(2021, 5, 1, 0, 0)
        end = datetime.datetime(2021, 5, 3, 0, 0)

        pump_guid = '00000000-0000-0000-0000-000000000001'
        serial_number = '12345'

        def fake_my_devices():
            return {
                serial_number: Device(
                    name='test',
                    model_number=serial_number,
                    status='OK',
                    guid=pump_guid)
            }
        tconnect.webui.my_devices = fake_my_devices

        def fake_device_settings_from_guid(guid):
            if guid != pump_guid:
                raise RuntimeError('invalid guid')
            return [DEVICE_PROFILE_A, DEVICE_PROFILE_B.activeProfile()], DEVICE_SETTINGS

        tconnect.webui.device_settings_from_guid = fake_device_settings_from_guid

        nightscout = NightscoutApi()

        def fake_current_profile(time_start=None, time_end=None):
            return build_ns_profile({'A': NS_PROFILE_A}, 'A')

        nightscout.current_profile = fake_current_profile

        count = None
        with patch("tconnectsync.sync.profile._get_default_upload_mode") as mock_upload_mode, \
             patch("tconnectsync.sync.profile._get_default_serial_number") as mock_serial_number:
            mock_upload_mode.return_value = 'replace'
            mock_serial_number.return_value = serial_number

            count = process_time_range(tconnect, nightscout, start, end, pretend=False, features=[PROFILES])

        self.assertDictEqual(nightscout.uploaded_entries, {})
        self.assertEqual(len(nightscout.put_entries["profile"]), 1)
        self.assertEqual(len(nightscout.put_entries["profile"][0]['store']), 2)
        self.assertDictEqual(nightscout.put_entries["profile"][0]['store']['A'], NS_PROFILE_A)
        self.assertDictEqual(nightscout.put_entries["profile"][0]['store']['B'], NS_PROFILE_B)
        self.assertListEqual(nightscout.deleted_entries, [])
        self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main()