import logging

"""
Enables logging at the specified level for all loggers
inside the tconnectsync package, and sets up a basicConfig
to print those log messages to stderr.
"""
def enable_logging(level=logging.DEBUG):
    logging.basicConfig()
    for logger in logging.root.manager.loggerDict:
        if logger.startswith('tconnectsync'):
            logging.getLogger(logger).setLevel(level)

"""
Returns a TConnectApi object with default secret parameters.
"""
def get_api():
    from ..api import TConnectApi
    from ..secret import TCONNECT_EMAIL, TCONNECT_PASSWORD
    return TConnectApi(TCONNECT_EMAIL, TCONNECT_PASSWORD)