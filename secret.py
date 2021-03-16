import os, sys
from dotenv import load_dotenv

load_dotenv()

TCONNECT_EMAIL = os.environ.get('TCONNECT_EMAIL', 'email@email.com')
TCONNECT_PASSWORD = os.environ.get('TCONNECT_PASSWORD', 'password')

try:
    PUMP_SERIAL_NUMBER = int(os.environ.get('PUMP_SERIAL_NUMBER', '11111111'))
except ValueError as e:
    print("Error: PUMP_SERIAL_NUMBER must be a number.")
    print("Current value: {}".format(PUMP_SERIAL_NUMBER))
    sys.exit(1)

NS_URL = os.environ.get('NS_URL', 'https://yournightscouturl/')
NS_SECRET = os.environ.get('NS_SECRET', 'apisecret')

TIMEZONE_NAME = os.environ.get('TIMEZONE_NAME', 'America/New_York')

_config = ['TCONNECT_EMAIL', 'TCONNECT_PASSWORD', 'PUMP_SERIAL_NUMBER',
          'NS_URL', 'NS_SECRET', 'TIMEZONE_NAME']

if __name__ == '__main__':
    for k in locals():
        print("{}={}".format(k, locals().get(k)))
