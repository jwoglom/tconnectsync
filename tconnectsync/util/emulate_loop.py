import arrow
from datetime import datetime
from ..nightscout import NightscoutApi
from ..secret import TIMEZONE_NAME
import logging
from . import iobcalc
def UpdateLoop(nightscout,tc,tcd):
	logging.info("UpdatingLoop: Starting")
	logging.info("UpdatingLoop: Getting last temp basal")

	lastbasalrate = nightscout.last_uploaded_entry("Temp Basal")
	battery = nightscout.last_uploaded_devicestatus()


	time = datetime.utcnow().isoformat() + "Z"
	logging.info(f"UpdateLoop: LAST UPDATE TIME: {time}")
	iobs = iobcalc.compute_iob(nightscout.url,iobcalc.hash_api_secret(nightscout.secret))
	loopdata = {
		"device": "tconnectsync",
		"created_at": time,
		"openaps": {
			"iob": {
				"iob": round(iobs['iob'],2),
				"bolusiob": round(iobs['bolusiob'],2),
				"basaliob": round(iobs['basaliob'],2),
				"time": time
			},
			"enacted": {
				"timestamp": time,
				"rate": lastbasalrate['absolute'],
				"duration": 5
				},
			
		},
		"pump": {
			"reservoir": None,
			"battery": {
			"percent": battery['pump']['battery']['percent']
			}
		}
	}
	logging.info(f"UpdateLoop: data {loopdata}")
	nightscout.upload_entry(loopdata,entity='devicestatus')