import logging

from .tandemsource import TandemSourceApi
from .. import secret

logger = logging.getLogger(__name__)

"""A wrapper for the Tandem Source API."""
class TConnectApi:
    email = None
    password = None

    def __init__(self, email, password, region=None):
        self.email = email
        self.password = password
        # A caller which does not pass a region (e.g. tconnectsync-heroku)
        # must get the configured TCONNECT_REGION, not a hardcoded US
        # default which would send EU accounts to the US endpoints (#152).
        self.region = region or secret.TCONNECT_REGION
        self._tandemsource = None

    @property
    def tandemsource(self):
        if self._tandemsource and not self._tandemsource.needs_relogin():
            return self._tandemsource

        logger.debug(f"Instantiating new TandemSourceApi for region {self.region}")

        self._tandemsource = TandemSourceApi(self.email, self.password, self.region)
        return self._tandemsource
