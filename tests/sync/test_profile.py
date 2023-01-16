#!/usr/bin/env python3

import unittest
from typing import Dict
import copy

from tconnectsync.sync.profile import get_pump_profiles, compare_profiles
from tconnectsync.domain.device_settings import Profile, ProfileSegment, DeviceSettings
from tconnectsync.secret import NIGHTSCOUT_PROFILE_CARBS_HR_VALUE, NIGHTSCOUT_PROFILE_DELAY_VALUE, TIMEZONE_NAME

from ..parser.test_tconnect import TestTConnectEntryReading

DEVICE_PROFILE_A = Profile(
    title='A', 
    active=False, 
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
)

DEVICE_PROFILE_B = Profile(
    title='B', 
    active=False, 
    segments=[
        ProfileSegment(
            display_time='Midnight', 
            time='12:00 AM', 
            basal_rate=0.8, 
            correction_factor=30.0, 
            carb_ratio=12.0, 
            target_bg_mgdl=110.0), 
        ProfileSegment(
            display_time='6:00 AM', 
            time='6:00 AM', 
            basal_rate=1.25, 
            correction_factor=30.0, 
            carb_ratio=12.0, 
            target_bg_mgdl=110.0), 
        ProfileSegment(
            display_time='11:00 AM', 
            time='11:00 AM', 
            basal_rate=1.0, 
            correction_factor=30.0, 
            carb_ratio=12.0, 
            target_bg_mgdl=110.0), 
        ProfileSegment(
            display_time='Noon', 
            time='12:00 PM', 
            basal_rate=0.9, 
            correction_factor=30.0, 
            carb_ratio=12.0, 
            target_bg_mgdl=110.0)
    ],
    calculated_total_daily_basal=22.85, 
    insulin_duration_min=300, 
    carbs_enabled=True
)

DEVICE_SETTINGS = DeviceSettings(
    low_bg_threshold=80,
    high_bg_threshold=200,
    raw_settings={}
)

NS_PROFILE_A = {
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

NS_PROFILE_B = {
    "dia": 5.0,
    "carbratio": [
        {
            "time": "00:00",
            "timeAsSeconds": 0,
            "value": 12.0
        },
        {
            "time": "06:00",
            "timeAsSeconds": 6*60*60,
            "value": 12.0
        },
        {
            "time": "11:00",
            "timeAsSeconds": 11*60*60,
            "value": 12.0
        },
        {
            "time": "12:00",
            "timeAsSeconds": 12*60*60,
            "value": 12.0
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
            "value": 0.9
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

NS_PROFILE_STORE = {
    'A': NS_PROFILE_A,
    'B': NS_PROFILE_B
}

def build_ns_profile(profiles: Dict[str, dict], current_profile: str) -> dict:
    return copy.deepcopy({
        "store": profiles,
        "defaultProfile": current_profile,
        "startDate": "1970-01-01T00:00:00.000Z",
        "mills": 0,
        "units": "mg/dl",
    })

class TestCompareProfiles(unittest.TestCase):
    maxDiff = None
    def test_compare_profiles_identical_a(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )

        self.assertFalse(changed)
        self.assertDictEqual(ns_profile_obj, new_profiles)

        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_identical_b(self):
        pump_profiles = [DEVICE_PROFILE_B.activeProfile()]
        ns_profile_obj = build_ns_profile({'B': NS_PROFILE_B}, 'B')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )

        self.assertFalse(changed)
        self.assertDictEqual(ns_profile_obj, new_profiles)

        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_extra_profile_in_nightscout_ignored(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A, 'B': NS_PROFILE_B}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )

        self.assertFalse(changed)
        self.assertDictEqual(ns_profile_obj, new_profiles)

        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_current_nightscout_profile_changed(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A, 'B': NS_PROFILE_B}, 'B')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )

        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)

        ns_profile_obj['defaultProfile'] = 'A'
        self.assertDictEqual(ns_profile_obj, new_profiles)
        
        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_new_pump_profile_added(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile(), DEVICE_PROFILE_B]
        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )
        
        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)
        
        ns_profile_obj['store']['B'] = new_profiles['store']['B']
        self.assertDictEqual(ns_profile_obj, new_profiles)

        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_new_pump_profile_added_and_active(self):
        pump_profiles = [DEVICE_PROFILE_A, DEVICE_PROFILE_B.activeProfile()]
        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )
        
        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)
        
        ns_profile_obj['store']['B'] = new_profiles['store']['B']
        ns_profile_obj['defaultProfile'] = 'B'
        self.assertDictEqual(ns_profile_obj, new_profiles)
        
        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_existing_profile_edited_basal(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        pump_profiles[0].segments[0].basal_rate = 0.1

        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )
        
        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)
        
        ns_profile_obj['store']['A']['basal'][0]['value'] = 0.1
        self.assertDictEqual(ns_profile_obj, new_profiles)
        
        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_existing_profile_edited_new_chunk(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        pump_profiles[0].segments.append(ProfileSegment(
            display_time='06:00 PM', 
            time='06:00 PM', 
            basal_rate=0.7, 
            correction_factor=30.0, 
            carb_ratio=6.0,
            target_bg_mgdl=110.0)
        )

        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )
        
        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)
        
        ns_profile_obj['store']['A']['basal'].append({'time': '18:00', 'timeAsSeconds': 18*60*60, 'value': 0.7})
        ns_profile_obj['store']['A']['carbratio'].append({'time': '18:00', 'timeAsSeconds': 18*60*60, 'value': 6})
        ns_profile_obj['store']['A']['sens'].append({'time': '18:00', 'timeAsSeconds': 18*60*60, 'value': 30})
        self.assertDictEqual(ns_profile_obj, new_profiles)
        
        self.ensure_stabilized(pump_profiles, new_profiles)

    def test_compare_profiles_existing_profile_edited_removed_chunk(self):
        pump_profiles = [DEVICE_PROFILE_A.activeProfile()]
        pump_profiles[0].segments.pop()

        ns_profile_obj = build_ns_profile({'A': NS_PROFILE_A}, 'A')

        changed, new_profiles = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            ns_profile_obj
        )
        
        self.assertTrue(changed)
        self.assertNotEqual(ns_profile_obj, new_profiles)
        
        ns_profile_obj['store']['A']['basal'].pop()
        ns_profile_obj['store']['A']['carbratio'].pop()
        ns_profile_obj['store']['A']['sens'].pop()
        self.assertDictEqual(ns_profile_obj, new_profiles)
        
        self.ensure_stabilized(pump_profiles, new_profiles)
    
    def ensure_stabilized(self, pump_profiles, new_profiles):
        changed, _ = compare_profiles(
            pump_profiles,
            DEVICE_SETTINGS,
            new_profiles
        )
        self.assertFalse(changed, 'did not stabilize')

if __name__ == '__main__':
    unittest.main()