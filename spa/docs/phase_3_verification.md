# Phase 3 Manual Verification

What the Home, history and library-sync slice cannot prove with tests: real sync timings against a
real Plex server, `<dialog>` behaviour in the browser the reader actually uses, and CSS parity
against `frontend/`. Run these after `uv run uvicorn backend.main:app --reload --port 5765` and
`npm run dev` are both up.

Assumes the SPA at `http://localhost:5173` and the API at `http://localhost:5765`.

## Automated Gate

All five must be green before any manual step is worth running.

```bash
cd spa
npm run build && npm run lint:check && npm run lint:css:check && npm run format:check && npm run test:run
```

Backend, for the sync progress and concurrency added in this phase:

```bash
uv run pytest && uv run ruff check . && uv run pyrefly check
```

## Home

1. Open `/`. The greeting and the three mode cards paint before the history feed has anything in it.
   Nothing here waits on a wizard; there is no wizard.
2. Each card is a link. Middle-click one — it opens in a new tab. `frontend/index.html:186` drew
   these as buttons and could not.
3. `/playlist/prompt`, `/playlist/seed` and `/recommend` answer `NotFound` inside the shell until
   Phase 4 lands.

## History Feed

Needs saved results. Generate a few through the legacy UI first, or run against a database that
already has them.

4. Entries group under date headings, newest first.
5. The chips filter what is already on screen. Switching between All, Playlists and Albums makes no
   request — watch the network panel.
6. `Load more` appends rather than replacing, and disappears once the total is reached.
7. Hover an entry: the delete button appears. **Tab to the entry instead** — it appears on focus
   too. The legacy revealed it on hover alone, so a keyboard could not reach it.
8. Click delete once. It asks again and reverts after three seconds if left alone.
9. Click it twice. The entry disappears immediately and does not return on reload.
10. Delete something already deleted in another tab. It disappears rather than erroring — a 404 is
    the outcome asked for.

## Library Sync

The expensive part. Needs a real Plex server; timings below are from an 80k-track library.

11. With the library already synced, the status bar reads the track count and how long ago it
    synced. **Nothing starts on its own.** `frontend/app.js:2352` started a sync on an empty
    library, which spent hours of somebody's server for opening a page.
12. Click `Refresh`. The bar switches to `Syncing …%` within a second.
13. **Watch the album phase.** It reads `Reading albums from Plex: N / M albums` and the number
    climbs. A bar frozen at 0% is the defect this phase fixed; the total used to be the track count
    while the phase counted albums.
14. Then `Enriching albums with genres: N / M genres`. This is the slowest stage — one Plex search
    per genre choice, of which a large library has hundreds. It runs `plex.genre_workers` at a time
    (default 8), so it should be visibly faster than the track phase per item.
15. Then `Reading tracks from Plex`, then `Saving tracks`. The bar restarts between phases because
    they count different things; the text is what says why.
16. Watch the backend log. Each phase logs its own progress line — `Fetching albums: N/M`,
    `Fetching genres: N/M` — rather than going silent for minutes.
17. Kill the API mid-sync and restart it. The next status read reports what the failed sync left
    behind, and a new sync resumes from the checkpointed offset rather than restarting.
18. Set `MEDIASAGE_PLEX__GENRE_WORKERS=1` and sync again. The genre stage is serial and much slower.
    This is the knob, and 8 is the default.

## First Sync

Needs an empty cache. Move `data/library_cache.db` aside; do not delete it.

19. Open `/`. The bar reads `Library not synced` and offers `Sync now`. Nothing has started.
20. Click it. A dialog opens over the page: title, explanation, progress bar, phase text.
21. **Press Escape.** It closes and the sync keeps reporting in the bar.
    `frontend/app.js:2372` made this modal inescapable.
22. Click the `×`. Same outcome — Escape alone is not an exit a mouse can find.
23. **Click the `Syncing …%` text in the bar.** The dialog comes back, on the phase it has reached.
    `frontend/app.js:2244` hid this modal with no way to reopen it.
24. While it runs, the three Home cards are dimmed and the intro line says the library is syncing
    and names what is disabled. Tab to a card: it is still focusable and announces as disabled.
    Click it: nothing happens.
25. **Scroll the page while the dialog is open.** The dialog stays centred on the viewport. It is
    the UA that fixes an open modal; overriding `position` made it scroll away.
26. Once the sync finishes the dialog closes on its own, the cards come back, and the bar reads the
    track count.
27. Start a second sync over a library that already has tracks. **No dialog opens on its own** — the
    app is usable, so interrupting it would be a regression. The progress text still opens one, and
    it says the app stays usable rather than telling the reader to wait.
28. Close the dialog mid-sync and watch the bar. The sync keeps going; the dialog is a view of it,
    never a stage of it.

## One Poller

29. Open `/settings` and start a sync from the Plex card's `Sync library` button. The **status bar
    agrees immediately** — same sync, one poller. Three components read it; three would disagree.
30. While it runs, both `Sync library` and the bar's `Refresh` are disabled.
31. With no server connected, `Sync library` is disabled.
32. Open the network panel during a sync. `GET /api/library/status` fires once a second, not twice
    and not three times.
33. Navigate between `/` and `/settings` mid-sync. The poll cadence does not change; the shell owns
    it and survives navigation.

## Errors

34. Stop the API. The bar reports it could not reach the server and the page still renders.
35. Break the history endpoint (stop the API, then reload `/`). Home still shows the greeting and
    the three cards; only the feed says it could not load.

## CSS Parity

Side by side with `frontend/` at three widths, per the migration plan. The breakpoints that matter
are declared in `spa/src/design-system/_sizes.scss`.

| Width  | What changes                                        |
| ------ | --------------------------------------------------- |
| 1280px | Desktop baseline                                    |
| 768px  | At or below: every control is a touch target (44px) |
| 600px  | At or below: nav loses entries, cards restack       |

Compare the mode-card grid, the feed's date headings, the status bar, and the sync dialog's width.
No visual-regression tooling is proposed; this is a human pass.
