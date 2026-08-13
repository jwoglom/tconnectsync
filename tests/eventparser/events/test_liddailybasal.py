#!/usr/bin/env python3

import json
import unittest

from tconnectsync.eventparser.generic import Event
from tconnectsync.eventparser import events as eventtypes
from tconnectsync.eventparser.raw_event import RawEvent


class TestLidDailyBasal(unittest.TestCase):
    """81: LID_DAILY_BASAL. Real captured binary events.

    The trailing 4 bytes are one packed uint32:
        (batteryLipoMilliVolts << 16) | (batteryChargePercent << 8) | finalEventForDay
    Tandem Source serializes scalars big-endian, so on the wire those bytes are
    [lipo_hi, lipo_lo, percent, final] at absolute offsets 22, 23, 24, 25.
    (pumpX2's BLE stream packs the same u32 little-endian, which is why its
    Java/Swift ports read the three fields in the opposite order -- correct
    there, wrong here.)

    batteryChargePercent is the pump's own state-of-charge byte, already scaled
    0-100; it is not derived from the millivolt bytes and carries no scaling.
    """
    maxDiff = None

    def setUp(self):
        # 2024-12-03 23:40:23-05:00, seq 1046436. Tail: 0e f6 37 00.
        self.fixtureMidCharge = b'\x00Q\x1f\xd6\x14g\x00\x0f\xf7\xa4A\xb2\xd3\xe2?L\xcc\xcd@~\xdeb\x0e\xf67\x00'
        # 2024-12-04 02:30:23-05:00, seq 1046875. Tail: 0e f3 36 00.
        self.fixtureMidChargeLater = b'\x00Q\x1f\xd6<?\x00\x0f\xf9[@\r\xcd{?\x9b\xa5\xe3?\xe3\x9a;\x0e\xf36\x00'
        # fixtureMidCharge with byte 25 forced to 0x01: the end-of-day marker.
        self.fixtureFinalEventForDay = self.fixtureMidCharge[:25] + b'\x01'
        # fixtureMidCharge with byte 24 forced to 0x64: a full battery.
        self.fixtureFullCharge = self.fixtureMidCharge[:24] + b'\x64' + self.fixtureMidCharge[25:]

    def test_dispatches_to_liddailybasal(self):
        ev = Event(self.fixtureMidCharge)
        self.assertIsInstance(ev, eventtypes.LidDailyBasal)
        self.assertIsNot(type(ev), RawEvent)

    def test_envelope_fields(self):
        ev = Event(self.fixtureMidCharge)
        self.assertEqual(ev.eventId, 81)
        self.assertEqual(ev.seqNum, 1046436)
        self.assertEqual(ev.raw.timestampRaw, 534123623)

    def test_timestamp_preserves_wall_clock(self):
        ev = Event(self.fixtureMidCharge)
        self.assertEqual(
            ev.eventTimestamp.format('YYYY-MM-DDTHH:mm:ss'),
            "2024-12-03T23:40:23",
        )

    def test_leading_float_fields(self):
        # The three float32s ahead of the packed u32 are unaffected by the
        # trailing-field layout; pinned here so a future offset change is loud.
        ev = Event(self.fixtureMidCharge)
        self.assertAlmostEqual(ev.dailyTotalBasal, 22.3535, places=4)
        self.assertAlmostEqual(ev.lastBasalRate, 0.8, places=4)
        self.assertAlmostEqual(ev.iob, 3.9823, places=4)

    def test_battery_fields_mid_charge(self):
        ev = Event(self.fixtureMidCharge)
        self.assertEqual(ev.batteryLipoMilliVolts, 3830)
        self.assertEqual(ev.batteryChargePercent, 55)
        self.assertEqual(ev.finalEventForDay, 0)

    def test_battery_fields_mid_charge_later(self):
        ev = Event(self.fixtureMidChargeLater)
        self.assertEqual(ev.seqNum, 1046875)
        self.assertEqual(ev.batteryLipoMilliVolts, 3827)
        self.assertEqual(ev.batteryChargePercent, 54)
        self.assertEqual(ev.finalEventForDay, 0)

    def test_lipo_millivolts_is_a_plausible_single_cell_voltage(self):
        # Reading the u32's high half as the voltage is what keeps this in 1S
        # LiPo range; the old layout produced 14080 mV here.
        for raw in (self.fixtureMidCharge, self.fixtureMidChargeLater):
            with self.subTest(raw=raw):
                ev = Event(raw)
                self.assertGreater(ev.batteryLipoMilliVolts, 3000)
                self.assertLess(ev.batteryLipoMilliVolts, 4400)

    def test_final_event_for_day_set(self):
        ev = Event(self.fixtureFinalEventForDay)
        self.assertEqual(ev.finalEventForDay, 1)
        # Flipping the last byte must not disturb the other two fields.
        self.assertEqual(ev.batteryLipoMilliVolts, 3830)
        self.assertEqual(ev.batteryChargePercent, 55)

    def test_battery_charge_percent_is_a_direct_percentage(self):
        # Byte 24 == 0x64 means 100%, not 100/256, 10000, or anything scaled.
        ev = Event(self.fixtureFullCharge)
        self.assertEqual(ev.batteryChargePercent, 100)
        self.assertIsInstance(ev.batteryChargePercent, int)
        self.assertEqual(ev.batteryLipoMilliVolts, 3830)
        self.assertEqual(ev.finalEventForDay, 0)

    def test_build_from_json(self):
        ev = Event({
            "eventCode": 81,
            "sequenceGroup": 0,
            "sequenceNumber": 1046436,
            "pumpDateTime": "2024-12-03T23:40:23",
            "eventProperties": {
                "dailyTotalBasal": 22.3535,
                "lastBasalRate": 0.8,
                "iob": 3.9823,
                "batteryLipoMilliVolts": 3830,
                "batteryChargePercent": 55,
                "finalEventForDay": 0,
            },
        })
        self.assertIsInstance(ev, eventtypes.LidDailyBasal)
        self.assertEqual(ev.batteryLipoMilliVolts, 3830)
        self.assertEqual(ev.batteryChargePercent, 55)
        self.assertEqual(ev.finalEventForDay, 0)

    def test_todict_is_json_serializable(self):
        ev = Event(self.fixtureMidCharge)
        d = ev.todict()
        json.dumps(d)  # must not raise
        self.assertEqual(d["id"], 81)
        self.assertEqual(d["name"], "LID_DAILY_BASAL")
        self.assertEqual(d["seqNum"], 1046436)
        self.assertEqual(d["batteryLipoMilliVolts"], 3830)
        self.assertEqual(d["batteryChargePercent"], 55)
        self.assertEqual(d["finalEventForDay"], 0)
        # The superseded MSB/LSB decomposition is gone for good.
        self.assertNotIn("batteryChargePercentMSBRaw", d)
        self.assertNotIn("batteryChargePercentLSBRaw", d)


if __name__ == "__main__":
    unittest.main()
