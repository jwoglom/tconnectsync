import unittest
import arrow
from tconnectsync.nightscout import format_datetime, time_range

class TestNightscoutDateParsing(unittest.TestCase):
    def test_format_datetime_various_formats(self):
        # Test with 'T' separator and timezone
        self.assertEqual(format_datetime("2023-10-26T10:00:00+02:00"), "2023-10-26T10:00:00+02:00")
        # Test with space separator and timezone
        self.assertEqual(format_datetime("2023-10-26 10:00:00+02:00"), "2023-10-26T10:00:00+02:00")
        # Test with 'T' separator without timezone
        self.assertEqual(format_datetime("2023-10-26T10:00:00"), "2023-10-26T10:00:00+00:00") # Arrow defaults to UTC
        # Test with space separator without timezone
        self.assertEqual(format_datetime("2023-10-26 10:00:00"), "2023-10-26T10:00:00+00:00") # Arrow defaults to UTC

    def test_format_datetime_invalid_format(self):
        with self.assertRaises(arrow.parser.ParserError):
            format_datetime("invalid-date-format")

    def test_time_range_formatting(self):
        # Test with start_time only, using a timezone-aware string
        self.assertEqual(
            time_range('created_at', "2023-10-26 10:00:00+02:00", None),
            "&find[created_at][$gte]=2023-10-26T10:00:00+02:00"
        )
        # Test with end_time only, using a timezone-aware ISO string with 'T' and 'Z'
        self.assertEqual(
            time_range('dateString', None, "2023-10-27T12:00:00Z"),
            "&find[dateString][$lte]=2023-10-27T12:00:00+00:00"
        )
        # Test with both start_time (naive, space separated) and end_time (naive, 'T' separated)
        self.assertEqual(
            time_range('myCustomField', "2023-10-28 08:00:00", "2023-10-28T09:00:00"),
            "&find[myCustomField][$gte]=2023-10-28T08:00:00+00:00&find[myCustomField][$lte]=2023-10-28T09:00:00+00:00"
        )
        # Test with start_time only, using a string that arrow parses as UTC by default if no timezone is present
        self.assertEqual(
            time_range('event_time', "2024-01-01T15:30:00", None),
            "&find[event_time][$gte]=2024-01-01T15:30:00+00:00"
        )
        # Test with no times (should return an empty string)
        self.assertEqual(
            time_range('any_field', None, None),
            ""
        )

if __name__ == '__main__':
    unittest.main()
