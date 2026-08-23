# Phase 2 Manual Verification

What the Settings slice cannot prove with tests: real Plex timings, real Ollama model lists, browser
constraint validation, and CSS parity against `frontend/`. Run these after `uv run uvicorn
backend.main:app --reload --port 5765` and `npm run dev` are both up.

Assumes the SPA at `http://localhost:5173` and the API at `http://localhost:5765`.

## Automated Gate

All five must be green before any manual step is worth running.

```bash
cd spa
npm run build && npm run lint:check && npm run lint:css:check && npm run format:check && npm run test:run
```

Backend, for the stats cache added in this phase:

```bash
uv run pytest && uv run ruff check . && uv run pyrefly check
```

## Load and Counts

1. Open `/settings`. **The form paints immediately** — Plex and LLM fields are usable before the
   library counts appear. A blocked form is the regression this phase fixed.
2. While the counts are outstanding, the Plex card reads `Getting library statistics, hold tight…`.
3. Counts arrive under the Plex fields, not in a card of their own.
4. Reload within 10 minutes. The counts are immediate — `library.stats_cache_seconds` (default 600)
   is holding them. Wait past it and the first read is slow again; on an 80k library Plex spends
   ~8.75s aggregating track genres.
5. Stop Plex, reload. The counts read `Library statistics are unavailable.` and the form still works.

## Plex Fields

6. With `MEDIASAGE_PLEX__URL` set, the URL field is disabled and says the environment supplies it.
7. The token field is blank with a `(configured)` placeholder when a token is stored. Saving without
   touching it leaves the stored token intact.

## Provider Switching

8. Switch the provider select through all five. Only the selected provider's fields render; nothing
   from the previous one is left behind.
9. With `LLM_PROVIDER` set in the environment, the select is disabled — then **save and confirm the
   provider survives**. A disabled control is absent from `FormData`; a hidden field carries it.

## Ollama

Needs a reachable Ollama server.

10. Type the URL one character at a time. The status goes to `Checking…` once, not once per
    keystroke, and settles on `Connected (N models)`.
11. Both selects fill with that server's models.
12. Pick a different analysis model. The context window follows it within a second.
13. Point at a second Ollama server that lacks your configured models. Both selects fall back to its
    first model only if _neither_ saved model survived; if only one survived, the other select is
    **empty**. Save, then reload: the model you did not choose must not have been overwritten.
14. Where the server reports no context window, the figure reads `(default)`. Save, reload, and
    confirm the stored `context_window` is unchanged — a default is never written back.

## Custom Provider

15. Set the context window to `20000000` and submit. The browser blocks it on `max`; the inline
    error alone does not.
16. Clear the field and submit. Blocked on `required`.
17. Enter `ftp://box/v1` and leave the field. Inline error names the protocol.

## Saving

18. Save with a typed Plex token. The button stays disabled through the save _and_ the revalidation
    that follows it, then the token field is **cleared** — a second save must not resend it.
19. Stop the API, then save. An error message appears and **everything typed stays on screen**. No
    error page.
20. Save something the API refuses (e.g. a malformed URL it validates). The message names the
    problem and the form survives.

## Shell and Errors

21. Stop the API and reload `/settings`. The error shows inside the shell — the header and navigation
    survive.
22. Visit `/settings/nonsense`. The not-found page renders inside the shell.

## CSS Parity

Side by side with `frontend/` at three widths, per the migration plan. The breakpoints that matter
are declared in `spa/src/design-system/_sizes.scss`.

| Width  | What changes                                        |
| ------ | --------------------------------------------------- |
| 1280px | Desktop baseline                                    |
| 768px  | At or below: every control is a touch target (44px) |
| 600px  | At or below: nav loses entries, cards restack       |

Compare spacing, field widths, status colours, and the counts grid. No visual-regression tooling is
proposed; this is a human pass.
