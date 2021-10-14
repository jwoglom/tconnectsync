import tconnectsync.api

class ControlIQApi(tconnectsync.api.controliq.ControlIQApi):
    def __init__(self):
        self.BASE_URL = 'invalid://'
        self.LOGIN_URL = 'invalid://'

    def login(self, email, password):
        raise NotImplementedError

    def needs_relogin(self):
        return False

    def _get(self, endpoint, query):
        raise NotImplementedError

class WS2Api(tconnectsync.api.ws2.WS2Api):
    def __init__(self):
        self.BASE_URL = 'invalid://'
        self.SLEEP_SECONDS_INCREMENT = 0.01

    def get(self, endpoint, query):
        raise NotImplementedError

    def get_jsonp(self, endpoint):
        raise NotImplementedError

class AndroidApi(tconnectsync.api.android.AndroidApi):
    def __init__(self):
        self.BASE_URL = 'invalid://'

    def login(self, email, password):
        raise NotImplementedError

    def needs_relogin(self):
        return False

    def _get(self, endpoint, query={}, **kwargs):
        raise NotImplementedError

class TConnectApi(tconnectsync.api.TConnectApi):
    def __init__(self):
        pass

    _ciq = ControlIQApi()
    _ws2 = WS2Api()
    _android = AndroidApi()
