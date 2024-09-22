from enum import Enum

from ...eventparser import events

class EventClass(set, Enum):
    # LidBasalDelivery = every 5min entry
    # LidBasalRateChange = only when basal rate changes
    BASAL = {events.LidBasalDelivery} # , LidBasalRateChange
    BASAL_SUSPENSION = {events.LidPumpingSuspended}
    BASAL_RESUME = {events.LidPumpingResumed}
    ALARM = {events.LidAlarmActivated, events.LidMalfunctionActivated}
    BOLUS = {events.LidBolusCompleted, events.LidBolexCompleted}
    CARTRIDGE = {events.LidCartridgeFilled, events.LidCannulaFilled, events.LidTubingFilled}
    CGM_ALERT = {events.LidCgmAlertActivated, events.LidCgmAlertActivatedDex, events.LidCgmAlertActivatedFsl2}
    CGM_START = {events.LidCgmStartSessionGx, events.LidCgmStartSessionFsl2}
    CGM_JOIN = {events.LidCgmJoinSessionGx, events.LidCgmJoinSessionG7, events.LidCgmJoinSessionFsl2}
    CGM_STOP = {events.LidCgmStopSessionGx, events.LidCgmStopSessionG7, events.LidCgmStopSessionFsl2}
    CGM_READING = {events.LidCgmDataGxb, events.LidCgmDataG7, events.LidCgmDataFsl2}
    USER_MODE = {events.LidAaUserModeChange}

    @staticmethod
    def for_event(evt):
        for typ, vals in EventClass.__members__.items():
            if type(evt) == type and evt in vals:
                return EventClass.__members__[typ]
            elif type(evt) in vals:
                return EventClass.__members__[typ]
        return None


