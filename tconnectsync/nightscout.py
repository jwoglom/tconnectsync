import sys
import requests
import hashlib
import time
import urllib.parse

from .parser.nightscout import ENTERED_BY

try:
    from .secret import NS_URL, NS_SECRET, TIMEZONE_NAME
except Exception:
    print('Unable to import Nightscout secrets from secret.py')
    sys.exit(1)


def upload_nightscout(ns_format, entity='treatments'):
	upload = requests.post(NS_URL + 'api/v1/' + entity + '?api_secret=' + NS_SECRET, json=ns_format, headers={
		'Accept': 'application/json',
		'Content-Type': 'application/json',
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
	})
	print("Nightscout upload status:", upload.status_code, upload.text)

def delete_nightscout(entity):
	upload = requests.delete(NS_URL + 'api/v1/' + entity + '?api_secret=' + NS_SECRET, json={}, headers={
		'Accept': 'application/json',
		'Content-Type': 'application/json',
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
	})
	print("Nightscout delete status:", upload.status_code, upload.text)

def put_nightscout(ns_format, entity):
	upload = requests.put(NS_URL + 'api/v1/' + entity + '?api_secret=' + NS_SECRET, json=ns_format, headers={
		'Accept': 'application/json',
		'Content-Type': 'application/json',
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
	})
	print("Nightscout put status:", upload.status_code, upload.text)

def last_uploaded_nightscout_entry(eventType):
    latest = requests.get(NS_URL + 'api/v1/treatments?count=1&find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[eventType]=' + urllib.parse.quote(eventType) + '&ts=' + str(time.time()), headers={
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
    })
    j = latest.json()
    if j and len(j) > 0:
        return j[0]
    return None

def last_uploaded_nightscout_activity(activityType):
    latest = requests.get(NS_URL + 'api/v1/activity?find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[activityType]=' + urllib.parse.quote(activityType) + '&ts=' + str(time.time()), headers={
		'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
    })
    j = latest.json()
    if j and len(j) > 0:
        return j[0]
    return None