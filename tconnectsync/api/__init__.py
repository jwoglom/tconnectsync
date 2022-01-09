import logging

from .android import AndroidApi
from .controliq import ControlIQApi
from .ws2 import WS2Api
from .webui import WebUIScraper

logger = logging.getLogger(__name__)

"""A wrapper for the three different t:connect API types."""
class TConnectApi:
    email = None
    password = None

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self._ciq = None
        self._ws2 = None
        self._android = None
        self._webui = None


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
    
    @property
    def webui(self):
        if self._webui and not self._webui.needs_relogin():
            return self._webui
        
        logger.debug("Instantiating new WebUIScraper")

        self._webui = WebUIScraper(self.controliq)
        return self._webui

