import tconnectsync.api

class ControlIQApi(tconnectsync.api.controliq.ControlIQApi):
    BASE_URL = 'invalid://'
    LOGIN_URL = 'invalid://'

    def __init__(self):
        pass

    def login(self, email, password):
        raise NotImplementedError

    def get(self, endpoint, query):
        raise NotImplementedError

class WS2Api(tconnectsync.api.ws2.WS2Api):
    BASE_URL = 'invalid://'

    def __init__(self):
        pass

    def get(self, endpoint, query):
        raise NotImplementedError

    def get_jsonp(self, endpoint):
        raise NotImplementedError

class AndroidApi(tconnectsync.api.android.AndroidApi):
    BASE_URL = 'invalid://'

    def __init__(self):
        pass

    def login(self, email, password):
        raise NotImplementedError

    def needs_relogin(self):
        return False

    def get(self, endpoint, query={}, **kwargs):
        raise NotImplementedError

class TConnectApi(tconnectsync.api.TConnectApi):
    def __init__(self):
        pass

    _ciq = ControlIQApi()
    _ws2 = WS2Api()
    _android = AndroidApi()
