from typing import List, Tuple
import logging
import json
import copy
import arrow

from ..api import TConnectApi
from ..domain.device_settings import Profile, DeviceSettings
from ..parser.nightscout import NightscoutEntry
from ..nightscout import NightscoutApi
from ..secret import PUMP_SERIAL_NUMBER, NIGHTSCOUT_PROFILE_UPLOAD_MODE

logger = logging.getLogger(__name__)

def _get_default_serial_number():
    return PUMP_SERIAL_NUMBER

def _get_default_upload_mode():
    return NIGHTSCOUT_PROFILE_UPLOAD_MODE

def get_pump_profiles(tconnect: TConnectApi, serial_number: int = None) -> Tuple[List[Profile], DeviceSettings]:
    all_devices = tconnect.webui.my_devices()
    if serial_number is None:
        serial_number = _get_default_serial_number()

    if str(serial_number) not in all_devices:
        logger.warn("Could not find entry for provided pump serial number in t:connect device list: %s, received: %s", serial_number, all_devices)
        return [], None
    
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

ns_profile_obj is the output from NightscoutApi.current_profile() and should be the most
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
        logger.debug("Checking for differences for %s profile between pump and nightscout", profile_name)
        pump_configured_profile = device[profile_name]
        ns_translated_profile = NightscoutEntry.profile_store(pump_configured_profile, device_settings)
        ns_configured_profile = ns[profile_name]

        logger.debug("Comparing %s profile from pump: %s to nightscout: %s", profile_name, ns_translated_profile, ns_configured_profile)
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

    if not current_pump_profile:
        logger.error('No current pump profile, so skipping profile update: device: %s', device_profiles)
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
    return True, new_ns_profile

def nightscout_profiles_identical(configured: dict, translated: dict) -> bool:
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

def setup_new_profile(ns_profile: dict) -> dict:
    if '_id' in ns_profile:
        del ns_profile['_id']
    
    now = arrow.now().isoformat()
    ns_profile['startDate'] = now
    ns_profile['created_at'] = now

    return ns_profile

def process_profiles(tconnect: TConnectApi, nightscout: NightscoutApi, pretend: bool = False, upload_mode: str = None) -> bool:
    if not upload_mode:
        upload_mode = _get_default_upload_mode()

    logger.debug("Checking for differences between pump and nightscout profiles: %s mode", upload_mode)
    
    ns_profile_obj = nightscout.current_profile()
    pump_profiles, pump_settings = get_pump_profiles(tconnect)
    diff, ns_profile_new = compare_profiles(pump_profiles, pump_settings, ns_profile_obj)

    if not diff:
        logger.info("Pump and Nightscout profiles up to date")
        return False
    
    if upload_mode == 'add':
        profile_to_upload = setup_new_profile(ns_profile_new)
        logger.info("Adding new Nightscout profiles object: %s", profile_to_upload)

        if not pretend:
            nightscout.upload_entry(profile_to_upload, entity='profile')
        return True

    elif upload_mode == 'replace':
        logger.info("Replacing new Nightscout profiles object: %s", ns_profile_new)

        if not pretend:
            nightscout.put_entry(ns_profile_new, entity='profile')
        return True

    else:
        raise RuntimeError('invalid upload_mode: %s' % upload_mode)