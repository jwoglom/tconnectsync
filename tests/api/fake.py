import tconnectsync.api
import requests

class ControlIQApi(tconnectsync.api.controliq.ControlIQApi):
    def __init__(self):
        self.BASE_URL = 'invalid://'
        self.LOGIN_URL = 'invalid://'
        self.session = requests.Session() # mocked in tests

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

    def get(self, endpoint):
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

class WebUIScraper(tconnectsync.api.webui.WebUIScraper):
    def __init__(self, controliq):
        self.controliq = controliq

class TConnectApi(tconnectsync.api.TConnectApi):
    def __init__(self, email=None, password=None):
        if email is not None and password is not None:
            self.with_credentials = True
        else:
            self.with_credentials = False

    _ciq = ControlIQApi()
    _ws2 = WS2Api()
    _android = AndroidApi()
