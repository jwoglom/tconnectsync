from .secret import ENABLE_TESTING_MODES

"""Supported synchronization features."""
BASAL = "BASAL"
BOLUS = "BOLUS"
IOB = "IOB"
BOLUS_BG = "BOLUS_BG"
CGM = "CGM"

DEFAULT_FEATURES = [
    BASAL,
    BOLUS,
    IOB
]

ALL_FEATURES = [
    BASAL,
    BOLUS,
    IOB
]


# These modes are not yet ready for wide use.
if ENABLE_TESTING_MODES:
    ALL_FEATURES += [
        BOLUS_BG,
        CGM
    ]