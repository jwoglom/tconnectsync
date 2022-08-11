from dataclasses import dataclass
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
