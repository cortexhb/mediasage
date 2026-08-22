"""Persisted playlists and album recommendations.

Results are what a generation run produced, kept so the history feed can render
them without running a model again. Entry points live in
`backend.results.store`.
"""

from backend.results.models import (
    ResultDetail,
    ResultListItem,
    ResultListResponse,
    ResultType,
)
from backend.results.store import get, page, remove, save
from backend.results.tables import Result

__all__ = [
    "Result",
    "ResultDetail",
    "ResultListItem",
    "ResultListResponse",
    "ResultType",
    "get",
    "page",
    "remove",
    "save",
]
