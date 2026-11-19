#!/usr/bin/env python3
"""Tests for the Nightscout query building: the date filter in time_range()
and the devicestatus "last uploaded" lookup."""

import unittest
import urllib.parse
from unittest import mock

import arrow

from tconnectsync.nightscout import NightscoutApi, time_range


class TestTimeRangeEncoding(unittest.TestCase):
    """A positive UTC offset ends an ISO-8601 timestamp with '+02:00'. Placed
    raw into a query string, the '+' is a reserved character that servers decode
    as a space, so Nightscout receives '2026-07-16T00:00:00 02:00' and rejects
    it with "could not parse as a valid ISO-8601 date". Percent-encoding the
    value keeps the offset intact."""

    def test_positive_offset_is_percent_encoded(self):
        start = arrow.get("2026-07-16T00:00:00+02:00")

        arg = time_range('created_at', start, None)

        self.assertNotIn(
            '+', arg,
            "A raw '+' in the query string is decoded to a space by the server, "
            "mangling the timestamp. Got: %s" % arg,
        )
        self.assertIn('%2B', arg, "Expected the offset '+' to be encoded as %%2B. Got: %s" % arg)

    def test_encoded_value_round_trips_to_the_original_timestamp(self):
        """Decoding the query the way a server would must yield the timestamp
        we meant to send."""
        start = arrow.get("2026-07-16T00:00:00+02:00")

        arg = time_range('created_at', start, None)

        value = arg.split('=', 1)[1]
        self.assertEqual(
            arrow.get(urllib.parse.unquote(value)), start,
            "Round-tripping the encoded filter must reproduce the original instant",
        )

    def test_negative_offset_and_z_suffix_still_parse(self):
        """US pumps report a '-04:00' offset and UTC values end in 'Z'; neither
        is ambiguous in a query string, but both must survive encoding."""
        for iso in ("2026-07-16T00:00:00-04:00", "2026-07-16T00:00:00Z"):
            with self.subTest(iso=iso):
                expected = arrow.get(iso)
                arg = time_range('created_at', expected, None)
                value = arg.split('=', 1)[1]
                self.assertEqual(arrow.get(urllib.parse.unquote(value)), expected)

    def test_both_bounds_are_emitted(self):
        start = arrow.get("2026-07-16T00:00:00+02:00")
        end = arrow.get("2026-07-17T00:00:00+02:00")

        arg = time_range('created_at', start, end)

        self.assertIn('find[created_at][$gte]=', arg)
        self.assertIn('find[created_at][$lte]=', arg)

    def test_omitted_bounds_produce_no_filter(self):
        self.assertEqual(time_range('created_at', None, None), '')


class TestLastUploadedDevicestatus(unittest.TestCase):
    """The pump's status goes up as more than one kind of devicestatus
    document; has_field asks Nightscout for the newest one of a kind."""

    def requested_url(self, **kwargs):
        response = mock.Mock(status_code=200)
        response.json.return_value = [{'created_at': '2026-11-19T16:24:21.000Z'}]
        with mock.patch('tconnectsync.nightscout.requests.get', return_value=response) as get:
            ret = NightscoutApi('https://ns.example/', 'secret').last_uploaded_devicestatus(**kwargs)
        self.assertEqual(ret, {'created_at': '2026-11-19T16:24:21.000Z'})
        return get.call_args[0][0]

    def test_without_a_field_asks_for_the_newest_of_this_tool(self):
        url = self.requested_url()

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query['find[device]'], ['Pump (tconnectsync)'])
        self.assertEqual(query['count'], ['1'])
        self.assertFalse([k for k in query if '$exists' in k])

    def test_has_field_filters_on_the_field_existing(self):
        url = self.requested_url(has_field='pump.reservoir')

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query['find[pump.reservoir][$exists]'], ['true'])
        self.assertEqual(query['find[device]'], ['Pump (tconnectsync)'])
        self.assertEqual(query['count'], ['1'])

    def test_has_field_keeps_the_date_window(self):
        url = self.requested_url(
            has_field='pump.battery.voltage',
            time_start=arrow.get("2026-11-18T17:00:00+01:00"),
            time_end=arrow.get("2026-11-19T17:00:00+01:00"))

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query['find[pump.battery.voltage][$exists]'], ['true'])
        self.assertEqual(arrow.get(query['find[created_at][$gte]'][0]), arrow.get("2026-11-18T17:00:00+01:00"))
        self.assertEqual(arrow.get(query['find[created_at][$lte]'][0]), arrow.get("2026-11-19T17:00:00+01:00"))


if __name__ == "__main__":
    unittest.main()
