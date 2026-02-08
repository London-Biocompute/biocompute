"""biocompute - London Biocompute client library."""

from biocompute._version import __version__
from biocompute.competition import Competition, SubmissionResult, WellResult
from biocompute.exceptions import BiocomputeError
from biocompute.reagent import Reagent, blue_dye, green_dye, red_dye, water
from biocompute.trace import Trace, TracedOp
from biocompute.well import Well, wells

__all__ = [
    "__version__",
    "Competition",
    "SubmissionResult",
    "WellResult",
    "Well",
    "wells",
    "Trace",
    "TracedOp",
    "Reagent",
    "red_dye",
    "green_dye",
    "blue_dye",
    "water",
    "BiocomputeError",
]
