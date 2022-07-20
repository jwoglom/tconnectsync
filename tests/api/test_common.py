import unittest

from unittest.mock import patch

from tconnectsync.api.common import base_session

class TestRequestsProxy(unittest.TestCase):
    def test_proxy_used_in_base_session(self):
        with patch("tconnectsync.api.common.secret") as mock_secret, \
             patch("requests.Session.request") as mock_request:

            s = base_session()
            s.request('sentinel')

            mock_request.assert_called_once_with('sentinel', proxies={
                'http': mock_secret.REQUESTS_PROXY,
                'https': mock_secret.REQUESTS_PROXY
            })

    def test_proxy_used_in_base_session_with_two_args(self):
        with patch("tconnectsync.api.common.secret") as mock_secret, \
             patch("requests.Session.request") as mock_request:

            s = base_session()
            s.request('GET', 'sentinel')

            mock_request.assert_called_once_with('GET', 'sentinel', proxies={
                'http': mock_secret.REQUESTS_PROXY,
                'https': mock_secret.REQUESTS_PROXY
            })

    def test_proxy_used_in_base_session_with_kwargs(self):
        with patch("tconnectsync.api.common.secret") as mock_secret, \
             patch("requests.Session.request") as mock_request:

            s = base_session()
            s.request('GET', 'sentinel', foo={'bar': 'baz'})

            mock_request.assert_called_once_with('GET', 'sentinel', foo={'bar': 'baz'}, proxies={
                'http': mock_secret.REQUESTS_PROXY,
                'https': mock_secret.REQUESTS_PROXY
            })

            
