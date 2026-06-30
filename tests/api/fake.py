import tconnectsync.api


class TConnectApi(tconnectsync.api.TConnectApi):
    def __init__(self, email=None, password=None):
        if email is not None and password is not None:
            self.with_credentials = True
        else:
            self.with_credentials = False

    _tandemsource = None
