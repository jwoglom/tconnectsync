import arrow
import logging

logger = logging.getLogger(__name__)

class ChooseDevice:
    def __init__(self, secret, tconnect):
        self.secret = secret
        self.tconnect = tconnect

    def choose(self):
        tconnect = self.tconnect

        pumpEventMetadata = tconnect.tandemsource.pump_event_metadata()

        serialNumberToPump = {p['serialNumber']: p for p in pumpEventMetadata}
        logger.info(f'Found {len(serialNumberToPump)} pumps: {serialNumberToPump.keys()}')

        tconnectDevice = None

        if self.secret.PUMP_SERIAL_NUMBER and str(self.secret.PUMP_SERIAL_NUMBER) != '11111111':
            if not str(self.secret.PUMP_SERIAL_NUMBER) in serialNumberToPump.keys():
                raise InvalidSerialNumber(f'Serial number {self.secret.PUMP_SERIAL_NUMBER} is not present on your account: choose one of {", ".join(serialNumberToPump.keys())}')

            tconnectDevice = serialNumberToPump[str(self.secret.PUMP_SERIAL_NUMBER)]

            # Warn if pump is stale (no events in >3 days)
            try:
                max_event_date = arrow.get(tconnectDevice["maxDateWithEvents"])
                age_days = (arrow.utcnow() - max_event_date).days

                if age_days > 3:
                    logger.warning(
                        f"The selected pump (serial {tconnectDevice['serialNumber']}) has no events in the last {age_days} days "
                        f"(last seen: {tconnectDevice['maxDateWithEvents']}). "
                        "You may have switched to a new pump. Consider removing or updating PUMP_SERIAL_NUMBER in your config."
                    )
            except Exception as e:
                logger.debug(f"Could not parse maxDateWithEvents to check for staleness: {e}")

            logger.info(f'Using pump with serial: {tconnectDevice["serialNumber"]} (tconnectDeviceId: {tconnectDevice["tconnectDeviceId"]}, last seen: {tconnectDevice["maxDateWithEvents"]})')
        else:
            maxDateSeen = None
            for pump in pumpEventMetadata:
                if not tconnectDevice:
                    tconnectDevice = pump
                    maxDateSeen = arrow.get(pump['maxDateWithEvents'])
                else:
                    if arrow.get(pump['maxDateWithEvents']) > maxDateSeen:
                        maxDateSeen = arrow.get(pump['maxDateWithEvents'])
                        tconnectDevice = pump

            logger.info(f'Using most recent pump (serial: {tconnectDevice["serialNumber"]}, tconnectDeviceId: {tconnectDevice["tconnectDeviceId"]}, last seen: {tconnectDevice["maxDateWithEvents"]})')


        return tconnectDevice



class InvalidSerialNumber(RuntimeError):
    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, super().__str__())