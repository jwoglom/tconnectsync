import arrow

from ..domain.device_settings import Profile, DeviceSettings
from ..secret import TIMEZONE_NAME, NIGHTSCOUT_PROFILE_CARBS_HR_VALUE, NIGHTSCOUT_PROFILE_DELAY_VALUE

ENTERED_BY = "Pump (tconnectsync)"

BASAL_EVENTTYPE = "Temp Basal"
BOLUS_EVENTTYPE = "Combo Bolus"
SITECHANGE_EVENTTYPE = "Site Change"
BASALSUSPENSION_EVENTTYPE = "Basal Suspension"
ACTIVITY_EVENTTYPE = "Activity"
EXERCISE_EVENTTYPE = "Exercise"
SLEEP_EVENTTYPE = "Sleep"

IOB_ACTIVITYTYPE = "tconnect_iob"


"""
Conversion methods for parsing data into Nightscout objects.
"""
class NightscoutEntry:
    @staticmethod
    def basal(value, duration_mins, created_at, reason=""):
        return {
            "eventType": BASAL_EVENTTYPE,
            "reason": reason,
            "duration": float(duration_mins) if duration_mins else None,
            "absolute": float(value),
            "rate": float(value),
            "created_at": created_at,
            "carbs": None,
            "insulin": None,
            "enteredBy": ENTERED_BY
        }

    # Note that Nightscout is not consistent and uses "Sensor"/"Finger"
    # for treatment objects, unlike "sgv"/"mbg" for entries
    SENSOR = "Sensor"
    FINGER = "Finger"

    @staticmethod
    def bolus(bolus, carbs, created_at, notes="", bg="", bg_type=""):
        data = {
            "eventType": BOLUS_EVENTTYPE,
			"created_at": created_at,
			"carbs": int(carbs),
			"insulin": float(bolus),
			"notes": notes,
			"enteredBy": ENTERED_BY,
        }
        if bg:
            if bg_type not in (NightscoutEntry.SENSOR, NightscoutEntry.FINGER):
                raise InvalidBolusTypeException("bg_type: %s (%s)" % (bg_type, data))

            data.update({
                "glucose": str(bg),
                "glucoseType": bg_type
            })
        return data

    @staticmethod
    def iob(iob, created_at):
        return {
            "activityType": IOB_ACTIVITYTYPE,
            "iob": float(iob),
            "created_at": created_at,
            "enteredBy": ENTERED_BY
        }
    
    @staticmethod
    def entry(sgv, created_at):
        return {
            "type": "sgv",
            "sgv": int(sgv),
            "date": int(1000 * arrow.get(created_at).timestamp()),
            "dateString": arrow.get(created_at).strftime('%Y-%m-%dT%H:%M:%S%z'),
            "device": ENTERED_BY,
            # delta, direction are undefined
        }

    @staticmethod
    def sitechange(created_at, reason=""):
        return {
            "eventType": SITECHANGE_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY
        }

    @staticmethod
    def basalsuspension(created_at, reason=""):
        return {
            "eventType": BASALSUSPENSION_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY
        }

    @staticmethod
    def activity(created_at, duration, reason="", event_type=ACTIVITY_EVENTTYPE):
        return {
            "eventType": event_type,
            "reason": reason,
            "notes": reason,
            "duration": float(duration),
            "created_at": created_at,
            "enteredBy": ENTERED_BY
        }
    
    # Tandem-scraped profile to Nightscout profile store entry
    @staticmethod
    def profile_store(profile: Profile, device_settings: DeviceSettings) -> dict:
        return {
            # insulin duration in hours; Nightscout JS bug requires all top-level fields to be strings
            "dia": "%s" % (profile.insulin_duration_min / 60),
            "carbratio": [
                {
                    "time": tandem_to_ns_time(segment.time),
                    "timeAsSeconds": tandem_to_ns_time_seconds(segment.time),
                    "value": segment.carb_ratio
                } for segment in profile.segments
            ],

            "carbs_hr": NIGHTSCOUT_PROFILE_CARBS_HR_VALUE,
            "delay": NIGHTSCOUT_PROFILE_DELAY_VALUE,
            "sens": [ # Correction factor
                {
                    "time": tandem_to_ns_time(segment.time),
                    "timeAsSeconds": tandem_to_ns_time_seconds(segment.time),
                    "value": segment.correction_factor
                } for segment in profile.segments
            ],
            "basal": [
                {
                    "time": tandem_to_ns_time(segment.time),
                    "timeAsSeconds": tandem_to_ns_time_seconds(segment.time),
                    "value": segment.basal_rate
                } for segment in profile.segments
            ],
            "target_low": [
                {
                    "time": "00:00",
                    "timeAsSeconds": 0,
                    "value": device_settings.low_bg_threshold
                }
            ],
            "target_high": [
                {
                    "time": "00:00",
                    "timeAsSeconds": 0,
                    "value": device_settings.high_bg_threshold
                }
            ],
            "timezone": TIMEZONE_NAME, # tconnectsync settings timezone
            "startDate": "1970-01-01T00:00:00.000Z",
            "units": "mg/dl"
        }
        
def tandem_to_ns_time(tandem_time: str) -> str:
    numbers, ampm = tandem_time.split(' ')
    hr, min = numbers.split(':')
    if ampm.lower().strip() == 'am':
        return "%02d:%02d" % (int(hr) % 12, int(min))
    elif ampm.lower().strip() == 'pm':
        return "%02d:%02d" % (12 + (int(hr) % 12), int(min))
    raise InvalidTimeException(tandem_time)

def tandem_to_ns_time_seconds(tandem_time: str) -> int:
    numbers, ampm = tandem_time.split(' ')
    hr, min = numbers.split(':')
    if ampm.lower().strip() == 'am':
        return 60 * (60 * (int(hr) % 12) + int(min))
    elif ampm.lower().strip() == 'pm':
        return 60 * (60 * (12 + (int(hr) % 12)) + int(min))
    raise InvalidTimeException(tandem_time)

class InvalidBolusTypeException(RuntimeError):
    pass

class InvalidTimeException(RuntimeError):
    pass