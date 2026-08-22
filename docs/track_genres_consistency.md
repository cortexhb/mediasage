# Keeping `track_genres` Consistent Without Triggers

`track_genres` is a normalized index over `tracks.genres`, so genre filters hit an index instead
of parsing a JSON column per row. It used to be maintained by three SQLite triggers. The move to
SQLAlchemy/SQLModel with Postgres as a future target removed them. This records what they
guaranteed, why none of the three could be carried across, and what took over.

Versions pinned from `uv.lock`: sqlmodel 0.0.39, sqlalchemy 2.0.52, alembic 1.19.1. SQLite
behaviour verified against the library bundled with this machine's Python, `sqlite3.sqlite_version
== "3.53.4"`.

## What the Triggers Did

The pre-Alembic schema is kept verbatim as `LEGACY_SCHEMA` in `tests/db/test_migrate.py:17-82`,
which is what the upgrade path is tested against now that the module defining it is deleted. Three
triggers kept the two tables in step:

- `tracks_genres_after_insert` — deleted the track's genre rows, then reinserted them from
  `json_each(NEW.genres)`.
- `tracks_genres_after_update` — the same body, `AFTER UPDATE OF genres`.
- `tracks_genres_after_delete` — deleted the track's genre rows.

`track_genres` had no foreign key: its declaration was a two-column primary key and nothing more,
so the delete trigger was the only thing preventing orphan rows.

Three statements wrote `tracks`: an `INSERT OR REPLACE` batch, a full `DELETE`, and a sweep of
rows the finished sync had not touched.

## The Three SQLite Behaviours Encoded

**`json_each` throws on invalid JSON.** Hence the `CASE WHEN json_valid(NEW.genres) THEN
NEW.genres ELSE '[]' END` guard in both bodies (`tests/db/test_migrate.py:48`). Without it one
corrupt row aborted the whole insert.

**`INSERT OR REPLACE` does not fire delete triggers.** From the SQLite documentation: "When the
REPLACE conflict resolution strategy deletes rows in order to satisfy a constraint, delete
triggers fire if and only if recursive triggers are enabled." The old connection set
`journal_mode`, `busy_timeout` and `foreign_keys` — never `recursive_triggers`. Confirmed by
running the pattern: with the pragma off, re-replacing a track leaves its old genre rows behind;
with it on, they are removed. The explicit `DELETE` at the top of the insert trigger body covered
that gap.

**`INSERT OR REPLACE` fires the insert trigger, not the update trigger.** REPLACE is a delete
followed by an insert, so a row always arrived through `AFTER INSERT`. Combined with the absence
of any bare `UPDATE tracks` statement, `tracks_genres_after_update` never fired in production. It
was dead code shadowing a real requirement.

## Why They Could Not Be Translated

The rewrite in `backend/db/statements.py:45-49` builds `INSERT … ON CONFLICT DO UPDATE`, the one
upsert form both SQLite and Postgres accept with the same builder shape. That change alone
invalidated the trigger set: on a row that already exists, `ON CONFLICT DO UPDATE` fires the
update trigger, not the insert trigger. Verified directly — a table carrying both triggers records
`from-update-trigger` after an upsert that conflicts. PostgreSQL documents the same split: "an
`INSERT` with an `ON CONFLICT DO UPDATE` clause may cause both insert and update operations, so it
will fire both kinds of triggers as needed."

So the dead trigger would have become the load-bearing one, and the live one would have stopped
firing on updates. The set needed restructuring, not translating.

Translation was separately blocked:

- `json_each` is SQLite-only; the Postgres equivalent is `jsonb_array_elements_text`, over a
  `jsonb` column rather than the `TEXT`-stored JSON SQLite used.
- PostgreSQL has no inline trigger body. "PostgreSQL only allows the execution of a user-defined
  function for the triggered action", requiring `CREATE FUNCTION … RETURNS trigger` plus
  `CREATE TRIGGER … EXECUTE FUNCTION`.
- `json_valid` has no direct counterpart; a `jsonb` column makes the guard unnecessary but forces
  a type change on `tracks.genres`.

Two dialect-specific implementations would have had to be written, kept in step by hand, and
tested separately — the opposite of the boundary `backend/db/statements.py:1-6` sets, where one
module knows dialect names and nothing above it does.

## What Replaced Them

**Deletion stays in the engine.** `TrackGenre.rating_key` (`backend/library/tables.py:64-66`)
declares `foreign_key="tracks.rating_key"` with `ondelete="CASCADE"`, so the database removes genre
rows when a track goes, with no application code. This is stronger than what came before: the old
schema had no foreign key at all, so anything bypassing the trigger orphaned rows silently. SQLite
enforces it because `PRAGMA foreign_keys=ON` is applied per connection at
`backend/db/engine.py:50`.

**Insert and update moved into the sync.** `write_batch` (`backend/library/sync.py:171-194`)
deletes the batch's existing genre rows, upserts the tracks, and inserts the new genre rows — all
in one transaction, alongside the resume checkpoint. `genre_rows`
(`backend/library/tables.py:99-118`) derives those rows in Python, deduplicating by lowercase and
dropping non-strings and blanks, which replaces the `je.type = 'text'` filter and the `json_valid`
guard with type checks that need no dialect.

The guarantee changed character: it was "no writer can leave the two out of sync, because the
database enforces it" and is now "one writer exists, and it writes both". `TrackGenre`'s docstring
at `backend/library/tables.py:53-59` states that constraint so a second writer is a visible
violation rather than a silent one.

## Migration

`0001_orm_schema` (`backend/migrations/versions/0001_orm_schema.py`) handles a fresh database and
a pre-Alembic one in the same path, with no stamping step. `tracks`, `track_genres` and
`sync_state` are a cache of Plex, so an existing database has them dropped and recreated rather
than altered: no column rename, no table rebuild to add the cascade, and nothing dialect-specific
to translate. Dropping `tracks` takes the three triggers with it, since SQLite drops a table's
triggers with the table. The cost is one re-sync after upgrading, which is why the old
`_backfill_track_genres` helper has no successor — the sync rebuilds the index from scratch.

`results` is not derivable, so its rows are copied into the new table
(`backend/migrations/versions/0001_orm_schema.py:104-118`) rather than dropped.

Both paths are checked against the models with `alembic.autogenerate.compare_metadata` in
`tests/db/test_migrate.py`, which asserts an empty diff for a fresh database and for a migrated
legacy one.

## Sources

- [SQLite: ON CONFLICT clause](https://www.sqlite.org/lang_conflict.html) — read 2026-08-22
- [PostgreSQL: CREATE TRIGGER](https://www.postgresql.org/docs/current/sql-createtrigger.html) —
  read 2026-08-22, current docs
