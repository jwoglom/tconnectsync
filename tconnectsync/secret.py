import os, sys
from dotenv import load_dotenv

load_dotenv()

def get(*args):
    return os.environ.get(*args)

def get_number(name, default):
    val = get(name, default)
    try:
        return int(val)
    except ValueError:
        print("Error: %s must be a number." % name)
        print("Current value: %s" % val)
        sys.exit(1)

def get_bool(name, default):
    return str(get(name, default) or '').lower() in ('true', '1')

TCONNECT_EMAIL = get('TCONNECT_EMAIL', 'email@email.com')
TCONNECT_PASSWORD = get('TCONNECT_PASSWORD', 'password')

PUMP_SERIAL_NUMBER = get_number('PUMP_SERIAL_NUMBER', '11111111')

NS_URL = get('NS_URL', 'https://yournightscouturl/')
NS_SECRET = get('NS_SECRET', 'apisecret')

TIMEZONE_NAME = get('TIMEZONE_NAME', 'America/New_York')

# Optional configuration

AUTOUPDATE_DEFAULT_SLEEP_SECONDS = get_number('AUTOUPDATE_DEFAULT_SLEEP_SECONDS', '300') # 5 minutes
AUTOUPDATE_MAX_SLEEP_SECONDS = get_number('AUTOUPDATE_MAX_SLEEP_SECONDS', '1500') # 25 minutes
AUTOUPDATE_USE_FIXED_SLEEP = get_bool('AUTOUPDATE_USE_FIXED_SLEEP', 'false')
AUTOUPDATE_FAILURE_MINUTES = get_number('AUTOUPDATE_FAILURE_MINUTES', '180') # 3 hours
AUTOUPDATE_RESTART_ON_FAILURE = get_bool('AUTOUPDATE_RESTART_ON_FAILURE', 'false')

ENABLE_TESTING_MODES = get_bool('ENABLE_TESTING_MODES', 'false')

if __name__ == '__main__':
    for k in locals():
        print("{} = {}".format(k, locals().get(k)))
