#!/usr/bin/env python3

import unittest
import itertools

from .fake import WS2Api

from tconnectsync.api.common import ApiException

class TestWS2Api(unittest.TestCase):
    def fake_get_with_http_500(self, num_times):
        tries = 0
        def fake_get(endpoint, **kwargs):
            nonlocal tries, num_times
            if "therapytimeline2csv" in endpoint:
                if tries < num_times:
                    tries += 1
                    raise ApiException(500, "fake HTTP 500")

                return ""
            raise NotImplementedError

        return fake_get

    def test_therapy_timeline_csv_works_after_two_retries(self):
        ws2 = WS2Api()

        ws2.get = self.fake_get_with_http_500(2)

        self.assertEqual(
            ws2.therapy_timeline_csv('2021-04-01', '2021-04-02'),
            {
                "readingData": [],
                "iobData": [],
                "basalData": [],
                "bolusData": []
            })

    def test_therapy_timeline_csv_fails_after_three_retries(self):
        ws2 = WS2Api()

        ws2.get = self.fake_get_with_http_500(3)

        self.assertRaises(ApiException, ws2.therapy_timeline_csv, '2021-04-01', '2021-04-02')

    RAW_DATA_HEADER = """Tandem Diabetes Care Inc.
t:connect Therapy Timeline Data Export
Patient Name, Sample Name
Patient DOB, 1/1/1990
Report Generated On, 4/24/2021 7:50:04 PM
"""
    RAW_DATA_CGM = """DeviceType,SerialNumber,Description,EventDateTime,Readings (CGM / BGM)
"t:slim X2 Insulin Pump","11111111","EGV","2021-04-01T00:01:33","235",
"t:slim X2 Insulin Pump","11111111","EGV","2021-04-01T00:06:33","230",
"t:slim X2 Insulin Pump","11111111","EGV","2021-04-02T23:31:36","181",
"""
    RAW_DATA_IOB = """Type,EventID,EventDateTime,IOB
"IOB","81","2021-04-01T00:00:19","13.24"
"IOB","9","2021-04-01T00:03:12","12.80"
"IOB","81","2021-04-02T23:58:19","4.25"
"""
    RAW_DATA_BOLUS = """Type,Description,BG,IOB,BolusRequestID,BolusCompletionID,CompletionDateTime,InsulinDelivered,FoodDelivered,CorrectionDelivered,CompletionStatusID,CompletionStatusDesc,BolusIsComplete,BolexCompletionID,BolexSize,BolexStartDateTime,BolexCompletionDateTime,BolexInsulinDelivered,BolexIOB,BolexCompletionStatusID,BolexCompletionStatusDesc,ExtendedBolusIsComplete,EventDateTime,RequestDateTime,BolusType,BolusRequestOptions,StandardPercent,Duration,CarbSize,UserOverride,TargetBG,CorrectionFactor,FoodBolusSize,CorrectionBolusSize,ActualTotalBolusRequested,IsQuickBolus,EventHistoryReportEventDesc,EventHistoryReportDetails,NoteID,IndexID,Note
"Bolus","Standard/Correction","141",,"7001.000","7001.000","2021-04-01T12:58:26","13.53","12.50","1.03","3","Completed","1",,,,,,,,,,"2021-04-01T12:53:36","2021-04-01T12:53:36","Carb","Standard/Correction","100.00","0","75","0","110","30.00","12.50","1.03","13.53","0","0","Correction & Food Bolus","CF 1:30 - Carb Ratio 1:6 - Target BG 110","0","1181649","",
"Bolus","Standard","131","0.71","7003.000","7003.000","2021-04-01T16:03:25","1.50","0.00","0.00","3","Completed","1",,,,,,,,,,"2021-04-01T16:02:04","2021-04-01T16:02:04","Carb","Standard","100.00","0","0","1","110","30.00","0.00","0.00","1.50","0","0","Food Bolus","CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.0 units","0","1182026","",
"Bolus","Standard/Correction","168","1.71","7004.000","7004.000","2021-04-01T16:24:08","2.00","0.00","0.00","3","Completed","1",,,,,,,,,,"2021-04-01T16:22:21","2021-04-01T16:22:21","Carb","Standard/Correction","100.00","0","0","1","110","30.00","0.00","0.22","2.00","0","0","Correction & Food Bolus","CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.2 units","0","1182082","",
"Bolus","Standard","220","3.98","7032.000","7032.000","2021-04-02T23:16:24","2.50","0.00","0.00","3","Completed","1",,,,,,,,,,"2021-04-02T23:14:33","2021-04-02T23:14:33","Carb","Standard","100.00","0","0","1","110","30.00","0.00","0.00","2.50","0","0","Food Bolus","CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.0 units","0","1185846","",
"""

    RAW_DATA_FULL = RAW_DATA_HEADER + "\n" + RAW_DATA_CGM + "\n" + RAW_DATA_IOB + "\n" + RAW_DATA_BOLUS

    PARSED_DATA = {
        'readingData': [
            {"DeviceType": "t:slim X2 Insulin Pump", "SerialNumber": "11111111", "Description": "EGV", "EventDateTime": "2021-04-01T00:01:33", "Readings (CGM / BGM)": "235"},
            {"DeviceType": "t:slim X2 Insulin Pump", "SerialNumber": "11111111", "Description": "EGV", "EventDateTime": "2021-04-01T00:06:33", "Readings (CGM / BGM)": "230"},
            {"DeviceType": "t:slim X2 Insulin Pump", "SerialNumber": "11111111", "Description": "EGV", "EventDateTime": "2021-04-02T23:31:36", "Readings (CGM / BGM)": "181"}
        ],
        'iobData': [
            {"Type": "IOB", "EventID": "81", "EventDateTime": "2021-04-01T00:00:19", "IOB": "13.24"},
            {"Type": "IOB", "EventID": "9", "EventDateTime": "2021-04-01T00:03:12", "IOB": "12.80"},
            {"Type": "IOB", "EventID": "81", "EventDateTime": "2021-04-02T23:58:19", "IOB": "4.25"},
        ],
        'basalData': [],
        'bolusData': [
            {"Type": "Bolus", "Description": "Standard/Correction", "BG": "141", "IOB": "", "BolusRequestID": "7001.000", "BolusCompletionID": "7001.000", "CompletionDateTime": "2021-04-01T12:58:26", "InsulinDelivered": "13.53", "FoodDelivered": "12.50", "CorrectionDelivered": "1.03", "CompletionStatusID": "3", "CompletionStatusDesc": "Completed", "BolusIsComplete": "1", "BolexCompletionID": "", "BolexSize": "", "BolexStartDateTime": "", "BolexCompletionDateTime": "", "BolexInsulinDelivered": "", "BolexIOB": "", "BolexCompletionStatusID": "", "BolexCompletionStatusDesc": "", "ExtendedBolusIsComplete": "", "EventDateTime": "2021-04-01T12:53:36", "RequestDateTime": "2021-04-01T12:53:36", "BolusType": "Carb", "BolusRequestOptions": "Standard/Correction", "StandardPercent": "100.00", "Duration": "0", "CarbSize": "75", "UserOverride": "0", "TargetBG": "110", "CorrectionFactor": "30.00", "FoodBolusSize": "12.50", "CorrectionBolusSize": "1.03", "ActualTotalBolusRequested": "13.53", "IsQuickBolus": "0", "EventHistoryReportEventDesc": "0", "EventHistoryReportDetails": "Correction & Food Bolus", "NoteID": "CF 1:30 - Carb Ratio 1:6 - Target BG 110", "IndexID": "0", "Note": "1181649"},
            {"Type": "Bolus", "Description": "Standard", "BG": "131", "IOB": "0.71", "BolusRequestID": "7003.000", "BolusCompletionID": "7003.000", "CompletionDateTime": "2021-04-01T16:03:25", "InsulinDelivered": "1.50", "FoodDelivered": "0.00", "CorrectionDelivered": "0.00", "CompletionStatusID": "3", "CompletionStatusDesc": "Completed", "BolusIsComplete": "1", "BolexCompletionID": "", "BolexSize": "", "BolexStartDateTime": "", "BolexCompletionDateTime": "", "BolexInsulinDelivered": "", "BolexIOB": "", "BolexCompletionStatusID": "", "BolexCompletionStatusDesc": "", "ExtendedBolusIsComplete": "", "EventDateTime": "2021-04-01T16:02:04", "RequestDateTime": "2021-04-01T16:02:04", "BolusType": "Carb", "BolusRequestOptions": "Standard", "StandardPercent": "100.00", "Duration": "0", "CarbSize": "0", "UserOverride": "1", "TargetBG": "110", "CorrectionFactor": "30.00", "FoodBolusSize": "0.00", "CorrectionBolusSize": "0.00", "ActualTotalBolusRequested": "1.50", "IsQuickBolus": "0", "EventHistoryReportEventDesc": "0", "EventHistoryReportDetails": "Food Bolus", "NoteID": "CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.0 units", "IndexID": "0", "Note": "1182026"},
            {"Type": "Bolus", "Description": "Standard/Correction", "BG": "168", "IOB": "1.71", "BolusRequestID": "7004.000", "BolusCompletionID": "7004.000", "CompletionDateTime": "2021-04-01T16:24:08", "InsulinDelivered": "2.00", "FoodDelivered": "0.00", "CorrectionDelivered": "0.00", "CompletionStatusID": "3", "CompletionStatusDesc": "Completed", "BolusIsComplete": "1", "BolexCompletionID": "", "BolexSize": "", "BolexStartDateTime": "", "BolexCompletionDateTime": "", "BolexInsulinDelivered": "", "BolexIOB": "", "BolexCompletionStatusID": "", "BolexCompletionStatusDesc": "", "ExtendedBolusIsComplete": "", "EventDateTime": "2021-04-01T16:22:21", "RequestDateTime": "2021-04-01T16:22:21", "BolusType": "Carb", "BolusRequestOptions": "Standard/Correction", "StandardPercent": "100.00", "Duration": "0", "CarbSize": "0", "UserOverride": "1", "TargetBG": "110", "CorrectionFactor": "30.00", "FoodBolusSize": "0.00", "CorrectionBolusSize": "0.22", "ActualTotalBolusRequested": "2.00", "IsQuickBolus": "0", "EventHistoryReportEventDesc": "0", "EventHistoryReportDetails": "Correction & Food Bolus", "NoteID": "CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.2 units", "IndexID": "0", "Note": "1182082"},
            {"Type": "Bolus", "Description": "Standard", "BG": "220", "IOB": "3.98", "BolusRequestID": "7032.000", "BolusCompletionID": "7032.000", "CompletionDateTime": "2021-04-02T23:16:24", "InsulinDelivered": "2.50", "FoodDelivered": "0.00", "CorrectionDelivered": "0.00", "CompletionStatusID": "3", "CompletionStatusDesc": "Completed", "BolusIsComplete": "1", "BolexCompletionID": "", "BolexSize": "", "BolexStartDateTime": "", "BolexCompletionDateTime": "", "BolexInsulinDelivered": "", "BolexIOB": "", "BolexCompletionStatusID": "", "BolexCompletionStatusDesc": "", "ExtendedBolusIsComplete": "", "EventDateTime": "2021-04-02T23:14:33", "RequestDateTime": "2021-04-02T23:14:33", "BolusType": "Carb", "BolusRequestOptions": "Standard", "StandardPercent": "100.00", "Duration": "0", "CarbSize": "0", "UserOverride": "1", "TargetBG": "110", "CorrectionFactor": "30.00", "FoodBolusSize": "0.00", "CorrectionBolusSize": "0.00", "ActualTotalBolusRequested": "2.50", "IsQuickBolus": "0", "EventHistoryReportEventDesc": "0", "EventHistoryReportDetails": "Food Bolus", "NoteID": "CF 1:30 - Carb Ratio 1:6 - Target BG 110 | Override: Pump calculated Bolus = 0.0 units", "IndexID": "0", "Note": "1185846"}
        ]
    }

    def test_therapy_timeline_csv_parses_full(self):
        ws2 = WS2Api()
        ws2.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        rawData = self.RAW_DATA_FULL

        def fake_get(endpoint, **kwargs):
            nonlocal rawData
            if endpoint == 'therapytimeline2csv/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/2021-04-01/2021-04-02?format=csv':
                return rawData

        ws2.get = fake_get

        tt = ws2.therapy_timeline_csv('2021-04-01', '2021-04-02')

        self.assertDictEqual(tt, self.PARSED_DATA)

    def test_therapy_timeline_csv_parses_random_order(self):
        ws2 = WS2Api()
        ws2.userGuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

        rawData = ""

        def fake_get(endpoint, **kwargs):
            nonlocal rawData
            if endpoint == 'therapytimeline2csv/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/2021-04-01/2021-04-02?format=csv':
                return rawData

        ws2.get = fake_get

        # Randomize the order of all sections
        for i in itertools.permutations([self.RAW_DATA_HEADER, self.RAW_DATA_CGM, self.RAW_DATA_IOB, self.RAW_DATA_BOLUS], 4):
            rawData = "\n".join(i)

            tt = ws2.therapy_timeline_csv('2021-04-01', '2021-04-02')
            self.assertDictEqual(tt, self.PARSED_DATA)

if __name__ == '__main__':
    unittest.main()