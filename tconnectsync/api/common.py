import datetime

def parse_date(date):
    if type(date) == str:
        return date
    return (date or datetime.datetime.now()).strftime('%m-%d-%Y')

def base_headers():
    return {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36'}

class ApiException(Exception):
    def __init__(self, status_code, text, *args, **kwargs):
        self.status_code = status_code
        super().__init__('%s (HTTP %s)' % (text, status_code), *args, **kwargs)

class ApiLoginException(ApiException):
    pass