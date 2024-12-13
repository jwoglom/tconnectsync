import time
import logging
import datetime
import sys
import arrow

from ...features import DEFAULT_FEATURES
from .process import ProcessTimeRange
from .choose_device import ChooseDevice

logger = logging.getLogger(__name__)

class TandemSourceAutoupdate:
    """Wrap access to secrets for easier testing."""
    def __init__(self, secret):
        self.secret = secret
        self.autoupdate_invocations = 0
        self.last_max_date_with_events = None
        self.last_event_time = 0
        self.last_attempt_time = 0
        self.last_event_seqnum = None
        self.time_diffs_between_attempts = []
        self.time_diffs_between_updates = []

    """
    Performs the auto-update functionality. Runs indefinitely in a loop
    until stopped (ctrl+c), or a maximum of AUTOUPDATE_MAX_LOOP_INVOCATIONS times.
    Stops if AUTOUPDATE_RESTART_ON_FAILURE is set and an error occurs.
    """
    def process(self, tconnect, nightscout, time_start, time_end, pretend, features=None):
        if features is None:
            features = DEFAULT_FEATURES

        # Read from android api, find exact interval to cut down on API calls
        # Refresh API token. If failure, die, have wrapper script re-run.

        self.autoupdate_start = time.time()

        while True:
            logger.debug("autoupdate loop")
            now = time.time()

            tconnectDevice = ChooseDevice(self.secret, tconnect).choose()

            event_seqnum = None
            cur_max_date_with_events = arrow.get(tconnectDevice['maxDateWithEvents']).float_timestamp
            if not self.last_max_date_with_events or cur_max_date_with_events > self.last_max_date_with_events:
                logger.info('New reported tandemsource data. (cur_max_date: %s last_max_date: %s)' % (cur_max_date_with_events, self.last_max_date_with_events))

                if pretend:
                    logger.info('Would update now if not in pretend mode')
                else:
                    added, event_seqnum = ProcessTimeRange(tconnect, nightscout, tconnectDevice, pretend, self.secret, features=features).process(time_start, time_end)
                    logger.info('Added %d items from ProcessTimeRange' % added)
                    self.last_successful_process_time_range = now

                # Track the time it took to find a new event between runs,
                # but skip this calculation the first process cycle (since
                # we don't know at what exact point the event index changed)
                if self.last_event_seqnum:
                    self.time_diffs_between_updates.append(now - self.last_max_date_with_events)
                    logger.debug('Updating tracking of time since last update: %s' % self.time_diffs_between_updates)

                # Mark the last event index uploaded from the pump and timestamp
                if event_seqnum:
                    self.last_event_seqnum = event_seqnum
                    self.last_event_time = now
                self.last_max_date_with_events = cur_max_date_with_events
                self.last_attempt_time = now
                self.time_diffs_between_attempts = []
            else:
                logger.info('No new reported tandemsource data. cur_max_date: %s (%dm ago) last_event_time: %s (%dm ago)' % (
                    arrow.get(cur_max_date_with_events) if cur_max_date_with_events else None,
                    (now - cur_max_date_with_events)//60 if cur_max_date_with_events else None,
                    arrow.get(self.last_event_time) if self.last_event_time else None,
                    (now - self.last_event_time)//60 if self.last_event_time else None
                ))

                # If we haven't seen the pump event index update in AUTOUPDATE_NO_DATA_FAILURE_MINUTES,
                # then trigger an error and potentially restart.
                # The most likely case here is that the pump isn't uploading right now.
                if self.last_event_time and (now - self.last_event_time) >= 60 * self.secret.AUTOUPDATE_NO_DATA_FAILURE_MINUTES:
                    logger.error(AutoupdateNoEventIndexesDetectedError(
                        "%s: No new data event indexes have been detected for %d minutes. " % (datetime.datetime.now(), (now - self.last_event_time)//60) +
                        "New data might not be uploading."))

                    # TODO: restarting doesn't really help anything here.
                    # Should we notify the user?
                    if self.secret.AUTOUPDATE_RESTART_ON_FAILURE:
                        logger.error("Exiting with error code due to AUTOUPDATE_RESTART_ON_FAILURE")
                        return 1

                # Similarly, if we HAVE seen pump event indexes update but have not successfully
                # found any associated data updates from the tconnect API for AUTOUPDATE_NO_DATA_FAILURE_MINUTES,
                # trigger an error and potentially restart. This could either be a tconnectsync problem,
                # where we can see the indexes increasing, but it takes us until a period of no index
                # update to reach our AUTOUPDATE_FAILURE_MINUTES threshold; or, a side effect of the
                # above no indexes warning.
                elif self.last_successful_process_time_range and (now - self.last_successful_process_time_range) >= 60 * self.secret.AUTOUPDATE_FAILURE_MINUTES:
                    logger.error(AutoupdateNoNewDataDetectedError(
                        "%s: No new data has been detected via the API for %d minutes (last: %s). " % (datetime.datetime.now(), (now - self.last_successful_process_time_range)//60, self.last_successful_process_time_range) +
                        "tconnectsync might not be functioning properly."))

                    if self.secret.AUTOUPDATE_RESTART_ON_FAILURE:
                        logger.error("%s: Exiting with error code due to AUTOUPDATE_RESTART_ON_FAILURE" % datetime.datetime.now())
                        return 1

                # Track how long we've been retrying
                if self.last_attempt_time:
                    self.time_diffs_between_attempts.append(now - self.last_attempt_time)

                self.last_attempt_time = now

                # If it's been 3 loops since the last time we found new data,
                # then we're not in sync with the rate at which pump data is being
                # uploaded, so
                if len(self.time_diffs_between_attempts) >= 3:
                    # The pump hasn't sent us data that, based on previous cadence, we were expecting
                    logger.warning(AutoupdateNoIndexChangeWarning("Sleeping %d seconds after unexpected no index change based on previous cadence. (New data might be delayed.)" %
                        int(self.secret.AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS)))

                    logger.debug("Last event time: %s, time diffs between attempts: %s" % (self.last_event_time, self.time_diffs_between_attempts))

                    time.sleep(self.secret.AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS)

                    # Since we bail early, update the invocations count and potentially exit after sleeping.
                    self.autoupdate_invocations += 1
                    if self.secret.AUTOUPDATE_MAX_LOOP_INVOCATIONS > 0 and self.autoupdate_invocations >= self.secret.AUTOUPDATE_MAX_LOOP_INVOCATIONS:
                        return 0

                    continue

            sleep_secs = self.secret.AUTOUPDATE_DEFAULT_SLEEP_SECONDS

            # Sleep for a rolling average of time between updates
            if self.secret.AUTOUPDATE_USE_FIXED_SLEEP != 1:
                logger.debug("Time diffs between updates: %s" % self.time_diffs_between_updates)

                # Only keep the 10 latest time diffs
                if len(self.time_diffs_between_updates) > 10:
                    self.time_diffs_between_updates = self.time_diffs_between_updates[1:]

                # If we have less than 3 data points,
                if len(self.time_diffs_between_updates) > 2:
                    sleep_secs = sum(self.time_diffs_between_updates) / len(self.time_diffs_between_updates)

                # At minimum, update every AUTOUPDATE_MAX_SLEEP_SECONDS regardless
                # of how often we're seeing new data appear
                if sleep_secs > self.secret.AUTOUPDATE_MAX_SLEEP_SECONDS:
                    sleep_secs = self.secret.AUTOUPDATE_MAX_SLEEP_SECONDS

            logger.info('Sleeping for %0.01f sec' % sleep_secs)
            time.sleep(sleep_secs)

            self.autoupdate_invocations += 1
            if self.secret.AUTOUPDATE_MAX_LOOP_INVOCATIONS > 0 and self.autoupdate_invocations >= self.secret.AUTOUPDATE_MAX_LOOP_INVOCATIONS:
                return 0


class AutoupdateError(RuntimeError):
    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, super().__str__())

class AutoupdateWarning(RuntimeWarning):
    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, super().__str__())
class AutoupdateFailureError(AutoupdateError):
    pass

class AutoupdateFailureWarning(AutoupdateWarning):
    pass

class AutoupdateNoEventIndexesDetectedError(AutoupdateError):
    pass

class AutoupdateNoNewDataDetectedError(AutoupdateError):
    pass

class AutoupdateNoIndexChangeWarning(AutoupdateWarning):
    pass