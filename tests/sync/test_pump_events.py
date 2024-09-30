#!/usr/bin/env python3

import json
import unittest
from typing import Dict
import copy

from tconnectsync.sync.pump_events import ns_write_pump_events

from ..nightscout_fake import NightscoutApi


def _stub_last_uploaded_entry(eventType, time_start=None, time_end=None):
    return None

class TestNsWritePumpEvents(unittest.TestCase):

    SITE_CHANGE_EVENT = {'time': '2024-02-04 16:27:50-05:00', 'event_type': 'Site/Cartridge Change'}
    SITE_CHANGE_NS = {'created_at': '2024-02-04 16:27:50-05:00', 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Site Change', 'notes': 'Site/Cartridge Change','reason': 'Site/Cartridge Change', 'pump_event_id': ''}
    def test_write_single_sitechange_event(self):
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = _stub_last_uploaded_entry
        ns_write_pump_events(nightscout, [
            self.SITE_CHANGE_EVENT
        ])

        self.assertDictEqual({
            'treatments': [
                self.SITE_CHANGE_NS
            ]
        }, dict(nightscout.uploaded_entries))

    EMPTY_CART_EVENT = {'time': '2024-05-14 09:01:59-04:00', 'event_type': 'Empty Cartridge/Pump Shutdown'}
    EMPTY_CART_NS = {'created_at': '2024-05-14 09:01:59-04:00', 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Basal Suspension', 'notes': 'Empty Cartridge/Pump Shutdown', 'reason': 'Empty Cartridge/Pump Shutdown', 'pump_event_id': ''}
    def test_write_single_emptycart_event(self):
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = _stub_last_uploaded_entry
        ns_write_pump_events(nightscout, [
            self.EMPTY_CART_EVENT
        ])

        self.assertDictEqual({
            'treatments': [
                self.EMPTY_CART_NS
            ]
        }, dict(nightscout.uploaded_entries))

    USER_SUSPENDED_EVENT = {'time': '2024-02-05 09:48:22-05:00', 'event_type': 'User Suspended'}
    USER_SUSPENDED_NS = {'created_at': '2024-02-05 09:48:22-05:00', 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Basal Suspension', 'notes': 'User Suspended', 'reason': 'User Suspended', 'pump_event_id': ''}
    def test_write_single_usersuspended_event(self):
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = _stub_last_uploaded_entry
        ns_write_pump_events(nightscout, [
            self.USER_SUSPENDED_EVENT
        ])

        self.assertDictEqual({
            'treatments': [
                self.USER_SUSPENDED_NS
            ]
        }, dict(nightscout.uploaded_entries))

    EXERCISE_EVENT = {'time': '2024-03-10 08:53:20-04:00', 'duration_mins': 269.3833333333333, 'event_type': 'Exercise'}
    EXERCISE_NS = {'created_at': '2024-03-10 08:53:20-04:00', 'duration': 269.3833333333333, 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Exercise', 'notes': 'Exercise', 'reason': 'Exercise', 'pump_event_id': ''}
    EXERCISE_EXTENDED_EVENT = {'time': '2024-03-10 08:53:20-04:00', 'duration_mins': 585.8833333333333, 'event_type': 'Exercise'}
    EXERCISE_EXTENDED_NS = {'created_at': '2024-03-10 08:53:20-04:00', 'duration': 585.8833333333333, 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Exercise', 'notes': 'Exercise', 'reason': 'Exercise', 'pump_event_id': ''}
    def test_write_exercise_events(self):
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = _stub_last_uploaded_entry
        ns_write_pump_events(nightscout, [
            self.EXERCISE_EVENT
        ])

        self.assertDictEqual({
            'treatments': [
                self.EXERCISE_NS
            ]
        }, dict(nightscout.uploaded_entries))

        _id = 'exercise_id'
        def _last_uploaded_entry(eventType, time_start=None, time_end=None):
            if eventType == 'Exercise':
                return {
                    '_id': _id,
                    **self.EXERCISE_NS
                }

        nightscout.last_uploaded_entry = _last_uploaded_entry

        ns_write_pump_events(nightscout, [
            self.EXERCISE_EXTENDED_EVENT
        ])

        self.assertListEqual([
            'treatments/%s' % _id
        ], nightscout.deleted_entries)

        self.assertDictEqual({
            'treatments': [
                self.EXERCISE_NS,
                self.EXERCISE_EXTENDED_NS
            ]
        }, dict(nightscout.uploaded_entries))

    SLEEP_EVENT = {'time': '2024-02-07 00:00:19-05:00', 'duration_mins': 13.916666666666666, 'event_type': 'Sleep'}
    SLEEP_NS = {'created_at': '2024-02-07 00:00:19-05:00', 'duration': 13.916666666666666, 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Sleep', 'notes': 'Sleep', 'reason': 'Sleep', 'pump_event_id': ''}
    SLEEP_EXTENDED_EVENT = {'time': '2024-02-07 00:00:19-05:00', 'duration_mins': 74.0, 'event_type': 'Sleep'}
    SLEEP_EXTENDED_NS = {'created_at': '2024-02-07 00:00:19-05:00', 'duration': 74.0, 'enteredBy': 'Pump (tconnectsync)', 'eventType': 'Sleep', 'notes': 'Sleep', 'reason': 'Sleep', 'pump_event_id': ''}
    def test_write_sleep_events(self):
        nightscout = NightscoutApi()
        nightscout.last_uploaded_entry = _stub_last_uploaded_entry
        ns_write_pump_events(nightscout, [
            self.SLEEP_EVENT
        ])

        self.assertDictEqual({
            'treatments': [
                self.SLEEP_NS
            ]
        }, dict(nightscout.uploaded_entries))

        _id = 'sleep_id'
        def _last_uploaded_entry(eventType, time_start=None, time_end=None):
            if eventType == 'Sleep':
                return {
                    '_id': _id,
                    **self.SLEEP_NS
                }

        nightscout.last_uploaded_entry = _last_uploaded_entry

        ns_write_pump_events(nightscout, [
            self.SLEEP_EXTENDED_EVENT
        ])

        self.assertListEqual([
            'treatments/%s' % _id
        ], nightscout.deleted_entries)

        self.assertDictEqual({
            'treatments': [
                self.SLEEP_NS,
                self.SLEEP_EXTENDED_NS
            ]
        }, dict(nightscout.uploaded_entries))


if __name__ == '__main__':
    unittest.main()