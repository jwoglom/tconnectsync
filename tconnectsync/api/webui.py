from typing import List
import requests
import urllib
import datetime
import arrow
import time
import logging

from bs4 import BeautifulSoup

from tconnectsync.domain.device_settings import Device, Profile, ProfileSegment
from tconnectsync.util import removesuffix, removeprefix
from tconnectsync.util.constants import MMOLL_TO_MGDL

from .common import base_headers, ApiException

logger = logging.getLogger(__name__)

"""
WebUIScraper contains data that is scraped from the t:connect Web UI and is
not accessible via any known API.
"""
class WebUIScraper:
    BASE_URL = "https://tconnect.tandemdiabetes.com/"

    def __init__(self, controliq):
        self.controliq = controliq

    def needs_relogin(self):
        return self.controliq.needs_relogin()

    def _get(self, endpoint):
        r = self.controliq.loginSession.get(self.BASE_URL + endpoint, headers=base_headers())

        if r.status_code != 200:
            raise ApiException(r.status_code, "WebUIScraper HTTP %s response: %s" % (str(r.status_code), r.text))
        return r


    def get(self, endpoint, tries=0):
        try:
            return self._get(endpoint)
        except ApiException as e:
            logger.warning("Received ApiException in WebUIScraper with endpoint '%s' (tries %d): %s" % (endpoint, tries, e))
            if tries > 0:
                raise ApiException(e.status_code, "WebUIScraper HTTP %d on retry #%d: %s", e.status_code, tries, e)

            # Trigger automatic re-login, and try again once
            if e.status_code == 401:
                logger.info("Performing automatic re-login to ControlIQApi after HTTP 401 for ControlIQApi")
                self.controliq.accessTokenExpiresAt = time.time()
                self.controliq.login(self.controliq._email, self.controliq._password)

                return self.get(endpoint, tries=tries+1)

            if e.status_code == 500:
                return self.get(endpoint, tries=tries+1)

            raise e
    
    def strip(self, txt):
        # Remove errant whitespace between litearl newlines (and literal &nbsp;)
        sep = '\r\n'
        if sep not in txt and '\n' in txt:
            sep = '\n'
        return ' '.join([i.replace('\xa0',' ').strip() for i in txt.strip().split(sep)])

    
    """
    Returns a mapping between pump/device IDs and information about that device,
    including the GUID used for obtaining pump settings.
    """
    def my_devices(self):
        devices = {}
        r = self.get('myaccount/my_devices.aspx')
        soup = BeautifulSoup(r.content, features='lxml')

        for device in soup.select('#content > div.box'):
            device_name = self.strip(device.select_one('.subTitle').text)

            def find_label_value(lbl):
                label = device.find(text=lbl)
                if label:
                    tds = label.parent.parent.parent.select('td')
                    if len(tds) > 1:
                        return self.strip(tds[1].text)
                return None
            
            serial_number = find_label_value('Serial #')
            model_number = find_label_value('Model #')
            status = find_label_value('Status')

            settings_span = device.find(text='View Settings')
            settings_guid = None
            if settings_span:
                settings_a = settings_span.parent.parent
                settings_guid = settings_a.attrs['href'].split('?guid=')[1]
            
            if serial_number:
                devices[serial_number] = Device(
                    name=device_name,
                    model_number=model_number,
                    status=status,
                    guid=settings_guid)
        
        return devices
    
    """
    Returns a parsed representation of a pump's settings.
    Note that pump_guid is NOT the serial number of the pump, and
    should be obtained from my_devices()[str(serial_number)]['guid']
    """
    def device_settings_from_guid(self, pump_guid: str) -> List[Profile]:
        profiles = []
        settings = {}
        r = self.get('myaccount/DeviceSettings.aspx?guid=%s' % pump_guid)
        soup = BeautifulSoup(r.content, features='lxml')
        settings["upload_date"] = self.strip(soup.select_one('#lblUploadDate').text)

        divxml = soup.select_one('#divXML')
        divxmlDiv = divxml.findChild('div')
        for tbl in divxmlDiv.findChildren('table', recursive=False):
            setting_bg = tbl.select_one('.setting_bg')
            if setting_bg and self.strip(setting_bg.text) == 'Profile':
                profiles.append(self._parse_profile_tbl(tbl))
            else:
                settings.update(self._parse_settings_tbl(tbl))
        
        return profiles, settings
    
    def _parse_profile_tbl(self, tbl) -> Profile:
        profile = {}
        profile["title"] = self.strip(tbl.select_one('.setting_title').text)
        profile["active"] = bool(tbl.find(text='Active at the time of upload'))
        profile["segments"] = []

        def parse_basal_rate(rate) -> float:
            return float(removesuffix(rate, ' u/hr'))
        
        def parse_factor(ratio) -> int:
            return parse_bg_mgdl(removeprefix(ratio, '1u:'))

        def parse_ratio(ratio) -> float:
            return float(removesuffix(removeprefix(ratio, '1u:'), ' g'))
        
        def parse_bg_mgdl(bg) -> int:
            if bg.endswith(' mg/dL'):
                return float(removesuffix(bg, ' mg/dL'))
            elif bg.endswith(' mmol/L'):
                return float(removesuffix(bg, ' mmol/L')) * MMOLL_TO_MGDL
            raise ValueError(bg)
        
        def hours_to_mins(text) -> int:
            hrmin = removesuffix(text, " hours")
            hr, min = hrmin.split(":", 1)
            return int(min) + int(hr)*60

        for tr in tbl.select('tr'):
            # Skip header rows
            if tr.select_one('.setting_bg'):
                continue
            if tr.find(text='Start Time'):
                continue
            
            tds = tr.select('td')
            def is_time_row(td):
                txt = self.strip(td.select_one('strong').text)
                return " AM" in txt or " PM" in txt or txt in ("Midnight", "Noon")

            if len(tds) > 0 and is_time_row(tds[0]):
                display_time = self.strip(tds[0].text)
                t = display_time
                if display_time == "Midnight":
                    t = "12:00 AM"
                elif display_time == "Noon":
                    t = "12:00 PM"

                segment = {
                    "display_time": display_time,
                    "time": t,
                    "basal_rate": parse_basal_rate(self.strip(tds[1].text)),
                    "correction_factor": parse_factor(self.strip(tds[2].text)),
                    "carb_ratio": parse_ratio(self.strip(tds[3].text)),
                    "target_bg_mgdl": parse_bg_mgdl(self.strip(tds[4].text))
                }
                profile["segments"].append(ProfileSegment(**segment))
                continue
            
            if tr.find(text='Calculated Total Daily Basal'):
                profile["calculated_total_daily_basal"] = float(removesuffix(self.strip(tds[1].text), " units"))
                continue
            
            # Last row
            if tr.find(text='Duration of Insulin:'):
                lastrow = self.strip(tr.text)
                for part in lastrow.split(' |'):
                    if len(part) < 1:
                        continue

                    key, val = part.split(': ')
                    key = self.strip(key)
                    val = self.strip(val)
                    if key == 'Duration of Insulin':
                        profile["insulin_duration_min"] = hours_to_mins(val)
                    elif key == 'Carbohydrates':
                        profile["carbs_enabled"] = self.strip(val.lower()) == "on"


        return Profile(**profile)

    def _parse_settings_tbl(self, tbl):
        outer_tr = tbl.select('tr')[2]

        settings = {}
        def loop(td, subhead):
            settings[subhead] = {}
            for tr in td.select('.settingstable > tr'):
                if not tr.select_one('strong'):
                    continue

                key = self.strip(tr.select_one('strong').text)

                tds = tr.select('td')
                if len(tds) == 1:
                    subhead = key
                    settings[subhead] = {}
                    continue

                val_text = self.strip(tds[1].text)
                val = {}
                if tds[1].find(text=' - '):
                    val['value'] = False
                elif tds[1].find(text='Off'):
                    val['value'] = False
                    val_text = self.strip(val_text.split('Off', 1)[1])
                elif tds[1].find(text='On'):
                    val['value'] = True
                    val_text = self.strip(val_text.split('On', 1)[1])

                val['text'] = val_text
                settings[subhead][key] = val

        children = outer_tr.findChildren('td', recursive=False)
        loop(children[0], 'Alerts')
        loop(children[1], 'Pump Settings')

        return settings
    
    """
    Wraps a call to my_devices to identify the device GUID from the
    given pump serial, and then returns device_settings_from_guid.
    """
    def device_settings(self, pump_serial):
        devices = self.my_devices()
        if str(pump_serial) in devices.keys():
            dev = devices[str(pump_serial)]
            return self.device_settings_from_guid(dev['guid'])
        
        raise RuntimeError('Unable to find pump with serial number: %s. Known devices: %s' % (pump_serial, devices))








                
