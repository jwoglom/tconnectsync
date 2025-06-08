from tconnectsync.domain.device_settings import Profile, ProfileSegment, DeviceSettings
from tconnectsync.secret import NIGHTSCOUT_PROFILE_CARBS_HR_VALUE, NIGHTSCOUT_PROFILE_DELAY_VALUE, TIMEZONE_NAME


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
    "dia": "5.0",
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
    "dia": "5.0",
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