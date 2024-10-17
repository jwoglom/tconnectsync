from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import List

@dataclass_json
@dataclass
class PumpProfileSegment:
    startTime: int # minutes
    basalRate: int # milliunits
    isf: int
    carbRatio: int
    targetBg: int

    @property
    def skip(self):
        return self.startTime == 0 and self.basalRate == 0 and self.isf == 0 and self.carbRatio == 0 and self.targetBg == 0

@dataclass_json
@dataclass
class PumpProfile:
    name: str
    idp: int
    tDependentSegs: List[PumpProfileSegment]
    insulinDuration: int # minutes
    carbEntry: int # 1 / 0
    maxBolus: int # milliunits

    def __post_init__(self):
        self.tDependentSegs = [i for i in self.tDependentSegs if not i.skip]

@dataclass_json
@dataclass
class PumpProfiles:
    activeIdp: int
    profile: List[PumpProfile]

@dataclass_json
@dataclass
class PumpGlucoseAlertSettings:
    mgPerDl: int
    enabled: int # 1 / 0
    duration: int # minutes
    status: int # unknown

@dataclass_json
@dataclass
class PumpCgmSettings:
    highGlucoseAlert: PumpGlucoseAlertSettings
    lowGlucoseAlert: PumpGlucoseAlertSettings

@dataclass_json
@dataclass
class PumpSettings:
    profiles: PumpProfiles
    cgmSettings: PumpCgmSettings