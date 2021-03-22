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

TCONNECT_EMAIL = get('TCONNECT_EMAIL', 'email@email.com')
TCONNECT_PASSWORD = get('TCONNECT_PASSWORD', 'password')

PUMP_SERIAL_NUMBER = get_number('PUMP_SERIAL_NUMBER', '11111111')

NS_URL = get('NS_URL', 'https://yournightscouturl/')
NS_SECRET = get('NS_SECRET', 'apisecret')

TIMEZONE_NAME = get('TIMEZONE_NAME', 'America/New_York')

# Optional configuration

AUTOUPDATE_DEFAULT_SLEEP_SECONDS = get_number('AUTOUPDATE_DEFAULT_SLEEP_SECONDS', '60')
AUTOUPDATE_MAX_SLEEP_SECONDS = get_number('AUTOUPDATE_MAX_SLEEP_SECONDS', '600')
AUTOUPDATE_USE_FIXED_SLEEP = get_number('AUTOUPDATE_USE_FIXED_SLEEP', '0')

_config = ['TCONNECT_EMAIL', 'TCONNECT_PASSWORD', 'PUMP_SERIAL_NUMBER',
          'NS_URL', 'NS_SECRET', 'TIMEZONE_NAME',
          'AUTOUPDATE_DEFAULT_SLEEP_SECONDS', 'AUTOUPDATE_MAX_SLEEP_SECONDS',
          'AUTOUPDATE_USE_FIXED_SLEEP']

if __name__ == '__main__':
    for k in locals():
        print("{} = {}".format(k, locals().get(k)))
