#!/usr/bin/env python3

import unittest
from tconnectsync.parser.nightscout import NightscoutEntry, InvalidBolusTypeException, tandem_to_ns_time, tandem_to_ns_time_seconds
from tconnectsync.domain.device_settings import Profile, ProfileSegment, DeviceSettings
from tconnectsync.secret import NIGHTSCOUT_PROFILE_CARBS_HR_VALUE, NIGHTSCOUT_PROFILE_DELAY_VALUE, TIMEZONE_NAME

class TestNightscoutEntry(unittest.TestCase):
    maxDiff = None
    def test_basal(self):
        self.assertEqual(
            NightscoutEntry.basal(
                value=1.05,
                duration_mins=30,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "eventType": "Temp Basal",
                "reason": "",
                "duration": 30,
                "absolute": 1.05,
                "rate": 1.05,
                "created_at": "2021-03-16 00:25:21-04:00",
                "carbs": None,
                "insulin": None,
                "enteredBy": "Pump (tconnectsync)"
            }
        )

        self.assertEqual(
            NightscoutEntry.basal(
                value=0.95,
                duration_mins=5,
                created_at="2021-03-16 12:25:21-04:00",
                reason="Correction"),
            {
                "eventType": "Temp Basal",
                "reason": "Correction",
                "duration": 5,
                "absolute": 0.95,
                "rate": 0.95,
                "created_at": "2021-03-16 12:25:21-04:00",
                "carbs": None,
                "insulin": None,
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    def test_bolus(self):
        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=7.5,
                carbs=45,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 00:25:21-04:00",
                "carbs": 45,
                "insulin": 7.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=0.5,
                carbs=5,
                created_at="2021-03-16 12:25:21-04:00"),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 12:25:21-04:00",
                "carbs": 5,
                "insulin": 0.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    def test_bolus_with_bg(self):
        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=7.5,
                carbs=45,
                created_at="2021-03-16 00:25:21-04:00",
                bg="123",
                bg_type=NightscoutEntry.SENSOR),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 00:25:21-04:00",
                "carbs": 45,
                "insulin": 7.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)",
                "glucose": "123",
                "glucoseType": "Sensor"
            }
        )

        self.assertEqual(
            NightscoutEntry.bolus(
                bolus=0.5,
                carbs=5,
                created_at="2021-03-16 12:25:21-04:00",
                bg="150",
                bg_type=NightscoutEntry.FINGER),
            {
                "eventType": "Combo Bolus",
                "created_at": "2021-03-16 12:25:21-04:00",
                "carbs": 5,
                "insulin": 0.5,
                "notes": "",
                "enteredBy": "Pump (tconnectsync)",
                "glucose": "150",
                "glucoseType": "Finger"
            }
        )

    def test_bolus_with_bg_invalid_type(self):
        self.assertRaises(InvalidBolusTypeException,
            NightscoutEntry.bolus, 
            bolus=0.5,
            carbs=5,
            created_at="2021-03-16 12:25:21-04:00",
            bg="150")

        self.assertRaises(InvalidBolusTypeException,
            NightscoutEntry.bolus, 
            bolus=0.5,
            carbs=5,
            created_at="2021-03-16 12:25:21-04:00",
            bg="150",
            bg_type="")

        self.assertRaises(InvalidBolusTypeException,
            NightscoutEntry.bolus, 
            bolus=0.5,
            carbs=5,
            created_at="2021-03-16 12:25:21-04:00",
            bg="150",
            bg_type="unknown")

    def test_iob(self):
        self.assertEqual(
            NightscoutEntry.iob(
                iob=2.05,
                created_at="2021-03-16 00:25:21-04:00"),
            {
                "activityType": "tconnect_iob",
                "iob": 2.05,
                "created_at": "2021-03-16 00:25:21-04:00",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    def test_entry(self):
        self.assertEqual(
            NightscoutEntry.entry(
                sgv=152,
                created_at="2021-10-23 22:17:14-04:00"),
            {
                "type": "sgv",
                "sgv": 152,
                "date": 1635041834000,
                "dateString": "2021-10-23T22:17:14-0400",
                "device": "Pump (tconnectsync)",
            }
        )
    
    def test_sitechange(self):
        self.assertEqual(
            NightscoutEntry.sitechange(
                created_at="2021-12-05T00:16:35.058Z",
                reason="reason"),
            {
                "eventType": "Site Change",
                "reason": "reason",
                "notes": "reason",
                "created_at": "2021-12-05T00:16:35.058Z",
                "enteredBy": "Pump (tconnectsync)"
            }
        )
    
    def test_basalsuspension(self):
        self.assertEqual(
            NightscoutEntry.basalsuspension(
                created_at="2021-12-05T00:16:35.058Z",
                reason="reason"),
            {
                "eventType": "Basal Suspension",
                "reason": "reason",
                "notes": "reason",
                "created_at": "2021-12-05T00:16:35.058Z",
                "enteredBy": "Pump (tconnectsync)"
            }
        )

    
    def test_profile_store(self):
        self.assertEqual(
            NightscoutEntry.profile_store(
                profile=Profile(
                    title='A', 
                    active=True, 
                    segments=[
                        ProfileSegment(
                            display_time='Midnight', 
                            time='12:00 AM', 
                            basal_rate=0.8, 
                            correction_factor=30.0, 
                            carb_ratio=6.0, 
                            target_bg_mgdl=110.0), 
                        ProfileSegment(
                            display_time='6:00 AM', 
                            time='6:00 AM', 
                            basal_rate=1.25, 
                            correction_factor=30.0, 
                            carb_ratio=6.0, 
                            target_bg_mgdl=110.0), 
                        ProfileSegment(
                            display_time='11:00 AM', 
                            time='11:00 AM', 
                            basal_rate=1.0, 
                            correction_factor=30.0, 
                            carb_ratio=6.0, 
                            target_bg_mgdl=110.0), 
                        ProfileSegment(
                            display_time='Noon', 
                            time='12:00 PM', 
                            basal_rate=0.8, 
                            correction_factor=30.0, 
                            carb_ratio=6.0, 
                            target_bg_mgdl=110.0)
                    ],
                    calculated_total_daily_basal=21.65, 
                    insulin_duration_min=300, 
                    carbs_enabled=True
                ),
                device_settings=DeviceSettings(
                    low_bg_threshold=80,
                    high_bg_threshold=200,
                    raw_settings={}
                )
            ),
            {
                "dia": 5.0,
                "carbratio": [
                    {
                        "time": "00:00",
                        "timeAsSeconds": 0,
                        "value": 6.0
                    },
                    {
                        "time": "06:00",
                        "timeAsSeconds": 6*60*60,
                        "value": 6.0
                    },
                    {
                        "time": "11:00",
                        "timeAsSeconds": 11*60*60,
                        "value": 6.0
                    },
                    {
                        "time": "12:00",
                        "timeAsSeconds": 12*60*60,
                        "value": 6.0
                    }
                ],

                "carbs_hr": NIGHTSCOUT_PROFILE_CARBS_HR_VALUE,
                "delay": NIGHTSCOUT_PROFILE_DELAY_VALUE,
                "sens": [
                    {
                        "time": "00:00",
                        "timeAsSeconds": 0,
                        "value": 30.0
                    },
                    {
                        "time": "06:00",
                        "timeAsSeconds": 6*60*60,
                        "value": 30.0
                    },
                    {
                        "time": "11:00",
                        "timeAsSeconds": 11*60*60,
                        "value": 30.0
                    },
                    {
                        "time": "12:00",
                        "timeAsSeconds": 12*60*60,
                        "value": 30.0
                    }
                ],
                "basal": [
                    {
                        "time": "00:00",
                        "timeAsSeconds": 0,
                        "value": 0.8
                    },
                    {
                        "time": "06:00",
                        "timeAsSeconds": 6*60*60,
                        "value": 1.25
                    },
                    {
                        "time": "11:00",
                        "timeAsSeconds": 11*60*60,
                        "value": 1.0
                    },
                    {
                        "time": "12:00",
                        "timeAsSeconds": 12*60*60,
                        "value": 0.8
                    }
                ],
                "target_low": [
                    {
                        "time": "00:00",
                        "timeAsSeconds": 0,
                        "value": 80
                    }
                ],
                "target_high": [
                    {
                        "time": "00:00",
                        "timeAsSeconds": 0,
                        "value": 200
                    }
                ],
                "timezone": TIMEZONE_NAME,
                "startDate": "1970-01-01T00:00:00.000Z",
                "units": "mg/dl"
            }
        )


class TestTandemNightscoutTime(unittest.TestCase):
    def test_tandem_to_ns_time(self):
        self.assertEqual(tandem_to_ns_time('12:00 AM'), '00:00')
        self.assertEqual(tandem_to_ns_time('12:30 AM'), '00:30')
        self.assertEqual(tandem_to_ns_time('6:00 AM'), '06:00')
        self.assertEqual(tandem_to_ns_time('6:30 AM'), '06:30')
        self.assertEqual(tandem_to_ns_time('11:30 AM'), '11:30')
        self.assertEqual(tandem_to_ns_time('12:00 PM'), '12:00')
        self.assertEqual(tandem_to_ns_time('12:30 PM'), '12:30')
        self.assertEqual(tandem_to_ns_time('06:30 PM'), '18:30')
        self.assertEqual(tandem_to_ns_time('11:30 PM'), '23:30')

    def test_tandem_to_ns_time_seconds(self):
        self.assertEqual(tandem_to_ns_time_seconds('12:00 AM'), 0)
        self.assertEqual(tandem_to_ns_time_seconds('12:30 AM'), 30*60)
        self.assertEqual(tandem_to_ns_time_seconds('6:00 AM'), 6*60*60)
        self.assertEqual(tandem_to_ns_time_seconds('6:30 AM'), 6*60*60 + 30*60)
        self.assertEqual(tandem_to_ns_time_seconds('11:30 AM'), 11*60*60 + 30*60)
        self.assertEqual(tandem_to_ns_time_seconds('12:00 PM'), 12*60*60)
        self.assertEqual(tandem_to_ns_time_seconds('12:30 PM'), 12*60*60 + 30*60)
        self.assertEqual(tandem_to_ns_time_seconds('06:30 PM'), 12*60*60 + 6*60*60 + 30*60)
        self.assertEqual(tandem_to_ns_time_seconds('11:30 PM'), 12*60*60 + 11*60*60 + 30*60)

if __name__ == '__main__':
    unittest.main()