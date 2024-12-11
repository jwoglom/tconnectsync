from ...features import DEFAULT_FEATURES
from .choose_device import ChooseDevice
from .process import ProcessTimeRange
from ... import secret

import datetime

def run_oneshot(tconnect, nightscout, pretend=False, features=DEFAULT_FEATURES, secret_arg=None, time_start=None, time_end=None):
    if not time_start and not time_end:
        time_end = datetime.datetime.now()
        time_start = time_end - datetime.timedelta(days=1)

    if not secret_arg:
        secret_arg = secret

    tconnectDevice = ChooseDevice(secret_arg, tconnect).choose()
    return ProcessTimeRange(tconnect, nightscout, tconnectDevice, pretend, secret_arg, features).process(time_start, time_end)
