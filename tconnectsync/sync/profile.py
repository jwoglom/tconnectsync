from typing import List, Tuple
import logging
import json
import copy

from ..api import TConnectApi
from ..domain.device_settings import Profile, DeviceSettings
from ..parser.nightscout import NightscoutEntry
from ..secret import PUMP_SERIAL_NUMBER

logger = logging.getLogger(__name__)

def get_pump_profiles(tconnect: TConnectApi, serial_number: int = None) -> Tuple[List[Profile], DeviceSettings]:
    all_devices = tconnect.webui.my_devices()
    if serial_number is None:
        serial_number = PUMP_SERIAL_NUMBER

    if str(serial_number) not in all_devices:
        logger.warn("Could not find entry for provided pump serial number in t:connect device list: %s, received: %s", serial_number, all_devices)
        return []
    
    device = all_devices[str(serial_number)]

    logger.info("Getting profile settings for %s", device)
    device_profiles, device_settings = tconnect.webui.device_settings_from_guid(device.guid)
    logger.debug("device_profiles: %s", device_profiles)
    logger.debug("device_settings: %s", device_settings)

    logger.info("Found pump profiles: %s", ["%s%s" % (profile.title, " (active)" if profile.active else "") for profile in device_profiles])

    return device_profiles, device_settings


"""
Compare pump device and Nightscout profiles, and return a final dictionary of
Nightscout profile objects, with the pump profile settings overriding what is
currently in Nightscout.

ns_profile_obj is the output from NightscoutApi.profiles() and should be the most
recent profile object in mongo.

Returns the new Nightscout profile and whether it was changed.
"""
def compare_profiles(device_profiles: List[Profile], device_settings: DeviceSettings, ns_profile_obj: dict) -> Tuple[bool, dict]:
    device = {profile.title: profile for profile in device_profiles}
    ns = ns_profile_obj.get('store', {})

    logger.info("compare_profiles profile names: device: %s ns: %s", device.keys(), ns.keys())

    new_ns_profile = copy.deepcopy(ns_profile_obj)
    updated_ns_profile = False

    missing_profiles_in_ns = set(device.keys()) - set(ns.keys())
    for profile_name in missing_profiles_in_ns:
        logger.info("Missing %s profile in Nightscout: %s", profile_name, device.get(profile_name))
        pump_configured_profile = device[profile_name]
        ns_translated_profile = NightscoutEntry.profile_store(pump_configured_profile, device_settings)
        logger.info("Will add %s profile to Nightscout: %s", profile_name, ns_translated_profile)
        new_ns_profile['store'][profile_name] = ns_translated_profile
        updated_ns_profile = True

    existent_profiles_in_ns = set(device.keys()) & set(ns.keys())
    for profile_name in existent_profiles_in_ns:
        logger.info("Checking for differences for %s profile between pump and nightscout", profile_name)
        pump_configured_profile = device[profile_name]
        ns_translated_profile = NightscoutEntry.profile_store(pump_configured_profile, device_settings)
        ns_configured_profile = ns[profile_name]

        logger.info("Comparing %s profile from pump: %s to nightscout: %s", profile_name, ns_translated_profile, ns_configured_profile)
        if nightscout_profiles_identical(ns_configured_profile, ns_translated_profile):
            logger.info("Profile %s identical between pump and nightscout", profile_name)
            continue

        logger.info("Profile %s needs update in nightscout: %s", profile_name, ns_translated_profile)
        new_ns_profile['store'][profile_name] = ns_translated_profile
        updated_ns_profile = True

    current_pump_profile = None
    for profile in device_profiles:
        if profile.active:
            current_pump_profile = profile.title

    current_ns_profile = ns_profile_obj.get('defaultProfile')
    if current_pump_profile != current_ns_profile:
        logger.info("Current profile changed: pump: %s nightscout: %s", current_pump_profile, current_ns_profile)
        new_ns_profile['defaultProfile'] = current_pump_profile
        updated_ns_profile = True

    if not updated_ns_profile:
        logger.info("No Nightscout profile changes")
        return False, ns_profile_obj

    logger.info("New Nightscout profile object: %s", new_ns_profile)
    return True, new_ns_profile

def nightscout_profiles_identical(configured: dict, translated: dict) -> bool:
    if json.dumps(configured, sort_keys=True, indent=None) == json.dumps(translated, sort_keys=True, indent=None):
        logger.debug("Initial JSON dump identical")
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

    configured_str = json.loads(json.dumps(configured))
    map_nested_dicts_modify(configured_str, lambda x: str(x))
    translated_str = json.loads(json.dumps(translated))
    map_nested_dicts_modify(translated_str, lambda x: str(x))

    if json.dumps(configured_str, sort_keys=True, indent=None) == json.dumps(translated_str, sort_keys=True, indent=None):
        logger.debug("map_nested_dicts JSON dump identical")
        return True

    logger.debug("profiles not identical")
    return False
