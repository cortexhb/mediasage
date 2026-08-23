"""Persisted playlists and album recommendations.

Results are what a generation run produced, kept so the history feed can render
them without running a model again. `results_store` is the entry point.
"""

from backend.results.models import (
    ResultDetail,
    ResultListItem,
    ResultListResponse,
    ResultType,
)
from backend.results.store import ResultStore, results_store
from backend.results.tables import Result

__all__ = [
    "Result",
    "ResultDetail",
    "ResultListItem",
    "ResultListResponse",
    "ResultStore",
    "ResultType",
    "results_store",
]
