from ...features import DEFAULT_FEATURES
from ...eventparser.generic import Events, decode_raw_events, EVENT_LEN
from .choose_device import ChooseDevice
from .process import ProcessTimeRange
from ...api import TConnectApi
from ... import secret

import datetime
import logging

logger = logging.getLogger(__name__)

def fetch_oneshot(username, password, time_start=None, time_end=None):
    tconnect = TConnectApi(username, password)
    if not time_start and not time_end:
        time_end = datetime.datetime.now()
        time_start = time_end - datetime.timedelta(days=1)

    tconnectDevice = ChooseDevice(secret, tconnect).choose()
    return tconnect.tandemsource.pump_events(tconnectDevice['tconnectDeviceId'], time_start, time_end, fetch_all_event_types=secret.FETCH_ALL_EVENT_TYPES)