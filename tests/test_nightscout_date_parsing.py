import unittest
import arrow
from tconnectsync.nightscout import format_datetime

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

if __name__ == '__main__':
    unittest.main()
