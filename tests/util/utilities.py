import arrow
from tconnectsync.secret import TIMEZONE_NAME

"""
Replaces timezone in string with provided timezone string, defaults to 'America/New_York'
  Example 1: replace_datetime_tz("2021-04-01 23:15:30-04:00")
  Example 2: replace_datetime_tz("2021-04-01 23:15:30-04:00", 'America/Chicago')
"""
def replace_with_user_tz(date, tz=TIMEZONE_NAME):
   return arrow.get(date, tzinfo=tz).format()
