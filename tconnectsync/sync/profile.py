from typing import List, Tuple
import logging

from ..api import TConnectApi
from ..domain.device_settings import Profile
from ..secret import PUMP_SERIAL_NUMBER

logger = logging.getLogger(__name__)

def get_pump_profiles(tconnect: TConnectApi) -> List[Profile]:
    all_devices = tconnect.webui.my_devices()
    if str(PUMP_SERIAL_NUMBER) not in all_devices:
        logger.warn("Could not find entry for provided pump serial number in t:connect device list: %s, received: %s", PUMP_SERIAL_NUMBER, all_devices)
        return []
    
    device = all_devices[str(PUMP_SERIAL_NUMBER)]

    logger.info("Getting profile settings for %s", device)
    device_profiles, device_settings = tconnect.webui.device_settings_from_guid(device.guid)
    logger.debug("device_profiles: %s", device_profiles)
    logger.debug("device_settings: %s", device_settings)

    logger.info("Found pump profiles: %s", ["%s%s" % (profile.title, " (active)" if profile.active else "") for profile in device_profiles])

    return device_profiles


"""
Compare pump device and Nightscout profiles, and return a final dictionary of
Nightscout profile objects, with the pump profile settings overriding what is
currently in Nightscout.

ns_profile_obj is the output from NightscoutApi.profiles() and should be the most
recent profile object in mongo.
"""
def compare_profiles(device_profiles: List[Profile], ns_profile_obj: dict):
    device = {profile.title: profile for profile in device_profiles}
    ns = ns_profile_obj.get('store', {})

    logger.info("compare_profiles profile names: device: %s ns: %s", device.keys(), ns.keys())

    missing_profiles_in_ns = set(device.keys()) - set(ns.keys())
    for profile_name in missing_profiles_in_ns:
        logger.info("Missing profile in Nightscout: %s: %s", profile_name, device.get(profile_name))
        pump_configured_profile = device[profile_name]
