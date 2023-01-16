from dataclasses import dataclass, replace
from typing import List, Optional

@dataclass
class Device:
    name: str
    model_number: str
    status: str
    guid: Optional[str]

@dataclass
class ProfileSegment:
    display_time: str # Identical to time except written out as Midnight or Noon
    time: str
    basal_rate: float # _ u/hr
    correction_factor: int # 1u: _ mg/dL
    carb_ratio: float # 1u: _ g
    target_bg_mgdl: int

@dataclass
class Profile:
    title: str
    active: bool
    segments: List[ProfileSegment]
    calculated_total_daily_basal: float # in units
    insulin_duration_min: int
    carbs_enabled: bool

    def activeProfile(self):
        p = self.copy()
        p.active = True
        return p

    def copy(self):
        p = replace(self)
        p.segments = [replace(s) for s in p.segments]
        return p

# Settings stored globally in the pump that are stored per-profile in Nightscout
@dataclass
class DeviceSettings:
    low_bg_threshold: int
    high_bg_threshold: int
    raw_settings: dict
