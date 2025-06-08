import os, sys, pathlib
from dotenv import dotenv_values

cwd_path = os.path.join(os.getcwd(), '.env')
global_path = os.path.join(pathlib.Path.home(), '.config/tconnectsync/.env')

cwd_creds_path = os.path.join(os.getcwd(), '.creds_cache')
global_creds_path = os.path.join(pathlib.Path.home(), '.config/tconnectsync/.creds_cache')

values = {}

if os.path.exists(cwd_path):
    values = dotenv_values(cwd_path)
elif os.path.exists(global_path):
    values = dotenv_values(global_path)
else:
    values = dotenv_values()

def get(val, default=None):
    return os.environ.get(val, values.get(val, default))

def get_one_of(name, default=None, options=[]):
    val = get(name, default)
    if val not in options:
        print("Error: %s must be one of: %s" % (name, options))
        print("Current value: %s" % val)
        sys.exit(1)
    return val

def get_number(name, default):
    val = get(name, default)
    try:
        return float(val)
    except ValueError:
        print("Error: %s must be a number." % name)
        print("Current value: %s" % val)
        sys.exit(1)

def get_bool(name, default):
    return str(get(name, default) or '').lower() in ('true', '1')

TCONNECT_EMAIL = get('TCONNECT_EMAIL', 'email@email.com')
TCONNECT_PASSWORD = get('TCONNECT_PASSWORD', 'password')
TCONNECT_REGION = get_one_of('TCONNECT_REGION', 'US', ['US', 'EU'])

PUMP_SERIAL_NUMBER = int(get_number('PUMP_SERIAL_NUMBER', '11111111'))

NS_URL = get('NS_URL', 'https://yournightscouturl/')
NS_SECRET = get('NS_SECRET', 'apisecret')

if not get('NS_SECRET') and get('API_SECRET'):
    print('API_SECRET environment variable is set, overriding NS_SECRET')
    NS_SECRET = get('API_SECRET')

NS_SKIP_TLS_VERIFY = get_bool('NS_SKIP_TLS_VERIFY', 'false')
NS_IGNORE_CONN_ERRORS = get_bool('NS_IGNORE_CONN_ERRORS', 'false')

# This should be the timezone your pump is set to.
TIMEZONE_NAME = get('TIMEZONE_NAME', 'America/New_York')

if not get('TIMEZONE_NAME') and get('TZ'):
    print('TZ environment variable is set, overriding TIMEZONE_NAME')
    TIMEZONE_NAME = get('TZ')

# Optional configuration

CACHE_CREDENTIALS = get_bool('CACHE_CREDENTIALS', 'true')
CACHE_CREDENTIALS_PATH = get('CACHE_CREDENTIALS', cwd_creds_path if os.path.exists(cwd_creds_path) else global_creds_path)
AUTOUPDATE_DEFAULT_SLEEP_SECONDS = get_number('AUTOUPDATE_DEFAULT_SLEEP_SECONDS', '300') # 5 minutes
AUTOUPDATE_MAX_SLEEP_SECONDS = get_number('AUTOUPDATE_MAX_SLEEP_SECONDS', '1500') # 25 minutes
AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS = get_number('AUTOUPDATE_UNEXPECTED_NO_INDEX_SLEEP_SECONDS', '60') # 1 minute
AUTOUPDATE_USE_FIXED_SLEEP = get_bool('AUTOUPDATE_USE_FIXED_SLEEP', 'false')
AUTOUPDATE_NO_DATA_FAILURE_MINUTES = get_number('AUTOUPDATE_NO_DATA_FAILURE_MINUTES', '180') # 3 hours
AUTOUPDATE_FAILURE_MINUTES = get_number('AUTOUPDATE_FAILURE_MINUTES', '75') # 75 minutes
AUTOUPDATE_RESTART_ON_FAILURE = get_bool('AUTOUPDATE_RESTART_ON_FAILURE', 'false')
AUTOUPDATE_MAX_LOOP_INVOCATIONS = get_number('AUTOUPDATE_MAX_LOOP_INVOCATIONS', '-1')

NIGHTSCOUT_PROFILE_UPLOAD_MODE = get_one_of('NIGHTSCOUT_PROFILE_UPLOAD_MODE', 'add', ['add', 'replace'])

# When set, all possible history log event types are fetched from Tandem Source
FETCH_ALL_EVENT_TYPES = get_bool('FETCH_ALL_EVENT_TYPES', 'false')

# Default Nightscout profile segment fields which aren't stored by Tandem
NIGHTSCOUT_PROFILE_CARBS_HR_VALUE = get('NIGHTSCOUT_PROFILE_CARBS_HR_VALUE', '20')
NIGHTSCOUT_PROFILE_DELAY_VALUE = get('NIGHTSCOUT_PROFILE_DELAY_VALUE', '20')
IGNORE_ZERO_UNIT_BASAL = get_bool('IGNORE_ZERO_UNIT_BASAL', 'false')

ENABLE_TESTING_MODES = get_bool('ENABLE_TESTING_MODES', 'false')
SKIP_NS_LAST_UPLOADED_CHECK = get_bool('SKIP_NS_LAST_UPLOADED_CHECK', 'false')
REQUESTS_PROXY = get('REQUESTS_PROXY', '')

if __name__ == '__main__':
    for k in locals():
        print("{} = {}".format(k, locals().get(k)))
