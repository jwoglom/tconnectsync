import sys
import requests
import hashlib

try:
    from secret import NS_URL, NS_SECRET, TIMEZONE_NAME
except Exception:
    print('Unable to import Nightscout secrets from secret.py')
    sys.exit(1)

ENTERED_BY = "Tandem Pump (tconnectsync)"

class NightscoutEntry:
    @staticmethod
    def basal(value, duration_mins, created_at, reason=""):
        return {
            "eventType": "Temp Basal",
            "reason": reason,
            "duration": int(round(duration_mins)),
            "absolute": float(value),
            "created_at": created_at,
            "carbs": None,
            "insulin": None,
            "enteredBy": ENTERED_BY
        }
    
    @staticmethod
    def bolus(bolus, carbs, created_at, notes=""):
        return {
            "eventType": "Meal Bolus",
			"created_at": created_at,
			"carbs": carbs,
			"insulin": bolus,
			"notes": notes,
			"enteredBy": ENTERED_BY,
        }



def upload_nightscout(ns_format):
	upload = requests.post(NS_URL + 'api/v1/treatments?api_secret=' + NS_SECRET, json=ns_format, headers={
		'Accept': 'application/json',
		'Content-Type': 'application/json',
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
	})
	print("Nightscout upload status:", upload.status_code, upload.text)

