import logging

from .android import AndroidApi
from .controliq import ControlIQApi
from .ws2 import WS2Api

logger = logging.getLogger(__name__)

"""A wrapper for the three different t:connect API types."""
class TConnectApi:
    email = None
    password = None

    _ciq = None
    _ws2 = None
    _android = None

    def __init__(self, email, password):
        self.email = email
        self.password = password


    @property
    def controliq(self):
        if self._ciq and not self._ciq.needs_relogin():
            return self._ciq

        logger.debug("Instantiating new ControlIQApi")

        self._ciq = ControlIQApi(self.email, self.password)
        return self._ciq

    @property
    def ws2(self):
        if self._ws2:
            return self._ws2

        logger.debug("Instantiating new WS2Api")

        # Trigger login or re-login via controliq api if necessary
        # so userGuid can be accessed from it
        self.controliq

        self._ws2 = WS2Api(self._ciq.userGuid)
        return self._ws2

    @property
    def android(self):
        if self._android and not self._android.needs_relogin():
            return self._android

        logger.debug("Instantiating new AndroidApi")

        self._android = AndroidApi(self.email, self.password)
        return self._android

