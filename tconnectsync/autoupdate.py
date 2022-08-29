import time
import logging
import datetime
import sys

from .process import process_time_range
from .features import DEFAULT_FEATURES
from . import secret

logger = logging.getLogger(__name__)

class Autoupdate:
    """Wrap access to secrets for easier testing."""
    def __init__(self, secret):
        self.secret = secret
        self.autoupdate_invocations = 0
        self.last_event_index = None
        self.last_event_time = None
        self.last_successful_process_time_range = None
        self.time_diffs_between_updates = []
        self.last_attempt_time = None
        self.time_diffs_between_attempts = []

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
            last_event = tconnect.android.last_event_uploaded(self.secret.PUMP_SERIAL_NUMBER)
            if not self.last_event_index or last_event['maxPumpEventIndex'] > self.last_event_index:
                logger.info('New reported t:connect data. (event index: %s last: %s)' % (last_event['maxPumpEventIndex'], self.last_event_index))

                if pretend:
                    logger.info('Would update now if not in pretend mode')
                else:
                    added = process_time_range(tconnect, nightscout, time_start, time_end, pretend, features=features)
                    logger.info('Added %d items from process_time_range' % added)
                    if added == 0:
                        # If we've been unable to find new events, but the last_event_index is increasing,
                        # suggesting there are more events being added, we might be in a bugged
                        # situation where we can't get any more data without restarting.
                        # We skip this check on the first process cycle, since we might
                        # just already be in sync with tconnect's pump data.
                        if self.last_event_index:

                            # Find the timestamp of the last time we've successfully obtained data, 
                            # or the time when the autoupdate run started, if we haven't at all.
                            last_action_or_start = self.last_successful_process_time_range
                            if not last_action_or_start:
                                last_action_or_start = self.autoupdate_start

                            # If it's been AUTOUPDATE_FAILURE_MINUTES in the state of not seeing
                            # event index changes reflected in the tconnect data we're pulling,
                            # raise an error and potentially restart.
                            # This is likely a tconnectsync problem, not a problem with the pump or app
                            # (we can see the indexes increasing, so we know something's happening!)
                            if (now - last_action_or_start) >= 60 * self.secret.AUTOUPDATE_FAILURE_MINUTES:
                                logger.error(AutoupdateFailureError(
                                        ("%s: An event index change was recorded, but no new data was found via the API. " % datetime.datetime.now()) +
                                        "The %s was %d minutes ago. This is a problem with tconnectsync." % 
                                        ("last processed event" if self.last_successful_process_time_range else "start of autoupdate", (now - last_action_or_start)//60)))

                                if self.secret.AUTOUPDATE_RESTART_ON_FAILURE:
                                    logger.error("Exiting with error code due to AUTOUPDATE_RESTART_ON_FAILURE")
                                    return 1
                            else:
                                logger.warning(AutoupdateFailureWarning(("%s: An event index change was recorded, but no new data was found via the API. " % datetime.datetime.now()) +
                                            "The %s was %d minutes ago. Resetting TConnectApi to attempt to solve this problem." % 
                                            ("last processed event" if self.last_successful_process_time_range else "start of autoupdate", (now - last_action_or_start)//60)))
                                
                                # As a stop-gap, try to re-initialize TConnectApi (triggering a re-login)
                                # Use __class__ instead of direct TConnectApi invocation to avoid initializing a real TConnectApi over a fake
                                tconnect = tconnect.__class__(self.secret.TCONNECT_EMAIL, self.secret.TCONNECT_PASSWORD)
                    else:
                        # Mark the last successful time we got data from tconnect
                        self.last_successful_process_time_range = now


                # Track the time it took to find a new event between runs,
                # but skip this calculation the first process cycle (since
                # we don't know at what exact point the event index changed)
                if self.last_event_index:
                    self.time_diffs_between_updates.append(now - self.last_event_time)
                    logger.debug('Updating tracking of time since last update: %s' % self.time_diffs_between_updates)

                # Mark the last event index uploaded from the pump and timestamp
                self.last_event_index = last_event['maxPumpEventIndex']
                self.last_event_time = now
                self.last_attempt_time = now
                self.time_diffs_between_attempts = []
            else:
                logger.info('No new reported t:connect data. (last event index: %s)' % last_event['maxPumpEventIndex'])

                # If we haven't seen the pump event index update in AUTOUPDATE_NO_DATA_FAILURE_MINUTES,
                # then trigger an error and potentially restart.
                # The most likely case here is that the pump isn't uploading right now.
                if self.last_event_time and (now - self.last_event_time) >= 60 * self.secret.AUTOUPDATE_NO_DATA_FAILURE_MINUTES:
                    logger.error(AutoupdateNoEventIndexesDetectedError(
                        "%s: No new data event indexes have been detected for %d minutes. " % (datetime.datetime.now(), (now - self.last_event_time)//60) +
                        "The t:connect app might no longer be functioning."))

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
                        "%s: No new data has been detected via the API for %d minutes. " % (datetime.datetime.now(), now - self.last_successful_process_time_range)//60 +
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
