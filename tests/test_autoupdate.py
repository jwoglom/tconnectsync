#!/usr/bin/env python3

import logging
import unittest
import datetime
import contextlib

from unittest.mock import patch

from tconnectsync.autoupdate import Autoupdate, AutoupdateFailureError, AutoupdateFailureWarning, AutoupdateNoEventIndexesDetectedError, AutoupdateNoIndexChangeWarning

from .api.fake import TConnectApi
from .nightscout_fake import NightscoutApi
from .secrets import build_secrets

logger = logging.getLogger(__name__)

def stub(*args, **kwargs):
    pass

@contextlib.contextmanager
def build_mock_logger():
    def fake_error(*args, **kwargs):
        logger.error(*args, **kwargs)
    
    def fake_warn(*args, **kwargs):
        logger.warning(*args, **kwargs)
        
    with patch("tconnectsync.autoupdate.logger.error") as mock_error, patch("tconnectsync.autoupdate.logger.warning") as mock_warn:
        mock_error.side_effect = fake_error
        mock_warn.side_effect = fake_warn
        yield (mock_error, mock_warn)

def num_instances_of(cls, m):
    return sum([isinstance(i[0][0], cls) for i in m.call_args_list])

class TestAutoupdate(unittest.TestCase):
    maxDiff = None

    # datetimes are unused
    start = datetime.datetime(2021, 4, 20, 12, 0)
    end = datetime.datetime(2021, 4, 21, 12, 0)

    # each time the returned function is called, it returns the next argument
    # until the end is reached, at which point it will repeat the last argument
    def fake_last_event_uploaded(self, *indexes):
        index = 0
        def fake(*args, **kwargs):
            nonlocal index
            if index < len(indexes):
                index += 1
            data = {'maxPumpEventIndex': indexes[index-1], 'processingStatus': 1}
            return data
        
        return fake

    # each time the returned function is called, it returns the next argument
    # until the end is reached, at which point it will repeat the last argument
    def fake_process_time_range(self, *returns):
        index = 0
        def fake(*args, **kwargs):
            nonlocal index
            if index < len(returns):
                index += 1
            return returns[index - 1]
        
        return fake
    
    """process_time_range should always be invoked the first time"""
    def test_process_time_range_called_on_start(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=1,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range:
            mock_process_time_range.return_value = 0

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 1)
            self.assertEqual(u.autoupdate_invocations, 1)
            self.assertEqual(u.last_event_index, 1)


    """process_time_range should never be called with pretend"""
    def test_process_time_range_never_called_with_pretend(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()


        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=1,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range:
            mock_process_time_range.return_value = 0

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=True)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 0)
            self.assertEqual(u.autoupdate_invocations, 1)
            self.assertEqual(u.last_event_index, 1)
    

    """
    If the event index increases without process_time_range detecting new data,
    AutoupdateFailureWarning should be raised.
    """
    def test_autoupdate_failure_warning_on_index_process_time_range_discrepancy(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1, 2)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=2,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0,
            TCONNECT_EMAIL="test@email.com",
            TCONNECT_PASSWORD="testpassword"
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(0, 0)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 2)
            self.assertEqual(u.autoupdate_invocations, 2)
            self.assertEqual(u.last_event_index, 2)

            self.assertEqual(num_instances_of(AutoupdateFailureWarning, mock_warn), 1)

    """
    On the first attempt, an AutoupdateFailureWarning should never be raised.
    """
    def test_autoupdate_no_failure_warning_on_index_process_time_range_discrepancy_first_attempt(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=1,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(0, 0)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 1)
            self.assertEqual(u.autoupdate_invocations, 1)
            self.assertEqual(u.last_event_index, 1)

            self.assertEqual(num_instances_of(AutoupdateFailureWarning, mock_warn), 0)


    """
    If the event index increases without process_time_range detecting new data
    for AUTOUPDATE_FAILURE_MINUTES, an AutoupdateFailureError should be raised.
    """
    def test_autoupdate_failure_error_on_index_process_time_range_discrepancy_for_failure_minutes(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1, 2)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=2,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0,
            AUTOUPDATE_FAILURE_MINUTES=0,
            AUTOUPDATE_RESTART_ON_FAILURE=False,
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(0, 0)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 2)
            self.assertEqual(u.autoupdate_invocations, 2)
            self.assertEqual(u.last_event_index, 2)

            self.assertEqual(num_instances_of(AutoupdateFailureError, mock_error), 1)
            
    """
    If the event index increases without process_time_range detecting new data
    for AUTOUPDATE_FAILURE_MINUTES, and AUTOUPDATE_RESTART_ON_FAILURE is true,
    then an AutoupdateFailureError should be raised AND 1 should be returned.
    """
    def test_autoupdate_failure_error_on_index_process_time_range_discrepancy_for_failure_minutes_performs_restart(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1, 2)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=3,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0,
            AUTOUPDATE_FAILURE_MINUTES=0,
            AUTOUPDATE_RESTART_ON_FAILURE=True,
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(0, 0)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 1)

            self.assertEqual(mock_process_time_range.call_count, 2)
            self.assertEqual(u.autoupdate_invocations, 1) # exits before invocations is incremented
            self.assertEqual(u.last_event_index, 1) # exits before changed to 2

            self.assertEqual(num_instances_of(AutoupdateFailureError, mock_error), 1)


    """Validate state after first successful update"""
    def test_state_after_first_successful_update(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=1,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range:
            mock_process_time_range.side_effect = self.fake_process_time_range(1)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 1)
            self.assertEqual(u.autoupdate_invocations, 1)
            self.assertEqual(u.last_event_index, 1)
            self.assertTrue(u.last_event_time == u.last_attempt_time == u.last_successful_process_time_range)
            self.assertEqual(len(u.time_diffs_between_updates), 0)

    """Validate sleep occurs for the given fixed length when set"""
    def test_sleep_for_fixed_length_when_set(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        sleep_length = 3 # sentinel
        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=1,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=sleep_length
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, patch("tconnectsync.autoupdate.time.sleep") as mock_sleep:
            mock_process_time_range.side_effect = self.fake_process_time_range(1)
            mock_sleep.side_effect = None

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(mock_process_time_range.call_count, 1)
            self.assertEqual(u.autoupdate_invocations, 1)
            self.assertEqual(u.last_event_index, 1)
            self.assertTrue(mock_sleep.called)
            self.assertEqual(mock_sleep.call_args[0], (sleep_length,))


    """
    If there is no event index update for AUTOUPDATE_NO_DATA_FAILURE_MINUTES, 
    then a AutoupdateNoEventIndexesDetectedError should be raised and
    a restart should be triggered with AUTOUPDATE_RESTART_ON_FAILURE.
    """
    def test_autoupdate_no_event_indexes_detected_error_on_no_index_change_less_than_three_iterations(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=100,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0.1,
            AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS=0.2,
            AUTOUPDATE_RESTART_ON_FAILURE=True,
            AUTOUPDATE_NO_DATA_FAILURE_MINUTES=1/600 # 0.1 second
        )

        # with more than 3 iterations, the sleep iteration will change

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(1, 0)

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 1)

            self.assertEqual(num_instances_of(AutoupdateNoEventIndexesDetectedError, mock_error), 1)


    """
    If there has been 3 failed attempts since the last time we found new data,
    we should sleep for AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS and
    a AutoupdateNoIndexChangeWarning should be logged.
    """
    def test_autoupdate_no_index_change_warning_on_unexpected_no_index_sleep(self):
        tconnect = TConnectApi()
        tconnect._android.last_event_uploaded = self.fake_last_event_uploaded(1)

        nightscout = NightscoutApi()

        secret = build_secrets(
            AUTOUPDATE_MAX_LOOP_INVOCATIONS=5,
            AUTOUPDATE_USE_FIXED_SLEEP=True,
            AUTOUPDATE_DEFAULT_SLEEP_SECONDS=0.1,
            AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS=0.2
        )

        with patch("tconnectsync.autoupdate.process_time_range") as mock_process_time_range, patch("tconnectsync.autoupdate.time.sleep") as mock_sleep, build_mock_logger() as (mock_error, mock_warn):
            mock_process_time_range.side_effect = self.fake_process_time_range(0)
            mock_sleep.side_effect = None

            u = Autoupdate(secret)
            ret = u.process(tconnect, nightscout, self.start, self.end, pretend=False)
            self.assertEqual(ret, 0)

            self.assertEqual(u.autoupdate_invocations, 5)
            self.assertEqual(u.last_event_index, 1)
            self.assertTrue(mock_sleep.called)
            self.assertEqual(len(mock_sleep.call_args_list), 5)
            self.assertEqual(mock_sleep.call_args_list[0][0], (0.1,))
            self.assertEqual(mock_sleep.call_args_list[1][0], (0.1,))
            self.assertEqual(mock_sleep.call_args_list[2][0], (0.1,))
            self.assertEqual(mock_sleep.call_args_list[3][0], (0.2,))
            self.assertEqual(mock_sleep.call_args_list[4][0], (0.2,))

            self.assertEqual(num_instances_of(AutoupdateNoIndexChangeWarning, mock_warn), 2)

