from enum import Enum

from ...eventparser import events

class EventClass(set, Enum):
    # LidBasalDelivery = every 5min entry
    # LidBasalRateChange = only when basal rate changes
    BASAL = {events.LidBasalDelivery} # , LidBasalRateChange
    BASAL_SUSPENSION = {events.LidPumpingSuspended}
    BASAL_RESUME = {events.LidPumpingResumed}
    ALARM = {events.LidAlarmActivated, events.LidMalfunctionActivated}
    BOLUS = {
        events.LidBolusRequestedMsg1, # carb amount, bg, iob
        events.LidBolusRequestedMsg2, # more robust bolus type
        events.LidBolusRequestedMsg3, # total bolus requested amount
        events.LidBolusCompleted, # final event showing amount delivered
        events.LidBolexCompleted # extended bolus
    }
    CARTRIDGE = {events.LidCartridgeFilled, events.LidCannulaFilled, events.LidTubingFilled}
    CGM_ALERT = {events.LidCgmAlertActivated, events.LidCgmAlertActivatedDex, events.LidCgmAlertActivatedFsl2}
    _CGM_START = {events.LidCgmStartSessionGx, events.LidCgmStartSessionFsl2}
    _CGM_JOIN = {events.LidCgmJoinSessionGx, events.LidCgmJoinSessionG7, events.LidCgmJoinSessionFsl2}
    _CGM_STOP = {events.LidCgmStopSessionGx, events.LidCgmStopSessionG7, events.LidCgmStopSessionFsl2}
    CGM_START_JOIN_STOP = {*_CGM_START, *_CGM_JOIN, *_CGM_STOP}
    CGM_READING = {events.LidCgmDataGxb, events.LidCgmDataG7, events.LidCgmDataFsl2}
    USER_MODE = {events.LidAaUserModeChange}
    DEVICE_STATUS = {events.LidDailyBasal}

    @staticmethod
    def for_event(evt):
        for typ, vals in EventClass.__members__.items():
            if typ.startswith('_'):
                continue
            if type(evt) == type and evt in vals:
                return EventClass.__members__[typ]
            elif type(evt) in vals:
                return EventClass.__members__[typ]
        return None


