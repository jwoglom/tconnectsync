import sys
import datetime
import arrow
import argparse
import logging
import pkg_resources
import typing

# Required for cryptography lib in python 3.7
if sys.version_info < (3, 8):
    import typing_extensions
    typing.Protocol = typing_extensions.Protocol

from .api import TConnectApi
from .process import process_time_range
from .autoupdate import Autoupdate
from .sync.tandemsource.autoupdate import TandemSourceAutoupdate
from .sync.tandemsource.choose_device import ChooseDevice as TandemSourceChooseDevice
from .sync.tandemsource.process import ProcessTimeRange as TandemSourceProcessTimeRange
from .check import check_login
from .nightscout import NightscoutApi
from .features import DEFAULT_FEATURES, ALL_FEATURES

try:
    from .secret import (
        TCONNECT_EMAIL,
        TCONNECT_PASSWORD,
        NS_URL,
        NS_SECRET,
        NS_SKIP_TLS_VERIFY,
        PUMP_SERIAL_NUMBER,
        NS_IGNORE_CONN_ERRORS
    )
    from . import secret
except Exception as e:
    print('Unable to read secrets from secret.py', e)
    sys.exit(1)


try:
    __version__ = pkg_resources.require("tconnectsync")[0].version
except Exception:
    __version__ = "UNKNOWN"

def parse_args(*args, **kwargs):
    parser = argparse.ArgumentParser(description="Syncs bolus, basal, and IOB data from Tandem Diabetes t:connect to Nightscout.", epilog="Version %s" % __version__)
    parser.add_argument('--version', action='version', version='tconnectsync %s' % __version__)
    parser.add_argument('--pretend', dest='pretend', action='store_const', const=True, default=False, help='Pretend mode: do not upload any data to Nightscout.')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_const', const=True, default=False, help='Verbose mode: show extra logging details')
    parser.add_argument('--start-date', dest='start_date', type=str, default=None, help='The oldest date to process data from. Must be specified with --end-date.')
    parser.add_argument('--end-date', dest='end_date', type=str, default=None, help='The newest date to process data until (inclusive). Must be specified with --start-date.')
    parser.add_argument('--days', dest='days', type=int, default=1, help='The number of days of t:connect data to read in. Cannot be used with --from-date and --until-date.')
    parser.add_argument('--auto-update', dest='auto_update', action='store_const', const=True, default=False, help='If set, continuously checks for updates from t:connect and syncs with Nightscout.')
    parser.add_argument('--check-login', dest='check_login', action='store_const', const=True, default=False, help='If set, checks that the provided t:connect credentials can be used to log in.')
    parser.add_argument('--features', dest='features', nargs='+', default=DEFAULT_FEATURES, choices=ALL_FEATURES, help='Specifies what data should be synchronized between tconnect and Nightscout.')
    parser.add_argument('--tandem-source', dest='tandem_source', action='store_const', const=True, default=False, help='FOR TESTING: Use Tandem Source')

    return parser.parse_args(*args, **kwargs)

def main(*args, **kwargs):
    args = parse_args(*args, **kwargs)

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        logging.root.debug("Set logging level to DEBUG")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

    if args.auto_update and (args.start_date or args.end_date):
        raise Exception('Auto-update cannot be used with start/end date')

    if args.start_date and args.end_date:
        time_start = arrow.get(args.start_date)
        time_end = arrow.get(args.end_date)
    else:
        time_end = datetime.datetime.now()
        time_start = time_end - datetime.timedelta(days=args.days)

    if time_end < time_start:
        raise Exception('time_start must be before time_end')


    if TCONNECT_EMAIL == 'email@email.com':
        logging.warn('NO USERNAME WAS PROVIDED. Ensure you have set TCONNECT_EMAIL appropriately.')
    if TCONNECT_PASSWORD == 'password':
        logging.warn('NO PASSWORD WAS PROVIDED. Ensure you have set TCONNECT_PASSWORD appropriately.')
    if NS_URL == 'https://yournightscouturl/':
        logging.warn('NO NIGHTSCOUT URL WAS PROVIDED. Ensure your have set NS_URL appropriately.')
    if PUMP_SERIAL_NUMBER == '11111111':
        if args.tandem_source:
            secret.PUMP_SERIAL_NUMBER = None
        else:
            logging.warn('NO PUMP SERIAL NUMBER WAS PROVIDED. Ensure you have set PUMP_SERIAL_NUMBER appropriately.')

    tconnect = TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)

    nightscout = NightscoutApi(NS_URL, NS_SECRET, skip_verify=NS_SKIP_TLS_VERIFY, ignore_conn_errors=NS_IGNORE_CONN_ERRORS)

    # NOT YET MIGRATED
    # if args.check_login:
    #     return check_login(tconnect, time_start, time_end)

    logging.warning("THIS VERSION OF TCONNECTSYNC READS DATA FROM TANDEM SOURCE, AND MAY CONTAIN BUGS!")
    logging.info("You may notice different behavior compared to older versions which utilized t:connect data sources.")
    logging.info("To report a bug or to get help, see https://github.com/jwoglom/tconnectsync/issues")

    logging.info("Enabled features: " + ", ".join(args.features))

    if args.check_login:
        args.pretend = True

    if args.auto_update:
        u = TandemSourceAutoupdate(secret)
        sys.exit(u.process(tconnect, nightscout, time_start, time_end, args.pretend, features=args.features))
    else:
        tconnectDevice = TandemSourceChooseDevice(secret, tconnect).choose()
        added, last_event_id = TandemSourceProcessTimeRange(tconnect, nightscout, tconnectDevice, pretend=args.pretend, secret=secret, features=args.features).process(time_start, time_end)

        # return exit code 0 if processed events
        sys.exit(0 if added>0 else 1)

