import importlib

def build_secrets(**kwargs):
    secret = importlib.reload(importlib.import_module("tconnectsync.secret"))
    class FakeSecret(object):
        pass

    fake = FakeSecret()
    for k in dir(secret):
        setattr(fake, k, getattr(secret, k))

    for k, v in kwargs.items():
        setattr(fake, k, v)
    
    return fake