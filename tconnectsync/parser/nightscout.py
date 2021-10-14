ENTERED_BY = "Pump (tconnectsync)"
BASAL_EVENTTYPE = "Temp Basal"
BOLUS_EVENTTYPE = "Combo Bolus"
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

    @staticmethod
    def bolus(bolus, carbs, created_at, notes=""):
        return {
            "eventType": BOLUS_EVENTTYPE,
			"created_at": created_at,
			"carbs": int(carbs),
			"insulin": float(bolus),
			"notes": notes,
			"enteredBy": ENTERED_BY,
        }

    @staticmethod
    def iob(iob, created_at):
        return {
            "activityType": IOB_ACTIVITYTYPE,
            "iob": float(iob),
            "created_at": created_at,
            "enteredBy": ENTERED_BY
        }