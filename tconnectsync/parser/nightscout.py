import arrow

from ..domain.device_settings import Profile, DeviceSettings
from ..domain.tandemsource.pump_settings import PumpProfile, PumpSettings
from ..secret import TIMEZONE_NAME, NIGHTSCOUT_PROFILE_CARBS_HR_VALUE, NIGHTSCOUT_PROFILE_DELAY_VALUE

ENTERED_BY = "Pump (tconnectsync)"

BASAL_EVENTTYPE = "Temp Basal"
BOLUS_EVENTTYPE = "Combo Bolus"
SITECHANGE_EVENTTYPE = "Site Change"
BASALSUSPENSION_EVENTTYPE = "Basal Suspension"
BASALRESUME_EVENTTYPE = "Basal Resume"
ACTIVITY_EVENTTYPE = "Activity"
EXERCISE_EVENTTYPE = "Exercise"
SLEEP_EVENTTYPE = "Sleep"
ALARM_EVENTTYPE = "Alarm"
CGM_ALERT_EVENTTYPE = "CGM Alert"
CGM_START_EVENTTYPE = "Sensor Start"
CGM_JOIN_EVENTTYPE = "Sensor Start"
CGM_STOP_EVENTTYPE = "Sensor Stop"

IOB_ACTIVITYTYPE = "tconnect_iob"


"""
Conversion methods for parsing data into Nightscout objects.
"""
class NightscoutEntry:
    @staticmethod
    def basal(value, duration_mins, created_at, reason="", pump_event_id=""):
        return {
            "eventType": BASAL_EVENTTYPE,
            "reason": reason,
            "duration": float(duration_mins) if duration_mins else None,
            "absolute": float(value),
            "rate": float(value),
            "created_at": created_at,
            "carbs": None,
            "insulin": None,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    # Note that Nightscout is not consistent and uses "Sensor"/"Finger"
    # for treatment objects, unlike "sgv"/"mbg" for entries
    SENSOR = "Sensor"
    FINGER = "Finger"

    @staticmethod
    def bolus(bolus, carbs, created_at, notes="", bg="", bg_type="", pump_event_id=""):
        data = {
            "eventType": BOLUS_EVENTTYPE,
			"created_at": created_at,
			"carbs": int(carbs) if carbs else 0,
			"insulin": float(bolus),
			"notes": notes,
			"enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }
        if bg:
            if bg_type:
                if bg_type not in (NightscoutEntry.SENSOR, NightscoutEntry.FINGER):
                    raise InvalidBolusTypeException("bg_type: %s (%s)" % (bg_type, data))

                data.update({
                    "glucose": str(bg),
                    "glucoseType": bg_type
                })
            else:
                data.update({
                    "glucose": str(bg)
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
    def entry(sgv, created_at, pump_event_id=""):
        return {
            "type": "sgv",
            "sgv": int(sgv),
            "date": int(1000 * arrow.get(created_at).timestamp()),
            "dateString": arrow.get(created_at).strftime('%Y-%m-%dT%H:%M:%S%z'),
            "device": ENTERED_BY,
            "pump_event_id": pump_event_id,
            # delta, direction are undefined
        }

    @staticmethod
    def sitechange(created_at, reason="", pump_event_id=""):
        return {
            "eventType": SITECHANGE_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def basalsuspension(created_at, reason="", pump_event_id=""):
        return {
            "eventType": BASALSUSPENSION_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def basalresume(created_at, pump_event_id=""):
        return {
            "eventType": BASALRESUME_EVENTTYPE,
            "reason": "Basal resumed",
            "notes": "Basal resumed",
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def alarm(created_at, reason="", pump_event_id=""):
        return {
            "eventType": ALARM_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def cgm_alert(created_at, reason="", pump_event_id=""):
        return {
            "eventType": CGM_ALERT_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def cgm_start(created_at, reason="", pump_event_id=""):
        return {
            "eventType": CGM_START_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def cgm_join(created_at, reason="", pump_event_id=""):
        return {
            "eventType": CGM_JOIN_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def cgm_stop(created_at, reason="", pump_event_id=""):
        return {
            "eventType": CGM_STOP_EVENTTYPE,
            "reason": reason,
            "notes": reason,
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def activity(created_at, duration, reason="", event_type=ACTIVITY_EVENTTYPE, pump_event_id=""):
        return {
            "eventType": event_type,
            "reason": reason,
            "notes": reason,
            "duration": float(duration),
            "created_at": created_at,
            "enteredBy": ENTERED_BY,
            "pump_event_id": pump_event_id
        }

    @staticmethod
    def devicestatus(created_at, batteryVoltage, batteryPercent, pump_event_id=""):
        return {
            "device": ENTERED_BY,
            "created_at": created_at,
            "pump": {
                "clock": created_at,
                "battery": {
                    "voltage": float(batteryVoltage),
                    "percent": int(batteryPercent) if batteryPercent else None,
                    "status": "%.0f%s" % (batteryPercent, '%')
                },
            },
            "pump_event_id": pump_event_id
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



    # TandemSource profile to Nightscout profile store entry
    @staticmethod
    def tandemsource_profile_store(profile: PumpProfile, pump_settings: PumpSettings) -> dict:
        return {
            # insulin duration in hours; Nightscout JS bug requires all top-level fields to be strings
            "dia": "%s" % (profile.insulinDuration / 60),
            "carbratio": list(sorted([
                {
                    "time": minutes_to_ns_time(segment.startTime),
                    "timeAsSeconds": segment.startTime * 60,
                    "value": segment.carbRatio / 1000 # milliunits->units
                } for segment in profile.tDependentSegs if not segment.skip
            ], key=lambda x: x["timeAsSeconds"])),

            "carbs_hr": NIGHTSCOUT_PROFILE_CARBS_HR_VALUE,
            "delay": NIGHTSCOUT_PROFILE_DELAY_VALUE,

            "sens": list(sorted([ # Correction factor / isf
                {
                    "time": minutes_to_ns_time(segment.startTime),
                    "timeAsSeconds": segment.startTime * 60,
                    "value": segment.isf
                } for segment in profile.tDependentSegs if not segment.skip
            ], key=lambda x: x["timeAsSeconds"])),

            "basal": list(sorted([
                {
                    "time": minutes_to_ns_time(segment.startTime),
                    "timeAsSeconds": segment.startTime * 60,
                    "value": segment.basalRate / 1000 # milliunits->units
                } for segment in profile.tDependentSegs
            ], key=lambda x: x["timeAsSeconds"])),

            "target_low": [
                {
                    "time": "00:00",
                    "timeAsSeconds": 0,
                    "value": pump_settings.cgmSettings.lowGlucoseAlert.mgPerDl
                }
            ],
            "target_high": [
                {
                    "time": "00:00",
                    "timeAsSeconds": 0,
                    "value": pump_settings.cgmSettings.highGlucoseAlert.mgPerDl
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

def minutes_to_ns_time(minutes_time: int) -> str:
    hr = minutes_time // 60
    mn = minutes_time % 60

    return "%02d:%02d" % (hr, mn)

class InvalidBolusTypeException(RuntimeError):
    pass

class InvalidTimeException(RuntimeError):
    pass