"""biocompute - Protocol definition and submission library."""

from biocompute._version import __version__
from biocompute.client import Client, SubmissionResult
from biocompute.exceptions import BiocomputeError
from biocompute.ops import FillOp, ImageOp, MixOp, Op
from biocompute.protocol import Protocol, collect_trace, protocol
from biocompute.reagent import Reagent, blue_dye, green_dye, red_dye, water
from biocompute.trace import Trace, TracedOp
from biocompute.well import Well, wells

__all__ = [
    "__version__",
    "Client",
    "SubmissionResult",

    "Protocol",
    "protocol",
    "collect_trace",
    "Well",
    "wells",
    "Trace",
    "TracedOp",
    "Op",
    "FillOp",
    "MixOp",
    "ImageOp",
    "Reagent",
    "red_dye",
    "green_dye",
    "blue_dye",
    "water",
    "BiocomputeError",
]
