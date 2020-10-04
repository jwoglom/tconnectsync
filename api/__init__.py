from .android import AndroidApi
from .controliq import ControlIQApi
from .ws2 import WS2Api

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
        if self._ciq:
            return self._ciq

        self._ciq = ControlIQApi(self.email, self.password)
        return self._ciq

    @property
    def ws2(self):
        if self._ws2:
            return self._ws2

        self._ws2 = WS2Api(self._ciq.userGuid)
        return self._ws2

    @property
    def android(self):
        if self._android and not self._android.needs_relogin():
            return self._android

        self._android = AndroidApi(self.email, self.password)
        return self._android

