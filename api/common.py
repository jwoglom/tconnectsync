import datetime

def parse_date(date):
    if type(date) == str:
        return date
    return (date or datetime.datetime.now()).strftime('%m-%d-%Y')

class ApiException(Exception):
    def __init__(self, status_code, text, *args, **kwargs):
        self.status_code = status_code
        super().__init__(text, *args, **kwargs)
