import dataclasses
import unittest
from tconnectsync.domain.bolus import Bolus

from tconnectsync.domain.therapy_event import BolusTherapyEvent, CGMTherapyEvent
from ..util.utilities import replace_with_user_tz

class TestCGMTherapyEvent(unittest.TestCase):
    maxDiff = None
    sampleJson = {
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
    }

    def test_parse_cgm(self):
        e = CGMTherapyEvent.parse(self.sampleJson)
        self.assertEqual(e.type, "CGM")
        self.assertEqual(e.eventDateTime, "2022-07-21T00:00:08")
        self.assertEqual(e.sourceRecId, 0)
        self.assertEqual(e.eventID, 256)
        self.assertEqual(e.egv, 174)

class TestBolusTherapyEvent(unittest.TestCase):
    maxDiff = None
    standardJson = {
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
            "active": False
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
    }

    def test_standard_to_bolus(self):
        e = BolusTherapyEvent.parse(self.standardJson)
        self.assertIsNotNone(e)
        b = e.to_bolus()
        self.assertEqual(dataclasses.asdict(b), dataclasses.asdict(Bolus(
            description="Standard",
            complete="1",
            completion="Completed",
            request_time=replace_with_user_tz("2022-07-21 12:27:36-04:00"),
            completion_time=replace_with_user_tz("2022-07-21 12:29:21-04:00"),
            insulin="4.17",
            requested_insulin="4.17",
            carbs="25",
            bg="",
            user_override="0",
            extended_bolus="0",
            bolex_completion_time="",
            bolex_start_time=""
        )))

    correctionJson = {
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
            "active": False
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
    }

    def test_correction_to_bolus(self):
        e = BolusTherapyEvent.parse(self.correctionJson)
        self.assertIsNotNone(e)
        b = e.to_bolus()
        self.assertEqual(dataclasses.asdict(b), dataclasses.asdict(Bolus(
            description="Automatic Bolus/Correction",
            complete="1",
            completion="Completed",
            request_time=replace_with_user_tz("2022-07-21 11:53:08-04:00"),
            completion_time=replace_with_user_tz("2022-07-21 11:55:24-04:00"),
            insulin="2.9",
            requested_insulin="2.9",
            carbs="0",
            bg="254",
            user_override="0",
            extended_bolus="0",
            bolex_completion_time="",
            bolex_start_time=""
        )))
    
    extendedBolusIncompleteJson = {
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
            "active": False
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

    def test_extended_bolus_incomplete_to_bolus(self):
        e = BolusTherapyEvent.parse(self.extendedBolusIncompleteJson)
        self.assertIsNotNone(e)
        b = e.to_bolus()
        self.assertEqual(dataclasses.asdict(b), dataclasses.asdict(Bolus(
            description="Extended 50.00%/0.00",
            complete="0",
            completion="",
            request_time=replace_with_user_tz("2022-08-09 23:19:15-04:00"),
            completion_time=replace_with_user_tz("2022-08-09 23:20:04-04:00"),
            insulin="0.2",
            requested_insulin="0.2",
            carbs="0",
            bg="131",
            user_override="1",
            extended_bolus="1",
            bolex_completion_time="",
            bolex_start_time=replace_with_user_tz("2022-08-09 23:20:04-04:00")
        )))
    
    extendedBolusJson = {
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
            "active": False
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

    def test_extended_bolus_complete_to_bolus(self):
        e = BolusTherapyEvent.parse(self.extendedBolusJson)
        self.assertIsNotNone(e)
        b = e.to_bolus()
        self.assertEqual(dataclasses.asdict(b), dataclasses.asdict(Bolus(
            description="Extended 50.00%/0.00",
            complete="1",
            completion="Completed",
            request_time=replace_with_user_tz("2022-08-09 23:19:15-04:00"),
            completion_time=replace_with_user_tz("2022-08-09 23:20:04-04:00"),
            insulin="0.2",
            requested_insulin="0.2",
            carbs="0",
            bg="131",
            user_override="1",
            extended_bolus="1",
            bolex_completion_time=replace_with_user_tz("2022-08-09 23:35:03-04:00"),
            bolex_start_time=replace_with_user_tz("2022-08-09 23:20:04-04:00")
        )))


BOLUS_FULL_EXAMPLES = [
    TestBolusTherapyEvent.standardJson,
    TestBolusTherapyEvent.correctionJson,
    TestBolusTherapyEvent.extendedBolusJson
]
