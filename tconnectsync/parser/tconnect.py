from os import stat
import sys
import arrow
from tconnectsync.domain.bolus import Bolus

from tconnectsync.domain.therapy_event import BolusTherapyEvent, CGMTherapyEvent, BGTherapyEvent, BasalTherapyEvent

try:
    from ..secret import TIMEZONE_NAME
except Exception:
    print('Unable to import parser secrets from secret.py')
    sys.exit(1)

"""
Conversion methods for parsing raw t:connect data into
a more digestable format, which is used internally.
"""
class TConnectEntry:
    BASAL_EVENTS = { 0: "Suspension", 1: "Profile", 2: "TempRate", 3: "Algorithm" }

    @staticmethod
    def _epoch_parse(x):
        # data["x"] is an integer epoch timestamp which, when read as an equivalent timestamp
        # stored in Pacific time (America/Los_Angeles), contains the user's local time, but
        # with the wrong timezone data attached.
        #
        # For example, data["x"] references UTC timestamp 2020-09-01T13:00:00+00:00,
        # which when read in Pacific time is equivalent to 2020-09-01T06:00:00-07:00.
        # However, the user's timezone is Eastern time, so the timezone of America/Los_Angeles
        # is overwritten with America/New_York, resulting in 2020-09-01T06:00:00-04:00, the
        # correct timestamp.
        return arrow.get(x, tzinfo="America/Los_Angeles").replace(tzinfo=TIMEZONE_NAME)
    
    @staticmethod
    def _jsonp_epoch_parse(x):
        return TConnectEntry._epoch_parse(int(x.replace('/Date(', '').replace('-0000)/', '')))

    @staticmethod
    def parse_ciq_basal_entry(data, delivery_type=""):
        time = TConnectEntry._epoch_parse(data["x"])
        duration_mins = data["duration"] / 60
        basal_rate = data["y"]

        return {
            "time": time.format(),
            "delivery_type": delivery_type,
            "duration_mins": duration_mins,
            "basal_rate": basal_rate,
        }
    
    @staticmethod
    def manual_suspension_to_basal_entry(parsedSuspension, seconds):
        duration_mins = seconds / 60
        return {
            "time": parsedSuspension["time"],
            "delivery_type": "%s suspension" % parsedSuspension["suspendReason"],
            "duration_mins": duration_mins,
            "basal_rate": 0.0
        }

    @staticmethod
    def parse_suspension_entry(data):
        time = TConnectEntry._epoch_parse(data["x"])
        return {
            "time": time.format(),
            "continuation": data["continuation"],
            "suspendReason": data["suspendReason"],
        }

    @staticmethod
    def _datetime_parse(date):
        return arrow.get(date, tzinfo=TIMEZONE_NAME)

    @staticmethod
    def parse_cgm_entry(data):
        # EventDateTime is stored in the user's timezone.
        return {
            "time": TConnectEntry._datetime_parse(data["EventDateTime"]).format(),
            "reading": data["Readings (CGM / BGM)"],
            "reading_type": data["Description"],
        }

    @staticmethod
    def parse_iob_entry(data):
        # EventDateTime is stored in the user's timezone.
        return {
            "time": TConnectEntry._datetime_parse(data["EventDateTime"]).format(),
            "iob": data["IOB"],
            "event_id": data["EventID"],
        }

    @staticmethod
    def parse_csv_basal_entry(data, duration_mins=None):
        # EventDateTime is stored in the user's timezone.
        return {
            "time": TConnectEntry._datetime_parse(data["EventDateTime"]).format(),
            "delivery_type": "Unknown",
            "duration_mins": duration_mins,
            "basal_rate": data["BasalRate"],
        }

    @staticmethod
    def parse_bolus_entry(data):
        # All DateTime's are stored in the user's timezone.
        def is_complete(s):
            return s and int(s) == 1

        complete = is_complete(data["ExtendedBolusIsComplete"]) or is_complete(data["BolusIsComplete"])
        extended_bolus = ("extended" in data["Description"].lower())

        return Bolus(**{
            "description": data["Description"],
            "complete": "1" if complete else "",
            "completion": data["CompletionStatusDesc"] if not extended_bolus else data["BolexCompletionStatusDesc"],
            "request_time": TConnectEntry._datetime_parse(data["RequestDateTime"]).format() if not extended_bolus else None,
            "completion_time": TConnectEntry._datetime_parse(data["CompletionDateTime"]).format() if not extended_bolus else None,
            "insulin": data["InsulinDelivered"],
            "requested_insulin": data["ActualTotalBolusRequested"],
            "carbs": data["CarbSize"],
            "bg": data["BG"], # Note: can be empty string for automatic Control-IQ boluses
            "user_override": data["UserOverride"],
            "extended_bolus": "1" if extended_bolus else "",
            # Note: completion time can be empty if the extended bolus is in progress
            "bolex_completion_time": TConnectEntry._datetime_parse(data["BolexCompletionDateTime"]).format() if data["BolexCompletionDateTime"] and complete and extended_bolus else None,
            "bolex_start_time": TConnectEntry._datetime_parse(data["BolexStartDateTime"]).format() if data["BolexStartDateTime"] and complete and extended_bolus else None,
        })
    
    @staticmethod
    def parse_reading_entry(data):
        return {
            "time": TConnectEntry._datetime_parse(data["EventDateTime"]).format(),
            "bg": data["Readings (CGM / BGM)"],
            "type": data["Description"]
        }

    ACTIVITY_EVENTS = { 1: "Sleep", 2: "Exercise", 3: "AutoBolus", 4: "CarbOnly" }

    @staticmethod
    def parse_ciq_activity_event(data):
        if data["eventType"] not in TConnectEntry.ACTIVITY_EVENTS.keys():
            raise UnknownCIQActivityEventException(data)

        time = TConnectEntry._epoch_parse(data["x"])
        return {
            "time": time.format(),
            "duration_mins": data["duration"] / 60,
            "event_type": TConnectEntry.ACTIVITY_EVENTS[data["eventType"]]
        }
    
    BASALSUSPENSION_EVENTS = {
        # site-cart corresponds to a Site or Cartridge change,
        # specifically a Tubing Filled: Norm AND a Cannula Filled: Norm alert.
        # (This means that a typical changing of a cartridge and then a site
        # will result in two consecutive events of this type.)
        "site-cart": "Site/Cartridge Change",

        # alarm corresponds to one of the following:
        # - an Empty Cartridge alarm
        # - a Pump shutdown
        "alarm": "Empty Cartridge/Pump Shutdown",

        # manual corresponds to a Pumping Suspended by User event
        "manual": "User Suspended",

        # temp-profile corresponds to a Basal Rate Change event to 0u/hr
        "temp-profile": "Basal Rate Change"
    }

    BASALSUSPENSION_SKIPPED_EVENTS = {
        # basal-profile events are not very useful; with ControlIQ enabled,
        # Tandem does not show them in the tconnect UI.
        "basal-profile",

        # If an event continues to occur after the date switches over to the next
        # day, then the pump generates a "previous" event. This isn't useful to
        # us, so we skip them.
        "previous",
    }
    @staticmethod
    def parse_basalsuspension_event(data):
        if not data or "SuspendReason" not in data:
            return None

        if data["SuspendReason"] in TConnectEntry.BASALSUSPENSION_SKIPPED_EVENTS:
            return None

        if data["SuspendReason"] not in TConnectEntry.BASALSUSPENSION_EVENTS.keys():
            raise UnknownBasalSuspensionEventException(data)

        time = TConnectEntry._jsonp_epoch_parse(data["EventDateTime"])
        return {
            "time": time.format(),
            "event_type": TConnectEntry.BASALSUSPENSION_EVENTS[data["SuspendReason"]]
        }
    
    # Parses an entry from controliq.therapy_events() and returns a TherapyEvent
    @staticmethod
    def parse_therapy_event(data):
        if data["type"] == "Bolus":
            return BolusTherapyEvent.parse(data)
        elif data["type"] == "CGM":
            return CGMTherapyEvent.parse(data)
        elif data["type"] == "BG":
            return BGTherapyEvent.parse(data)
        elif data["type"] == "Basal":
            return BasalTherapyEvent.parse(data)
        
        raise UnknownTherapyEventException(data)

class UnknownCIQActivityEventException(Exception):
    def __init__(self, data):
        super().__init__("Unknown CIQ activity event type: %s" % data)

class UnknownBasalSuspensionEventException(Exception):
    def __init__(self, data):
        super().__init__("Unknown basal suspension event type: %s" % data)

class UnknownTherapyEventException(Exception):
    def __init__(self, data):
        typ = data["type"]
        super().__init__(f"Unknown therapy event type: {typ} in {data}")
