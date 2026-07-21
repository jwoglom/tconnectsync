from dataclasses import dataclass
from dataclasses_json import dataclass_json, DataClassJsonMixin
from typing import List

# These dataclasses model the `settings.details` blob from the Tandem Source
# bff/pumper endpoint (BffPump.settings.details). Only the fields the
# profile sync consumes are declared; dataclasses_json ignores the rest.

@dataclass_json
@dataclass
class PumpProfileSegment:
    startTime: int # minutes
    basalRate: int # milliunits
    isf: int
    carbRatio: int # milliunits
    targetBg: int

    @property
    def skip(self):
        return self.startTime == 0 and self.basalRate == 0 and self.isf == 0 and self.carbRatio == 0 and self.targetBg == 0

@dataclass_json
@dataclass
class PumpProfile:
    name: str
    idp: int
    timeDependentSegments: List[PumpProfileSegment]
    insulinDuration: int # minutes
    carbEntry: str # e.g. "UnitsAsCarbs"
    maxBolus: int # milliunits

    def __post_init__(self):
        self.timeDependentSegments = [i for i in self.timeDependentSegments if not i.skip]

    @property
    def tDependentSegs(self) -> List[PumpProfileSegment]:
        # Back-compat alias for the pre-BFF field name.
        return self.timeDependentSegments

@dataclass_json
@dataclass
class PumpProfiles:
    activeIdp: int
    profile: List[PumpProfile]

@dataclass_json
@dataclass
class PumpCgmSettings:
    # The bff/pumper cgmSettings block is flat (no nested per-alert object).
    highGlucoseAlertMgPerDl: int
    lowGlucoseAlertMgPerDl: int

@dataclass_json
@dataclass
class PumpSettings(DataClassJsonMixin):
    profiles: PumpProfiles
    cgmSettings: PumpCgmSettings
