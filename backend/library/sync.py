"""Syncing the Plex library into the local cache, and the state of that sync.

The only writer of `tracks` and `track_genres`. Both are written in one
transaction per batch, which is what keeps the normalized genre index in step
now that the SQLite triggers are gone — see docs/track_genres_consistency.md.

Tracks are fetched a page at a time and upserted as they arrive, with the
offset checkpointed. A failed sync keeps what it wrote and the next call
resumes from the checkpoint instead of refetching the library. Rows a
completed sync did not touch are swept only once it succeeds.

Entry point: `library_sync.run`. Blocking; call it through `asyncio.to_thread`.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr
from sqlalchemy import delete, func, insert, select

from backend.config.store import config_store
from backend.db import Upsert, db
from backend.library.live import LiveVersionRule
from backend.library.models import (
    AlbumMetadata,
    SyncPhase,
    SyncProgress,
    SyncResult,
    SyncRun,
    SyncStatus,
    TrackRow,
)
from backend.library.tables import SyncState, Track, TrackGenre

logger = logging.getLogger(__name__)


class LibrarySync(BaseModel):
    """The cache, the sync that fills it, and the progress that sync reports.

    One sync at a time: `run` refuses to start a second. The lock guards the
    in-memory state, which the event loop polls while the sync blocks a worker
    thread.

    The questions about the cache -- how old it is, whether it holds anything,
    which server it was built against -- are answered here rather than beside
    it, because each of them is read off the same `sync_state` row this writes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _run: SyncRun = PrivateAttr(default_factory=SyncRun)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def snapshot(self) -> SyncRun:
        """A consistent copy of the running sync's state."""
        with self._lock:
            return self._run.model_copy(deep=True)

    # -- what the cache knows about itself -------------------------------

    def status(self) -> SyncStatus:
        """What the cache knows about the last sync, plus any running one."""
        with db.session() as session:
            state = SyncState.load(session)
            stored = SyncStatus(
                track_count=state.track_count,
                synced_at=state.last_sync_at,
                plex_server_id=state.plex_server_id,
                sync_duration_ms=state.sync_duration_ms,
            )

        run = self.snapshot()
        stored.is_syncing = run.is_syncing
        stored.error = run.error
        stored.sync_progress = run.progress if run.is_syncing else None
        return stored

    def has_tracks(self) -> bool:
        """Whether a completed sync left tracks behind.

        Reads the recorded count rather than the table, so a half-finished
        first sync does not make callers treat the cache as usable.
        """
        with db.session() as session:
            return SyncState.load(session).track_count > 0

    def is_stale(self) -> bool:
        """Whether the cache is older than the configured age, or never synced."""
        limit = config_store.get().library.stale_after_hours
        synced_at = self.status().synced_at
        if not synced_at:
            return True

        try:
            stamp = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
        except ValueError, TypeError:
            return True
        return (datetime.now(UTC) - stamp).total_seconds() / 3600 > limit

    def server_changed(self, current_server_id: str) -> bool:
        """Whether the cache was built against a different Plex server."""
        cached = self.status().plex_server_id
        if not cached:
            return False
        return cached != current_server_id

    def clear_cache(self) -> None:
        """Drop every cached track and forget the last sync.

        Genre rows go with their tracks by cascade, so only `tracks` is deleted.
        """
        with db.session() as session:
            session.execute(delete(Track))
            state = SyncState.load(session)
            state.last_sync_at = None
            state.track_count = 0
            state.sync_duration_ms = None
            state.sync_token = None
            state.sync_cursor = 0
            session.add(state)

        logger.info("Cache cleared")

    # -- running one -----------------------------------------------------

    def _claim(self) -> bool:
        """Mark a sync as started, unless one already is."""
        with self._lock:
            if self._run.is_syncing:
                return False
            self._run = SyncRun(is_syncing=True, progress=SyncProgress(phase="fetching_albums"))
            return True

    @contextmanager
    def _claimed(self) -> Iterator[None]:
        """Hold the sync claim, releasing it however the run ends."""
        try:
            yield
        finally:
            with self._lock:
                self._run.is_syncing = False
                self._run.progress = SyncProgress()

    def _advance(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        phase: SyncPhase | None = None,
    ) -> None:
        """Update whichever progress fields were supplied."""
        with self._lock:
            if current is not None:
                self._run.progress.current = current
            if total is not None:
                self._run.progress.total = total
            if phase is not None:
                self._run.progress.phase = phase

    def _fail(self, message: str) -> None:
        """Record why the sync stopped, for the next status poll."""
        with self._lock:
            self._run.error = message

    def run(
        self,
        plex_client: Any,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Mirror the Plex music library into the cache.

        Args:
            plex_client: Connected PlexClient
            on_progress: Called with (synced, total) after each batch

        Returns:
            The outcome; `resumable` marks a failure worth retrying
        """
        if not self._claim():
            return SyncResult(success=False, error="Sync already in progress")

        started = time.time()
        with self._claimed():
            try:
                return self._run_sync(plex_client, on_progress, started)
            except Exception as error:
                logger.exception("Sync failed: %s", error)
                self._fail(str(error))
                return SyncResult(success=False, error=str(error), resumable=True)

    def _run_sync(
        self,
        plex_client: Any,
        on_progress: Callable[[int, int], None] | None,
        started: float,
    ) -> SyncResult:
        """The sync itself, with failures left to `run` to classify."""
        server_id = plex_client.connection.machine_identifier()
        if not server_id:
            raise ValueError("Could not get Plex server identifier")

        if self.server_changed(server_id):
            logger.info("Plex server changed, clearing cache")
            self.clear_cache()

        token, cursor = self._checkpoint()
        total = plex_client.library.total_tracks()
        self._advance(total=total)

        logger.info("Fetching album metadata from Plex...")
        album_metadata = plex_client.library.album_metadata()
        logger.info("Got metadata for %d albums", len(album_metadata))
        self._advance(phase="processing")

        synced = self._write_pages(plex_client, album_metadata, token, cursor, total, on_progress)
        return self._finish(server_id, token, synced, started)

    def _checkpoint(self) -> tuple[str, int]:
        """Resume an interrupted sync, or start a new one."""
        with db.session() as session:
            state = SyncState.load(session)
            if state.sync_token and state.sync_cursor:
                logger.info("Resuming interrupted sync at offset %d", state.sync_cursor)
                return state.sync_token, state.sync_cursor

            token = str(uuid.uuid4())
            state.sync_token = token
            state.sync_cursor = 0
            session.add(state)
            return token, 0

    def _write_pages(
        self,
        plex_client: Any,
        album_metadata: dict[str, AlbumMetadata],
        token: str,
        cursor: int,
        total: int,
        on_progress: Callable[[int, int], None] | None,
    ) -> int:
        """Upsert every remaining track, batch by batch."""
        config = config_store.get().library
        live_rule = LiveVersionRule.of(config)
        synced = cursor
        batch: list[TrackRow] = []

        for page in plex_client.library.iter_raw_tracks(start=cursor):
            for track in page:
                batch.append(TrackRow.of_plex(track, album_metadata, token, live_rule))
                if len(batch) < config.sync_batch_size:
                    continue

                synced += len(batch)
                self._write_batch(batch, token, synced)
                batch = []

                self._advance(current=synced)
                if on_progress:
                    on_progress(synced, total)
                logger.info("Synced %d/%d tracks", synced, total)

        if batch:
            synced += len(batch)
            self._write_batch(batch, token, synced)
            self._advance(current=synced)

        return synced

    def _write_batch(self, rows: list[TrackRow], token: str, cursor: int) -> None:
        """Write one batch of tracks, their genres, and the resume checkpoint.

        All three land in a single transaction, so a checkpoint can never claim
        progress the rows did not make.
        """
        if not rows:
            return

        keys = [row.rating_key for row in rows]
        values = [row.columns() for row in rows]
        genres = [
            entry for row in rows for entry in TrackGenre.rows_for(row.rating_key, row.genres)
        ]

        with db.session() as session:
            dialect = session.get_bind().dialect
            session.execute(delete(TrackGenre).where(TrackGenre.rating_key.in_(keys)))
            write = Upsert(table=Track.__table__, rows=values, keys=["rating_key"])
            session.execute(write.statement(dialect))
            if genres:
                session.execute(insert(TrackGenre), genres)

            state = SyncState.load(session)
            state.sync_token = token
            state.sync_cursor = cursor
            session.add(state)

    def _finish(self, server_id: str, token: str, synced: int, started: float) -> SyncResult:
        """Sweep rows this sync did not write, then record it as complete."""
        duration_ms = int((time.time() - started) * 1000)

        with db.session() as session:
            # Through the connection: only a cursor result is typed to count rows.
            removed = (
                session.connection()
                .execute(delete(Track).where(Track.sync_token.is_distinct_from(token)))
                .rowcount
            )
            if removed:
                logger.info("Removed %d tracks no longer in the Plex library", removed)

            final_count = session.execute(select(func.count()).select_from(Track)).scalar_one()
            state = SyncState.load(session)
            state.plex_server_id = server_id
            state.last_sync_at = datetime.now(UTC).isoformat()
            state.track_count = final_count
            state.sync_duration_ms = duration_ms
            state.sync_token = None
            state.sync_cursor = 0
            session.add(state)

        logger.info("Sync complete: %d tracks in %dms", final_count, duration_ms)
        return SyncResult(success=True, track_count=final_count, duration_ms=duration_ms)


# The single sync this process runs.
library_sync = LibrarySync()
