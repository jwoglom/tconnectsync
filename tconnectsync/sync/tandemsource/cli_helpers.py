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
    pump_events_raw = tconnect.tandemsource.pump_events_raw(tconnectDevice['tconnectDeviceId'], time_start, time_end)
    pump_events_decoded = decode_raw_events(pump_events_raw)
    logger.info(f"Read {len(pump_events_decoded)} bytes (est. {len(pump_events_decoded)/EVENT_LEN} events)")

    return list(Events(pump_events_decoded))