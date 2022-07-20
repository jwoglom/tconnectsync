import datetime
import requests
import hashlib
import time
import urllib.parse
import arrow

from urllib.parse import urljoin

from .api.common import ApiException
from .parser.nightscout import ENTERED_BY

def format_datetime(date):
	return arrow.get(date).strftime('%Y-%m-%d %H:%M:%S')

def time_range(field_name, start_time, end_time):
	arg = ''
	if start_time:
		arg += '&find[%s][$gte]=%s' % (field_name, format_datetime(start_time))
	if end_time:
		arg += '&find[%s][$lte]=%s' % (field_name, format_datetime(end_time))
	return arg


class NightscoutApi:
	def __init__(self, url, secret):
		self.url = url
		self.secret = secret


	def upload_entry(self, ns_format, entity='treatments'):
		r = requests.post(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout upload response: %s" % r.text)

	def delete_entry(self, entity):
		r = requests.delete(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json={}, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout delete response: %s" % r.text)

	def put_entry(self, ns_format, entity):
		r = requests.put(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout put response: %s" % r.text)

	def last_uploaded_entry(self, eventType, time_start=None, time_end=None):
		dateFilter = time_range('created_at', time_start, time_end)
		latest = requests.get(urljoin(self.url, 'api/v1/treatments?count=1&find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[eventType]=' + urllib.parse.quote(eventType) + dateFilter + '&ts=' + str(time.time())), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if latest.status_code != 200:
			raise ApiException(latest.status_code, "Nightscout last_uploaded_entry response: %s" % latest.text)

		j = latest.json()
		if j and len(j) > 0:
			return j[0]
		return None
	
	def last_uploaded_bg_entry(self, time_start=None, time_end=None):
		dateFilter = time_range('dateString', time_start, time_end)
		latest = requests.get(urljoin(self.url, 'api/v1/entries.json?count=1&find[device]=' + urllib.parse.quote(ENTERED_BY) + dateFilter + '&ts=' + str(time.time())), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if latest.status_code != 200:
			raise ApiException(latest.status_code, "Nightscout last_uploaded_bg_entry response: %s" % latest.text)

		j = latest.json()
		if j and len(j) > 0:
			return j[0]
		return None

	def last_uploaded_activity(self, activityType, time_start=None, time_end=None):
		dateFilter = time_range('created_at', time_start, time_end)
		latest = requests.get(urljoin(self.url, 'api/v1/activity?find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[activityType]=' + urllib.parse.quote(activityType) + dateFilter + '&ts=' + str(time.time())), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if latest.status_code != 200:
			raise ApiException(latest.status_code, "Nightscout activity response: %s" % latest.text)

		j = latest.json()
		if j and len(j) > 0:
			return j[0]
		return None

	"""
	Returns general status information about the Nightscout server.
	"""
	def api_status(self):
		status = requests.get(urljoin(self.url, 'api/v1/status.json'), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		})
		if status.status_code != 200:
			raise Exception('HTTP error status code (%d) from Nightscout: %s' % (status.status_code, status.text))
		return status.json()