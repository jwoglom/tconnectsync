import datetime
import requests
import hashlib
import time
import urllib.parse
import arrow
import logging

from urllib.parse import urljoin

from .api.common import ApiException
from .parser.nightscout import ENTERED_BY

def format_datetime(date):
	return arrow.get(date).isoformat()

def time_range(field_name, start_time, end_time, t_to_space=False):
	def fmt(date):
		ret = format_datetime(date)
		if t_to_space:
			return ret.replace('T', ' ')
		return ret
	arg = ''
	if start_time:
		arg += '&find[%s][$gte]=%s' % (field_name, fmt(start_time))
	if end_time:
		arg += '&find[%s][$lte]=%s' % (field_name, fmt(end_time))
	return arg


logger = logging.getLogger(__name__)
class NightscoutApi:
	def __init__(self, url, secret, skip_verify=False):
		self.url = url
		self.secret = secret
		self.verify = False if skip_verify else None


	def upload_entry(self, ns_format, entity='treatments'):
		r = requests.post(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout upload response: %s" % r.text)

	def delete_entry(self, entity):
		r = requests.delete(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json={}, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout delete response: %s" % r.text)

	def put_entry(self, ns_format, entity):
		r = requests.put(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout put response: %s" % r.text)

	def last_uploaded_entry(self, eventType, time_start=None, time_end=None):
		def internal(t_to_space):
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/treatments?count=1&find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[eventType]=' + urllib.parse.quote(eventType) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				raise ApiException(latest.status_code, "Nightscout last_uploaded_entry response: %s" % latest.text)

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None
		
		ret = internal(False)
		if ret is None and (time_start or time_end):
			ret = internal(True)
			if ret is not None:
				logger.warning("last_uploaded_entry with eventType=%s time_start=%s time_end=%s only returned data when timestamps contained a space" % (eventType, time_start, time_end))
		return ret
	
	def last_uploaded_bg_entry(self, time_start=None, time_end=None):
		def internal(t_to_space):
			dateFilter = time_range('dateString', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/entries.json?count=1&find[device]=' + urllib.parse.quote(ENTERED_BY) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				raise ApiException(latest.status_code, "Nightscout last_uploaded_bg_entry response: %s" % latest.text)

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None
		
		ret = internal(False)
		if ret is None and (time_start or time_end):
			ret = internal(True)
			if ret is not None:
				logger.warning("last_uploaded_bg_entry with time_start=%s time_end=%s only returned data when timestamps contained a space" % (time_start, time_end))
		return ret

	def last_uploaded_activity(self, activityType, time_start=None, time_end=None):
		def internal(t_to_space):
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/activity?find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[activityType]=' + urllib.parse.quote(activityType) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				raise ApiException(latest.status_code, "Nightscout activity response: %s" % latest.text)

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None
		
		ret = internal(False)
		if ret is None and (time_start or time_end):
			ret = internal(True)
			if ret is not None:
				logger.warning("last_uploaded_activity with activityType=%s time_start=%s time_end=%s only returned data when timestamps contained a space" % (activityType, time_start, time_end))
		return ret

	"""
	Returns general status information about the Nightscout server.
	"""
	def api_status(self):
		status = requests.get(urljoin(self.url, 'api/v1/status.json'), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if status.status_code != 200:
			raise Exception('HTTP error status code (%d) from Nightscout: %s' % (status.status_code, status.text))
		return status.json()