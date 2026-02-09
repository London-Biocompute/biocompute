"""biocompute - London Biocompute client library."""

from biocompute._version import __version__
from biocompute.client import Client, SubmissionResult
from biocompute.dye import Dye
from biocompute.exceptions import BiocomputeError
from biocompute.well import Well

__all__ = [
    "__version__",
    "Client",
    "SubmissionResult",
    "Well",
    "Dye",
    "BiocomputeError",
]
