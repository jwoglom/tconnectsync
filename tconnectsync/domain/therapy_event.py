import arrow

from tconnectsync.domain.bolus import Bolus

from ..secret import TIMEZONE_NAME


def _datetime_parse(date):
    # consistent format with ws2 endpoint
    return arrow.get(date, tzinfo=TIMEZONE_NAME).format("YYYY-MM-DD HH:mm:ssZZ")

class TherapyEvent:
    type = None
    eventDateTime = None
    sourceRecId = None

    def parse(self, json):
        self.type = json['type']
        self.eventDateTime = json['eventDateTime']
        self.sourceRecId = json['sourceRecId']
        self.rawJson = json

class CGMTherapyEvent(TherapyEvent):
    eventID = None
    egv = None
    """
    {
        "eventDateTime": "2022-07-21T00:00:08",
        "eventID": 256,
        "requestDateTime": "0001-01-01T00:00:00",
        "type": "CGM",
        "description": "EGV",
        "sourceRecId": 0,
        "eventTypeId": 0,
        "deviceType": "t:slim X2 Insulin Pump",
        "serialNumber": "xxx",
        "indexId": 0,
        "uploadId": 0,
        "interactive": 0,
        "tempRateId": 0,
        "tempRateCompleted": 0,
        "tempRateActivated": 0,
        "egv": {
            "estimatedGlucoseValue": 174,
            "hypo": 0,
            "belowTarget": 0,
            "withinTarget": 1,
            "aboveTarget": 0,
            "hyper": 0
        }
    },
    """
    @classmethod
    def parse(_, json):
        self = CGMTherapyEvent()
        TherapyEvent.parse(self, json)
        self.eventID = json['eventID']
        self.egv = json['egv']['estimatedGlucoseValue']
        return self

class BGTherapyEvent(TherapyEvent):
    eventID = None
    egv = None
    """
    {   
        'bg': 160, # note in EGV
        'cgmCalibration': 1, # not in EGV
        'description': 'BG',
        'deviceType': 't:slim X2 Insulin Pump',
        'eventDateTime': '2022-08-20T07:25:24',
        'eventTypeId': 16,
        'indexId': 844955,
        'interactive': 0,
        'iob': 0.75,
        'note': {   'active': False,
                'eventId': 0, # different location than EGV
                'eventTypeId': 16,
                'id': 0,
                'indexId': '',
                'sourceRecordId': 0},
        'requestDateTime': '0001-01-01T00:00:00',
        'serialNumber': 'xxx',
        'sourceRecId': 793549667,
        'tempRateActivated': 0,
        'tempRateCompleted': 0,
        'tempRateId': 0,
        'type': 'BG',
        'uploadId': 748700213}
    """    
    @classmethod
    def parse(_, json):
        self = BGTherapyEvent()
        TherapyEvent.parse(self, json)
        self.eventID = json['note']['eventId']
        # This is probably not how we want to provide CGM calibrations to Nightscout,
        # but will just include it as egv data for now to keep the thing from crashing :)
        self.egv = json['bg']
        return self

class BolusTherapyEvent(TherapyEvent):
    bolusRequestOptions = None
    REQUEST_AUTOMATIC = "Automatic Bolus/Correction"
    REQUEST_STANDARD = "Standard"

    bolusType = None
    TYPE_AUTOMATIC = "Automatic Correction"
    TYPE_CARB = "Carb"

    carbSize = None
    correctionBolusSize = None
    foodBolusSize = None
    
    insulinDelivered = None
    insulinRequested = None
    completionDateTime = None

    completionStatus = None
    STATUS_COMPLETED = "Completed"

    eventHistoryReportDetails = None

    standardPercent = None
    sourceRecId = None

    @classmethod
    def parse(_, json):
        self = BolusTherapyEvent()
        TherapyEvent.parse(self, json)
        self.description = json.get("description")
        self.complete = json.get("standard", {}).get("bolusIsComplete")
        self.completion = json.get("standard", {}).get("completionStatusDesc")
        self.request_time = json.get("requestDateTime")
        self.completion_time = json.get("standard", {}).get("insulinDelivered", {}).get("completionDateTime")
        # TODO: separate extended vs standard bolus into separate fields
        self.insulin = json.get("standard", {}).get("insulinDelivered", {}).get("value")
        self.requested_insulin = json.get("standard", {}).get("insulinRequested")
        self.carbs = json.get("carbSize")
        self.bg = json.get("bg")
        self.user_override = json.get("userOverride")
        self.extended_bolus = json.get("bolusRequestOptions") == "Extended"
        if self.extended_bolus and self.complete:
            # TODO(https://github.com/jwoglom/tconnectsync/issues/19): read more extended bolus info
            self.complete = json.get("bolex", {}).get("extendedBolusIsComplete")
            self.completion = json.get("bolex", {}).get("completionStatusDesc")
            self.bolex_completion_time = json.get("bolex", {}).get("insulinDelivered", {}).get("completionDateTime")
            self.bolex_start_time = json.get("bolex", {}).get("bolexStartDateTime")
        else:
            self.bolex_completion_time = ""
            self.bolex_start_time = ""
        return self
    
    def to_bolus(self):
        return Bolus(
            description=self.description,
            complete="1" if self.complete else "0",
            completion=self.completion or "",
            request_time=_datetime_parse(self.request_time),
            completion_time=_datetime_parse(self.completion_time),
            insulin=str(self.insulin),
            requested_insulin=str(self.requested_insulin),
            carbs=str(self.carbs or "0"), # Nightscout expects non-empty carbs
            bg=str(self.bg or ""),
            user_override=str(self.user_override),
            extended_bolus="1" if self.extended_bolus else "0",
            bolex_completion_time=_datetime_parse(self.bolex_completion_time) if self.bolex_completion_time else "",
            bolex_start_time=_datetime_parse(self.bolex_start_time) if self.bolex_start_time else ""
        )

    """
    Correction:
    {
        "actualTotalBolusRequested": 2.9,
        "bg": 254,
        "bolusRequestOptions": "Automatic Bolus/Correction",
        "bolusType": "Automatic Correction",
        "carbSize": 0,
        "correctionBolusSize": 2.9,
        "correctionFactor": 30,
        "declinedCorrection": 0,
        "duration": 0,
        "eventDateTime": "2022-07-21T11:53:08",
        "eventHistoryReportDetails": "CF 1:30 - Carb Ratio 1:0 - Target BG 110",
        "eventHistoryReportEventDesc": "Correction Bolus",
        "foodBolusSize": 0,
        "isQuickBolus": 0,
        "note": {
            "id": 0,
            "indexId": "572946",
            "eventTypeId": 64,
            "sourceRecordId": 0,
            "eventId": 0,
            "active": false
        },
        "requestDateTime": "2022-07-21T11:53:08",
        "standard": {
            "insulinDelivered": {
                "completionDateTime": "2022-07-21T11:55:24",
                "value": 2.9
            },
            "foodDelivered": 0,
            "correctionDelivered": 2.9,
            "insulinRequested": 2.9,
            "completionStatusId": 3,
            "completionStatusDesc": "Completed",
            "bolusIsComplete": 1,
            "bolusRequestId": 3361,
            "bolusCompletionId": 3361
        },
        "standardPercent": 100,
        "targetBG": 110,
        "userOverride": 0,
        "type": "Bolus",
        "description": "Automatic Bolus/Correction",
        "sourceRecId": 1171791787,
        "eventTypeId": 0,
        "indexId": 0,
        "uploadId": 0,
        "interactive": 0,
        "tempRateId": 0,
        "tempRateCompleted": 0,
        "tempRateActivated": 0
    },
    Standard:
    {
        "actualTotalBolusRequested": 4.17,
        "bolusRequestOptions": "Standard",
        "bolusType": "Carb",
        "carbSize": 25,
        "correctionBolusSize": 0,
        "correctionFactor": 30,
        "declinedCorrection": 0,
        "duration": 0,
        "eventDateTime": "2022-07-21T12:27:36",
        "eventHistoryReportDetails": "CF 1:30 - Carb Ratio 1:6 - Target BG 110",
        "eventHistoryReportEventDesc": "Food Bolus",
        "foodBolusSize": 4.17,
        "iob": 2.62,
        "isQuickBolus": 0,
        "note": {
            "id": 0,
            "indexId": "573042",
            "eventTypeId": 64,
            "sourceRecordId": 0,
            "eventId": 0,
            "active": false
        },
        "requestDateTime": "2022-07-21T12:27:36",
        "standard": {
            "insulinDelivered": {
                "completionDateTime": "2022-07-21T12:29:21",
                "value": 4.17
            },
            "foodDelivered": 4.17,
            "correctionDelivered": 0,
            "insulinRequested": 4.17,
            "completionStatusId": 3,
            "completionStatusDesc": "Completed",
            "bolusIsComplete": 1,
            "bolusRequestId": 3362,
            "bolusCompletionId": 3362
        },
        "standardPercent": 100,
        "targetBG": 110,
        "userOverride": 0,
        "type": "Bolus",
        "description": "Standard",
        "sourceRecId": 1171853319,
        "eventTypeId": 0,
        "indexId": 0,
        "uploadId": 0,
        "interactive": 0,
        "tempRateId": 0,
        "tempRateCompleted": 0,
        "tempRateActivated": 0
    },
    Extended bolus incomplete:
    {
        "actualTotalBolusRequested": 0.4,
        "bg": 131,
        "bolex": {
            "size": 0.2,
            "bolexStartDateTime": "2022-08-09T23:20:04",
            "iob": 0,
            "completionStatusId": 0,
            "extendedBolusIsComplete": 0,
            "insulinRequested": 0,
            "bolexCompletionId": 0
        },
        "bolusRequestOptions": "Extended",
        "bolusType": "Carb",
        "carbSize": 0,
        "correctionBolusSize": 0.0,
        "correctionFactor": 30.0,
        "declinedCorrection": 0,
        "duration": 15,
        "eventDateTime": "2022-08-09T23:19:15",
        "eventHistoryReportDetails": "CF 1:30 - Carb Ratio 1:6 - Target BG 110<br/>Override: Pump calculated Bolus = 0.0 units",
        "eventHistoryReportEventDesc": "Food Bolus: 50&#37; Extended 15 mins",
        "foodBolusSize": 0.0,
        "iob": 5.87,
        "isQuickBolus": 0,
        "note": {
            "id": 0,
            "indexId": "631597",
            "eventTypeId": 64,
            "sourceRecordId": 0,
            "eventId": 0,
            "active": false
        },
        "requestDateTime": "2022-08-09T23:19:15",
        "standard": {
            "insulinDelivered": {
                "completionDateTime": "2022-08-09T23:20:04",
                "value": 0.2
            },
            "foodDelivered": 0.0,
            "correctionDelivered": 0.0,
            "insulinRequested": 0.2,
            "completionStatusId": 3,
            "completionStatusDesc": "Completed",
            "bolusIsComplete": 1,
            "bolusRequestId": 3636.0,
            "bolusCompletionId": 3636.0
        },
        "standardPercent": 50.0,
        "targetBG": 110,
        "userOverride": 1,
        "type": "Bolus",
        "description": "Extended 50.00%/0.00",
        "sourceRecId": 1209631944,
        "eventTypeId": 0,
        "indexId": 0,
        "uploadId": 0,
        "interactive": 0,
        "tempRateId": 0,
        "tempRateCompleted": 0,
        "tempRateActivated": 0
    }
    Extended bolus (complete):
    {
        "actualTotalBolusRequested": 0.4,
        "bg": 131,
        "bolex": {
            "size": 0.2,
            "bolexStartDateTime": "2022-08-09T23:20:04",
            "insulinDelivered": {
                "completionDateTime": "2022-08-09T23:35:03",
                "value": 0.2
            },
            "iob": 5.7,
            "completionStatusId": 3.0,
            "completionStatusDesc": "Completed",
            "extendedBolusIsComplete": 1,
            "insulinRequested": 0.2,
            "bolexCompletionId": 16757133
        },
        "bolusRequestOptions": "Extended",
        "bolusType": "Carb",
        "carbSize": 0,
        "correctionBolusSize": 0.0,
        "correctionFactor": 30.0,
        "declinedCorrection": 0,
        "duration": 15,
        "eventDateTime": "2022-08-09T23:19:15",
        "eventHistoryReportDetails": "CF 1:30 - Carb Ratio 1:6 - Target BG 110<br/>Override: Pump calculated Bolus = 0.0 units",
        "eventHistoryReportEventDesc": "Food Bolus: 50&#37; Extended 15 mins",
        "foodBolusSize": 0.0,
        "iob": 5.87,
        "isQuickBolus": 0,
        "note": {
            "id": 0,
            "indexId": "631597",
            "eventTypeId": 64,
            "sourceRecordId": 0,
            "eventId": 0,
            "active": false
        },
        "requestDateTime": "2022-08-09T23:19:15",
        "standard": {
            "insulinDelivered": {
                "completionDateTime": "2022-08-09T23:20:04",
                "value": 0.2
            },
            "foodDelivered": 0.0,
            "correctionDelivered": 0.0,
            "insulinRequested": 0.2,
            "completionStatusId": 3,
            "completionStatusDesc": "Completed",
            "bolusIsComplete": 1,
            "bolusRequestId": 3636.0,
            "bolusCompletionId": 3636.0
        },
        "standardPercent": 50.0,
        "targetBG": 110,
        "userOverride": 1,
        "type": "Bolus",
        "description": "Extended 50.00%/0.00",
        "sourceRecId": 1209631944,
        "eventTypeId": 0,
        "indexId": 0,
        "uploadId": 0,
        "interactive": 0,
        "tempRateId": 0,
        "tempRateCompleted": 0,
        "tempRateActivated": 0
    }
    CGM Calibration (Therapy Event Type BG):
    {   'bg': 160,
        'cgmCalibration': 1,
        'description': 'BG',
        'deviceType': 't:slim X2 Insulin Pump',
        'eventDateTime': '2022-08-20T07:25:24',
        'eventTypeId': 16,
        'indexId': 844955,
        'interactive': 0,
        'iob': 0.75,
        'note': {   'active': False,
                    'eventId': 0,
                    'eventTypeId': 16,
                    'id': 0,
                    'indexId': '',
                    'sourceRecordId': 0},
        'requestDateTime': '0001-01-01T00:00:00',
        'serialNumber': 'xxx',
        'sourceRecId': 793549667,
        'tempRateActivated': 0,
        'tempRateCompleted': 0,
        'tempRateId': 0,
        'type': 'BG',
        'uploadId': 0}
    """

class BasalTherapyEvent(TherapyEvent):
    """
    {
        'basalRate': {
            'duration': 0, 
            'percent': 0, 
            'value': 0.0
        }, 
        'displayInHistory': 0, 
        'eventDateTime': '2022-12-02T00:00:00', 
        'note': {
            'id': 0, 
            'indexId': '16403', 
            'eventTypeId': 90, 
            'sourceRecordId': 0, 
            'eventId': 0, 
            'active': False
        }, 
        'noteDate': {}, 
        'requestDateTime': '0001-01-01T00:00:00', 
        'type': 'Basal', 
        'description': 'NDE', 
        'sourceRecId': xxx, 
        'eventTypeId': 0, 
        'indexId': 0, 
        'uploadId': 0, 
        'interactive': 1, 
        'tempRateId': 0, 
        'tempRateCompleted': 0, 
        'tempRateActivated': 0
    }
    """
    basalRateValue = None
    basalRatePercent = None
    basalRateDuration = None
    eventTime = None


    @classmethod
    def parse(_, json):
        self = CGMTherapyEvent()
        TherapyEvent.parse(self, json)
        if 'basalRate' in json:
            self.basalRateValue = json['basalRate']['value']
            self.basalRatePercent = json['basalRate']['percent']
            self.basalRateDuration = json['basalRate']['duration']
        self.eventTime = json['eventDateTime']
        return self