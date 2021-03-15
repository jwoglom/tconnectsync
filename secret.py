import os, sys
from dotenv import load_dotenv
load_dotenv( )

TCONNECT_EMAIL = os.environ.get('TCONNECT_EMAIL', 'email@email.com')
TCONNECT_PASSWORD = os.environ.get('TCONNECT_PASSWORD', 'password')

try:
  PUMP_SERIAL_NUMBER = int(os.environ.get('PUMP_SERIAL_NUMBER', '11111111'))
  if (len(str(PUMP_SERIAL_NUMBER)) < 8):
    print("""PUMP_SERIAL_NUMBER should be a number.
  Please review the following which is not a number.
  PUMP_SERIAL_NUMBER={}""".format(os.environ.get('PUMP_SERIAL_NUMBER')))
    sys.exit(1)
except ValueError as e:
  print("""PUMP_SERIAL_NUMBER must be a number.
Please review the following which is not a number.
PUMP_SERIAL_NUMBER={}""".format(os.environ.get('PUMP_SERIAL_NUMBER')))
  sys.exit(1)

NS_URL = os.environ.get('NS_URL', 'https://yournightscouturl/')
NS_SECRET = os.environ.get('NS_SECRET', 'apisecret')

TIMEZONE_NAME = os.environ.get('TIMEZONE_NAME', 'America/New_York')
_config = ['TCONNECT_EMAIL', 'TCONNECT_PASSWORD', 'PUMP_SERIAL_NUMBER',
          'NS_URL', 'NS_SECRET', 'TIMEZONE_NAME']

if __name__ == '__main__':
  for k in _config:
    print("{}: {}".format( k, locals( ).get(k)))

