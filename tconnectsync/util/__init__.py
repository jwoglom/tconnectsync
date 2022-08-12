import arrow

from . import cli
from . import constants

def timeago(timestamp):
    seconds = (arrow.get() - arrow.get(timestamp)).total_seconds()
    fmt = '%s ago' if seconds >= 0 else 'in %s'
    seconds = abs(seconds)

    ret = ''
    if seconds//86400 > 0:
        ret += '%d days, ' % (seconds//86400)
        seconds = seconds % 86400
    if seconds//3600 > 0:
        ret += '%d hours, ' % (seconds//3600)
        seconds = seconds % 3600
    ret += '%d minutes' % (seconds//60)

    return fmt % ret

# String methods only available in python 3.9+
def removesuffix(input_string, suffix):
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string

def removeprefix(input_string, prefix):
    if prefix and input_string.startswith(prefix):
        return input_string[len(prefix):]
    return input_string