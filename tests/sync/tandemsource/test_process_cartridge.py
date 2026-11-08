#!/usr/bin/env python3

import unittest

from tconnectsync.sync.tandemsource.process_cartridge import ProcessCartridge
from tconnectsync.eventparser.generic import Events

from ...api.fake import TConnectApi
from ...nightscout_fake import NightscoutApi

# Real captured events (deviceAssignmentId redacted).
# LID_CARTRIDGE_FILLED (33): 180u cartridge fill.
CARTRIDGE_FILLED = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 33,
    "sequenceGroup": 0,
    "sequenceNumber": 448073,
    "pumpDateTime": "2026-05-15T23:50:59",
    "eventProperties": {"insulinVolume": 180, "v2Volume": 0},
    "estimatedDateTime": "2026-05-15T23:50:59Z",
}

# LID_CANNULA_FILLED (61): 0.3u fractional prime.
CANNULA_FILLED = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 61,
    "sequenceGroup": 0,
    "sequenceNumber": 448176,
    "pumpDateTime": "2026-05-16T00:14:09",
    "eventProperties": {"primeSize": 0.3, "completionStatus": 3, "infusionSetType": 0},
    "estimatedDateTime": "2026-05-16T00:14:09Z",
}

# LID_TUBING_FILLED (63): primeSize -1 sentinel ("not recorded").
TUBING_FILLED = {
    "deviceAssignmentId": "00000000-0000-0000-0000-000000000000",
    "eventCode": 63,
    "sequenceGroup": 0,
    "sequenceNumber": 448074,
    "pumpDateTime": "2026-05-15T23:50:59",
    "eventProperties": {"primeSize": -1, "completionStatus": 3, "position": 547509},
    "estimatedDateTime": "2026-05-15T23:50:59Z",
}


class TestProcessCartridge(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tconnect = TConnectApi()
        self.nightscout = NightscoutApi()
        self.process = ProcessCartridge(self.tconnect, self.nightscout, 'abcdef', pretend=False)
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: None

    def test_cartridge_fill(self):
        p = self.process.process(list(Events([dict(CARTRIDGE_FILLED)])), None, None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'eventType': 'Insulin Change',
            'reason': 'Cartridge Filled (180u filled)',
            'notes': 'Cartridge Filled (180u filled)',
            'created_at': '2026-05-15 23:50:59-04:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '448073'
        })

    def test_cannula_fill(self):
        p = self.process.process(list(Events([dict(CANNULA_FILLED)])), None, None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'eventType': 'Site Change',
            'reason': 'Cannula Filled (0.3u primed)',
            'notes': 'Cannula Filled (0.3u primed)',
            'created_at': '2026-05-16 00:14:09-04:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '448176'
        })

    def test_tubing_fill_sentinel_hidden(self):
        # primeSize -1 sentinel -> no suffix.
        p = self.process.process(list(Events([dict(TUBING_FILLED)])), None, None)

        self.assertEqual(len(p), 1)
        self.assertDictEqual(p[0], {
            'eventType': 'Insulin Change',
            'reason': 'Tubing Filled',
            'notes': 'Tubing Filled',
            'created_at': '2026-05-15 23:50:59-04:00',
            'enteredBy': 'Pump (tconnectsync)',
            'pump_event_id': '448074'
        })

    def test_all_three_ordered(self):
        # Output order: cartridge, cannula, tubing.
        p = self.process.process(
            list(Events([dict(CARTRIDGE_FILLED), dict(CANNULA_FILLED), dict(TUBING_FILLED)])),
            None, None)

        self.assertEqual(len(p), 3)
        self.assertEqual([e['reason'] for e in p], [
            'Cartridge Filled (180u filled)',
            'Cannula Filled (0.3u primed)',
            'Tubing Filled',
        ])

    def test_dedup_skips_at_or_before_last_upload(self):
        # last upload between cartridge (23:50:59) and cannula (00:14:09)
        # -> cartridge/tubing skipped, only cannula emitted.
        self.nightscout.last_uploaded_entry = lambda *args, **kwargs: {'created_at': '2026-05-16 00:00:00-04:00'}

        p = self.process.process(
            list(Events([dict(CARTRIDGE_FILLED), dict(CANNULA_FILLED), dict(TUBING_FILLED)])),
            None, None)

        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]['reason'], 'Cannula Filled (0.3u primed)')
        self.assertEqual(p[0]['pump_event_id'], '448176')

    def test_dedup_is_per_event_type(self):
        # A site change after every event must not hold back cartridge/tubing fills,
        # which are deduplicated against the last insulin change (none here).
        last = {'Site Change': {'created_at': '2026-05-16 01:00:00-04:00'}}
        self.nightscout.last_uploaded_entry = lambda eventType, *args, **kwargs: last.get(eventType)

        p = self.process.process(
            list(Events([dict(CARTRIDGE_FILLED), dict(CANNULA_FILLED), dict(TUBING_FILLED)])),
            None, None)

        self.assertEqual([(e['eventType'], e['reason']) for e in p], [
            ('Insulin Change', 'Cartridge Filled (180u filled)'),
            ('Insulin Change', 'Tubing Filled'),
        ])


if __name__ == '__main__':
    unittest.main()
