import logging
import arrow
import copy
import json
from typing import Tuple

from ...features import DEFAULT_FEATURES
from ... import features
from ...domain.tandemsource.pump_settings import PumpSettings
from ...parser.nightscout import (
    NightscoutEntry, ENTERED_BY
)
from ...secret import NIGHTSCOUT_PROFILE_UPLOAD_MODE

logger = logging.getLogger(__name__)

def _get_default_upload_mode():
    return NIGHTSCOUT_PROFILE_UPLOAD_MODE

class UpdateProfiles:
    def __init__(self, tconnect, nightscout, tconnect_device_id, pretend, features=DEFAULT_FEATURES):
        self.tconnect = tconnect
        self.nightscout = nightscout
        self.tconnect_device_id = tconnect_device_id
        self.pretend = pretend
        self.features = features

    def enabled(self):
        return features.PROFILES in self.features

    def update(self, pretend):
        upload_mode = _get_default_upload_mode()
        logger.debug("UpdateProfiles: getting Tandem Source profile data")

        all_metadata = self.tconnect.tandemsource.pump_event_metadata()
        pump_meta = None
        for m in all_metadata:
            if m['tconnectDeviceId'] == self.tconnect_device_id:
                pump_meta = m

        if not pump_meta:
            return False

        raw_settings = pump_meta.get("lastUpload", {}).get("settings")
        if not raw_settings:
            return False

        pump_settings = PumpSettings.from_dict(raw_settings)
        logger.info("Current pump settings: %s" % pump_settings)

        ns_profile_obj = self.nightscout.current_profile()
        logger.debug("Current Nightscout profile: %s" % ns_profile_obj)
        if ns_profile_obj is None:
            ns_profile_obj = {}

        logger.info("Current Nightscout profile was authored by: %s" % (ns_profile_obj.get('enteredBy')))

        diff, ns_profile_new = self.compare_profiles(pump_settings, ns_profile_obj)
        if not diff:
            logger.info("Pump and Nightscout profiles up to date")
            return False

        if upload_mode == 'add':
            profile_to_upload = self.setup_new_profile(ns_profile_new)
            logger.info("Adding new Nightscout profiles object: %s", profile_to_upload)

            if not pretend:
                self.nightscout.upload_entry(profile_to_upload, entity='profile')
            return True

        elif upload_mode == 'replace':
            logger.info("Replacing new Nightscout profiles object: %s", ns_profile_new)

            if not pretend:
                self.nightscout.put_entry(ns_profile_new, entity='profile')
            return True

        else:
            raise RuntimeError('invalid upload_mode: %s' % upload_mode)


    """
    Compare pump device and Nightscout profiles, and return a final dictionary of
    Nightscout profile objects, with the pump profile settings overriding what is
    currently in Nightscout.

    ns_profile_obj is the output from NightscoutApi.current_profile() and should be the most
    recent profile object in mongo.

    Returns the new Nightscout profile and whether it was changed.
    """
    def compare_profiles(self, pump_settings: PumpSettings, ns_profile_obj: dict) -> Tuple[bool, dict]:
        device = {profile.name: profile for profile in pump_settings.profiles.profile}
        activeIdp = pump_settings.profiles.activeIdp

        ns = ns_profile_obj.get('store', {})

        logger.debug("compare_profiles profile names: device: %s ns: %s", device.keys(), ns.keys())

        new_ns_profile = copy.deepcopy(ns_profile_obj)
        if not 'store' in new_ns_profile:
            new_ns_profile['store'] = {}
        updated_ns_profile = False

        missing_profiles_in_ns = set(device.keys()) - set(ns.keys())
        for profile_name in missing_profiles_in_ns:
            logger.info("Missing %s profile in Nightscout: %s", profile_name, device.get(profile_name))
            pump_configured_profile = device[profile_name]
            ns_translated_profile = NightscoutEntry.tandemsource_profile_store(pump_configured_profile, pump_settings)
            logger.info("Will add %s profile to Nightscout: %s", profile_name, ns_translated_profile)
            new_ns_profile['store'][profile_name] = ns_translated_profile
            updated_ns_profile = True

        existent_profiles_in_ns = set(device.keys()) & set(ns.keys())
        for profile_name in existent_profiles_in_ns:
            #logger.debug("Checking for differences for %s profile between pump and nightscout", profile_name)
            pump_configured_profile = device[profile_name]
            ns_translated_profile = NightscoutEntry.tandemsource_profile_store(pump_configured_profile, pump_settings)
            ns_configured_profile = ns[profile_name]

            #logger.debug("Comparing %s profile from pump: %s to nightscout: %s", profile_name, ns_translated_profile, ns_configured_profile)
            if self.nightscout_profiles_identical(ns_configured_profile, ns_translated_profile):
                logger.info("Profile %s identical between pump and nightscout", profile_name)
                continue

            logger.info("Profile %s needs update in nightscout: %s", profile_name, ns_translated_profile)
            new_ns_profile['store'][profile_name] = ns_translated_profile
            updated_ns_profile = True

        current_pump_profile = None
        for profile in pump_settings.profiles.profile:
            if profile.idp == activeIdp:
                current_pump_profile = profile.name

        if not current_pump_profile:
            logger.error('No current pump profile, so skipping profile update')
            return False, ns_profile_obj

        current_ns_profile = ns_profile_obj.get('defaultProfile')
        if current_pump_profile != current_ns_profile:
            logger.info("Current profile changed: pump: %s nightscout: %s", current_pump_profile, current_ns_profile)
            new_ns_profile['defaultProfile'] = current_pump_profile
            updated_ns_profile = True

        if not updated_ns_profile:
            logger.info("No Nightscout profile changes")
            return False, ns_profile_obj

        logger.info("New Nightscout profile object: %s", new_ns_profile)
        new_ns_profile['enteredBy'] = ENTERED_BY
        return True, new_ns_profile

    def nightscout_profiles_identical(self, configured: dict, translated: dict) -> bool:
        if configured == translated:
            logger.debug("direct dicts equal")
            return True

        if json.dumps(configured, sort_keys=True, indent=None) == json.dumps(translated, sort_keys=True, indent=None):
            logger.debug("initial JSON dump identical")
            return True

        # convert all JSON values into strings
        def map_nested_dicts_modify(ob, func):
            for k, v in ob.items():
                if isinstance(v, dict):
                    map_nested_dicts_modify(v, func)
                elif isinstance(v, list):
                    map_nested_lists_modify(v, func)
                else:
                    ob[k] = func(v)

        def map_nested_lists_modify(ob, func):
            for i in range(len(ob)):
                v = ob[i]
                if isinstance(v, dict):
                    map_nested_dicts_modify(v, func)
                elif isinstance(v, list):
                    map_nested_lists_modify(v, func)
                else:
                    ob[i] = func(v)

        def to_numeric(x):
            if type(x) in [int, float]:
                return '%f' % x
            try:
                return '%f' % float(x)
            except (ValueError, TypeError):
                return x


        convert_func = lambda x: to_numeric(x)

        configured_str = json.loads(json.dumps(configured))
        map_nested_dicts_modify(configured_str, convert_func)
        translated_str = json.loads(json.dumps(translated))
        map_nested_dicts_modify(translated_str, convert_func)

        if json.dumps(configured_str, sort_keys=True, indent=None) == json.dumps(translated_str, sort_keys=True, indent=None):
            logger.debug("map_nested_dicts JSON dump identical")
            return True

        logger.debug("profiles not identical")
        return False

    def setup_new_profile(self, ns_profile: dict) -> dict:
        if '_id' in ns_profile:
            del ns_profile['_id']

        now = arrow.now().isoformat()
        ns_profile['startDate'] = now
        ns_profile['created_at'] = now

        return ns_profile
