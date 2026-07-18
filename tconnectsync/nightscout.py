import datetime
import requests
import hashlib
import time
import urllib.parse
import arrow
import logging

from urllib.parse import urljoin
from typing import Optional, Union

from .api.common import ApiException
from .parser.nightscout import ENTERED_BY

# Anything arrow.get() accepts for the date filters / timestamps passed around
# in this module (ISO strings, datetimes, or already-parsed Arrow objects).
DateLike = Union[str, datetime.datetime, arrow.Arrow]

def format_datetime(date: DateLike) -> str:
	return arrow.get(date).isoformat()

def time_range(field_name: str, start_time: Optional[DateLike], end_time: Optional[DateLike], t_to_space: bool = False) -> str:
	def fmt(date: DateLike) -> str:
		ret = format_datetime(date)
		return ret
	arg = ''
	if start_time:
		arg += '&find[%s][$gte]=%s' % (field_name, fmt(start_time))
	if end_time:
		arg += '&find[%s][$lte]=%s' % (field_name, fmt(end_time))
	return arg


logger = logging.getLogger(__name__)
class NightscoutApi:
	def __init__(self, url: str, secret: str, skip_verify: bool = False, ignore_conn_errors: bool = False) -> None:
		self.url = url
		self.secret = secret
		self.verify = False if skip_verify else None
		self.ignore_conn_errors = ignore_conn_errors


	def upload_entry(self, ns_format: dict, entity: str = 'treatments') -> None:
		r = requests.post(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout upload %s response: %s" % (r.status_code, r.text))

	def delete_entry(self, entity: str) -> None:
		r = requests.delete(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json={}, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout delete %s response: %s" % (r.status_code, r.text))

	def put_entry(self, ns_format: dict, entity: str) -> None:
		r = requests.put(urljoin(self.url, 'api/v1/' + entity + '?api_secret=' + self.secret), json=ns_format, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout put %s response: %s" % (r.status_code, r.text))

	def last_uploaded_entry(self, eventType: str, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> Optional[dict]:
		def internal(t_to_space: bool) -> Optional[dict]:
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/treatments?count=1&find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[eventType]=' + urllib.parse.quote(eventType) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				if 'as a valid ISO-8601 date' in latest.text:
					logger.warning("Nightscout last_uploaded_entry %s could not process ISO-8601 date: start=%s end=%s dateFilter=%s" % (eventType, time_start, time_end, dateFilter))
					return None
				raise ApiException(latest.status_code, "Nightscout last_uploaded_entry %s response: %s" % (latest.status_code, latest.text))

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None
		try:
			ret = None
			try:
				ret = internal(False)
			except ApiException as e:
				#logger.warning("last_uploaded_entry with no t_to_space: %s", e)
				ret = None
			if ret is None and (time_start or time_end):
				try:
					ret = internal(True)
				except ApiException as e:
					#logger.warning("last_uploaded_entry with t_to_space: %s", e)
					ret = None
				if ret is not None:
					logger.warning("last_uploaded_entry with eventType=%s time_start=%s time_end=%s only returned data when timestamps contained a space" % (eventType, time_start, time_end))
			return ret
		except requests.exceptions.ConnectionError as e:
			if self.ignore_conn_errors:
				logger.warn('Ignoring ConnectionError because ignore_conn_errors=true', e)
			else:
				raise e
	def get_entries(self, eventType: str, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> Optional[dict]:
		def internal(t_to_space: bool) -> Optional[dict]:
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/treatments?find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[eventType]=' + urllib.parse.quote(eventType) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				if 'as a valid ISO-8601 date' in latest.text:
					logger.warning("Nightscout last_uploaded_entry %s could not process ISO-8601 date: start=%s end=%s dateFilter=%s" % (eventType, time_start, time_end, dateFilter))
					return None
				raise ApiException(latest.status_code, "Nightscout last_uploaded_entry %s response: %s" % (latest.status_code, latest.text))

			j = latest.json()
			if j and len(j) > 0:
				return j
			return None
		try:
			ret = None
			try:
				ret = internal(False)
			except ApiException as e:
				#logger.warning("last_uploaded_entry with no t_to_space: %s", e)
				ret = None
			if ret is None and (time_start or time_end):
				try:
					ret = internal(True)
				except ApiException as e:
					#logger.warning("last_uploaded_entry with t_to_space: %s", e)
					ret = None
				if ret is not None:
					logger.warning("last_uploaded_entry with eventType=%s time_start=%s time_end=%s only returned data when timestamps contained a space" % (eventType, time_start, time_end))
			return ret
		except requests.exceptions.ConnectionError as e:
			if self.ignore_conn_errors:
				logger.warn('Ignoring ConnectionError because ignore_conn_errors=true', e)
			else:
				raise e
	def last_uploaded_bg_entry(self, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> Optional[dict]:
		def internal(t_to_space: bool) -> Optional[dict]:
			dateFilter = time_range('dateString', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/entries.json?count=1&find[device]=' + urllib.parse.quote(ENTERED_BY) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				if 'as a valid ISO-8601 date' in latest.text:
					logger.warning("Nightscout last_uploaded_bg_entry could not process ISO-8601 date: start=%s end=%s dateFilter=%s" % (time_start, time_end, dateFilter))
					return None
				raise ApiException(latest.status_code, "Nightscout last_uploaded_bg_entry %s response: %s" % (latest.status_code, latest.text))

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None

		try:
			ret = internal(False)
			if ret is None and (time_start or time_end):
				ret = internal(True)
				if ret is not None:
					logger.warning("last_uploaded_bg_entry with time_start=%s time_end=%s only returned data when timestamps contained a space" % (time_start, time_end))

			return ret
		except requests.exceptions.ConnectionError as e:
			if self.ignore_conn_errors:
				logger.warn('Ignoring ConnectionError because ignore_conn_errors=true', e)
			else:
				raise e

	def last_uploaded_activity(self, activityType: str, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> Optional[dict]:
		def internal(t_to_space: bool) -> Optional[dict]:
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/activity?find[enteredBy]=' + urllib.parse.quote(ENTERED_BY) + '&find[activityType]=' + urllib.parse.quote(activityType) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				if 'as a valid ISO-8601 date' in latest.text:
					logger.warning("Nightscout activity %s could not process ISO-8601 date: start=%s end=%s dateFilter=%s" % (activityType, time_start, time_end, dateFilter))
					return None
				raise ApiException(latest.status_code, "Nightscout activity %s response: %s" % (latest.status_code, latest.text))

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None

		try:
			ret = internal(False)
			if ret is None and (time_start or time_end):
				ret = internal(True)
				if ret is not None:
					logger.warning("last_uploaded_activity with activityType=%s time_start=%s time_end=%s only returned data when timestamps contained a space" % (activityType, time_start, time_end))
			return ret
		except requests.exceptions.ConnectionError as e:
			if self.ignore_conn_errors:
				logger.warn('Ignoring ConnectionError because ignore_conn_errors=true', e)
			else:
				raise e

	def last_uploaded_devicestatus(self, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> Optional[dict]:
		def internal(t_to_space: bool) -> Optional[dict]:
			dateFilter = time_range('created_at', time_start, time_end, t_to_space=t_to_space)
			latest = requests.get(urljoin(self.url, 'api/v1/devicestatus?find[device]=' + urllib.parse.quote(ENTERED_BY) + dateFilter + '&ts=' + str(time.time())), headers={
				'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
			}, verify=self.verify)
			if latest.status_code != 200:
				if 'as a valid ISO-8601 date' in latest.text:
					logger.warning("Nightscout devicestatus could not process ISO-8601 date: start=%s end=%s dateFilter=%s" % (time_start, time_end, dateFilter))
					return None
				raise ApiException(latest.status_code, "Nightscout devicestatus %s response: %s" % (latest.status_code, latest.text))

			j = latest.json()
			if j and len(j) > 0:
				return j[0]
			return None

		try:
			ret = internal(False)
			if ret is None and (time_start or time_end):
				ret = internal(True)
				if ret is not None:
					logger.warning("devicestatus time_start=%s time_end=%s only returned data when timestamps contained a space" % (time_start, time_end))
			return ret
		except requests.exceptions.ConnectionError as e:
			if self.ignore_conn_errors:
				logger.warn('Ignoring ConnectionError because ignore_conn_errors=true', e)
			else:
				raise e

	"""
	Returns general status information about the Nightscout server.
	"""
	def api_status(self) -> dict:
		status = requests.get(urljoin(self.url, 'api/v1/status.json'), headers={
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if status.status_code != 200:
			raise Exception('HTTP error status code (%d) from Nightscout: %s' % (status.status_code, status.text))
		return status.json()

	"""
	Returns information on the currently configured Nightscout profile data store
	(contains all profiles in Nightscout under one mongo object).
	"""
	def current_profile(self, time_start: Optional[DateLike] = None, time_end: Optional[DateLike] = None) -> dict:
		r = requests.get(urljoin(self.url, 'api/v1/profile/current?api_secret=' + self.secret), json={}, headers={
			'Accept': 'application/json',
			'Content-Type': 'application/json',
			'api-secret': hashlib.sha1(self.secret.encode()).hexdigest()
		}, verify=self.verify)
		if r.status_code != 200:
			raise ApiException(r.status_code, "Nightscout current_profile %s response: %s" % (r.status_code, r.text))
		return r.json()
