from dataclasses import dataclass, asdict


@dataclass
class Bolus:
    description: str
    complete: str # "1" / "0"
    completion: str
    request_time: str # _datetime_parse timestamp
    completion_time: str # _datetime_parse timestamp
    insulin: str
    requested_insulin: str
    carbs: str
    bg: str # potentially ""
    user_override: str
    extended_bolus: str # "1" / "0"
    bolex_completion_time: str
    bolex_start_time: str

    def to_dict(self):
        return asdict(self)
    
    @property
    def is_extended_bolus(self):
        return self.extended_bolus == "1"