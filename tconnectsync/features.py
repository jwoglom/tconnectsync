from .secret import ENABLE_TESTING_MODES

"""Supported synchronization features."""
BASAL = "BASAL"
BOLUS = "BOLUS"
IOB = "IOB"
BOLUS_BG = "BOLUS_BG"
CGM = "CGM"
PUMP_EVENTS = "PUMP_EVENTS"

DEFAULT_FEATURES = [
    BASAL,
    BOLUS
]

ALL_FEATURES = [
    BASAL,
    BOLUS,
    IOB,
    PUMP_EVENTS
]


# These modes are not yet ready for wide use.
if ENABLE_TESTING_MODES:
    ALL_FEATURES += [
        BOLUS_BG,
        CGM
    ]