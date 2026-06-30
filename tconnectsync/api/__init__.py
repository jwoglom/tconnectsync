import logging

from .tandemsource import TandemSourceApi

logger = logging.getLogger(__name__)

"""A wrapper for the Tandem Source API."""
class TConnectApi:
    email = None
    password = None

    def __init__(self, email, password, region='US'):
        self.email = email
        self.password = password
        self.region = region
        self._tandemsource = None

    @property
    def tandemsource(self):
        if self._tandemsource and not self._tandemsource.needs_relogin():
            return self._tandemsource

        logger.debug(f"Instantiating new TandemSourceApi for region {self.region}")

        self._tandemsource = TandemSourceApi(self.email, self.password, self.region)
        return self._tandemsource
