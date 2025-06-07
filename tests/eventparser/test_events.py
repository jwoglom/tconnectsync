import unittest
from tconnectsync.eventparser.events import LidCgmAlertActivatedDex, LidCgmAlertClearedDex
from tconnectsync.eventparser.raw_event import RawEvent
import arrow

class TestEventParserEvents(unittest.TestCase):
    def test_lid_cgm_alert_activated_dex_unknown_alert_2(self):
        # Create a dummy RawEvent
        raw_event_data = bytearray(b'\x01q \xc9!k\x00\x02\t\xc3\x00\x00\x02\x0e\x00\x00!\x0e\x00\x00\x00\x14D\\@\x00') # Example raw data, modify if needed

        # Modify bytes for dalertidRaw = 2 and other relevant fields if necessary
        # Assuming dalertid is at byte index 13 as per LidCgmAlertActivatedDex structure
        # raw_event_data[13] = 2 # This is a simplified example, actual byte manipulation might be more complex

        # For the purpose of this test, we will mock the build method to directly inject the dalertidRaw value
        # as byte manipulation is complex and error-prone without deeper knowledge of the byte structure.

        mock_raw_event = RawEvent(source=0, id=369, timestampRaw=0, seqNum=0, raw=bytearray(b''))

        event = LidCgmAlertActivatedDex(
            raw=mock_raw_event, # This would ideally be a properly constructed RawEvent
            dalertidRaw=2,
            sensortypeRaw=3, # Example value
            faultlocatordata=0, # Example value
            param1=0, # Example value
            param2=0.0 # Example value
        )
        self.assertEqual(event.dalertidRaw, 2)
        self.assertEqual(event.dalertid, LidCgmAlertActivatedDex.DalertidEnum.UnknownAlert2)
        self.assertIn("Unknown Alert 2", LidCgmAlertActivatedDex.DalertidMap.get("2"))

    def test_lid_cgm_alert_cleared_dex_unknown_alert_2(self):
        mock_raw_event = RawEvent(source=0, id=370, timestampRaw=0, seqNum=0, raw=bytearray(b''))

        event = LidCgmAlertClearedDex(
            raw=mock_raw_event, # This would ideally be a properly constructed RawEvent
            dalertidRaw=2,
            sensortypeRaw=3 # Example value
        )
        self.assertEqual(event.dalertidRaw, 2)
        self.assertEqual(event.dalertid, LidCgmAlertClearedDex.DalertidEnum.UnknownAlert2)
        self.assertIn("Unknown Alert 2", LidCgmAlertClearedDex.DalertidMap.get("2"))


if __name__ == '__main__':
    unittest.main()
