import time
import logging

from .process import process_time_range
from .secret import (
    PUMP_SERIAL_NUMBER,
    AUTOUPDATE_DEFAULT_SLEEP_SECONDS,
    AUTOUPDATE_MAX_SLEEP_SECONDS,
    AUTOUPDATE_USE_FIXED_SLEEP
)

logger = logging.getLogger(__name__)

"""
Performs the auto-update functionality. Runs indefinitely in a loop
until stopped (ctrl+c).
"""
def process_auto_update(tconnect, nightscout, time_start, time_end, pretend):
    # Read from android api, find exact interval to cut down on API calls
    # Refresh API token. If failure, die, have wrapper script re-run.

    last_event_index = None
    last_event_time = None
    last_process_time_range = None
    time_diffs = []
    while True:
        last_event = tconnect.android.last_event_uploaded(PUMP_SERIAL_NUMBER)
        if not last_event_index or last_event['maxPumpEventIndex'] > last_event_index:
            now = time.time()
            logger.info('New reported t:connect data. (event index: %d last: %d)' % (last_event['maxPumpEventIndex'], last_event_index))

            if pretend:
                logger.info('Would update now if not in pretend mode')
            else:
                added = process_time_range(tconnect, nightscout, time_start, time_end, pretend)
                logger.info('Added %d items from process_time_range' % added)
                if len(added) == 0 and last_event_index:
                    logger.error('An event index change was recorded, but no new data was found via the API.')
                    logger.error('If this error reoccurs, try restarting tconnectsync.')

            if last_event_index:
                time_diffs.append(now - last_event_time)
                logger.debug('Updating tracking of time since last update: %s' % time_diffs)

            last_event_index = last_event['maxPumpEventIndex']
            last_event_time = now
        else:
            logger.info('No new reported t:connect data. (last event index: %d)' % last_event['maxPumpEventIndex'])

            if len(time_diffs) > 2:
                logger.info('Sleeping 60 seconds after unexpected no index change. (New data might be delayed.)')
                time.sleep(60)
                continue

        sleep_secs = AUTOUPDATE_DEFAULT_SLEEP_SECONDS
        if AUTOUPDATE_USE_FIXED_SLEEP != 1:
            if len(time_diffs) > 10:
                time_diffs = time_diffs[1:]

            if len(time_diffs) > 2:
                sleep_secs = sum(time_diffs) / len(time_diffs)

            if sleep_secs > AUTOUPDATE_MAX_SLEEP_SECONDS:
                sleep_secs = AUTOUPDATE_MAX_SLEEP_SECONDS

        # Sleep for a rolling average of time between updates
        logger.info('Sleeping for %d sec' % sleep_secs)
        time.sleep(sleep_secs)