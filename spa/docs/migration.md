# Migrating the Frontend to the SPA

Plan of attack for replacing `frontend/app.js` (5488 lines) with the React app in `spa/`. Covers
sequencing, the architectural decisions the port commits to, and the defects that must be fixed
before or during it.

Assumes the conventions in `spa/README.md`, which stays authoritative on structure, naming, styles,
and testing. This document records order and rationale, not rules.

Versions the plan holds for, from `spa/package-lock.json`: React 19.2.8, React Router 8.3.0,
Vite 8.2.2, TypeScript 6.0.3, Vitest 4.1.11, msw 2.15.0, sass-embedded 1.103.1,
@hey-api/openapi-ts 0.99.0, ESLint 10.9.0.

## The Legacy App Is Unusable, Not Merely Outdated

The backend was refactored across several passes while `frontend/` was deliberately left alone. The
result is worse than a stale UI.

`frontend/app.js:5421` gates the setup wizard on `setupStatus.setup_complete`. That field no longer
exists on `SetupStatusResponse`, so the expression reads `!undefined`, which is `true`. The wizard
opens on every page load, and the `return` at `frontend/app.js:5423` skips normal initialisation.

There is no way out of it. The wizard's final action calls `completeSetup()`
(`frontend/app.js:5361`), which posts to `/api/setup/complete` — an endpoint that was deleted. The
call throws inside an unguarded `await`, so `exitSetupWizard()` never runs.

The AI step cannot be completed either. `POST /api/setup/validate-ai` rejects any request without a
model name (`backend/api/routes/setup/ai.py:26`) or a context window
(`backend/api/routes/setup/ai.py:28`). The wizard collects neither and has no model input at all.

This inverts the usual migration risk. The SPA has no wizard, and not porting one removes the
failure rather than inheriting it. The cost is that **Settings becomes the only configuration
surface**, which drives the sequencing below.

## Sequencing

Two foundation phases, then one vertical slice per route.

Phases 0 and 1 build the API boundary, the design-system core, and the app shell. Neither ships a
user-visible screen. Every phase after that is a single route delivered whole: its page, its
loader and action, its organisms, its styles, and its tests landing together and working against the
real backend.

Per-layer sequencing was rejected because it produces a component library with no consumers, where
every prop shape is a guess unverified for months. Pure per-page with no foundation was rejected
because the first page would drag the entire API layer in behind it, un-reviewably.

Components are born in `organisms/`. The second consumer moves one down a layer, as
`spa/README.md` already requires. Nothing is promoted speculatively.

| Phase | Scope                                                               | Why here                                       |
| ----- | ------------------------------------------------------------------- | ---------------------------------------------- |
| 0     | Design-system core, API boundary, SSE reader, spikes                | Nothing can be built without it                |
| 1     | App shell, nav, `Overlay`, route table with stubs, legacy-hash shim | Proves routing and tokens                      |
| 2     | Settings                                                            | Only configuration surface; the broken screen  |
| 3     | Home, history feed, library sync                                    | Read-mostly; exercises loaders                 |
| 4     | Prompt flow, filters, generation, `/result/:id`                     | Proves the step mechanism and the stream       |
| 5     | Seed flow                                                           | Validates the shared filters route             |
| 6     | Recommend Album                                                     | Largest screen; server-held session            |
| 7     | Parity sweep                                                        | Checklist written in Phase 1                   |
| 8     | Cutover                                                             | SPA fallback, Docker stage, delete `frontend/` |

### Settings Leads the Page Slices

Four reasons, in order of weight.

It is the only way to configure the app once the wizard is gone. Nothing else can be exercised
against a real Plex server or a real provider until it exists.

It is the broken screen. Saving a cloud provider fails today: sending `llm_provider` triggers
`ConfigUpdate.provider_changes` (`backend/config/models.py:456`), which blanks `model_analysis` and
`model_generation`, and the same request is then probed with an empty model name.

It exercises the generated client harder than any other screen, across `/api/config`,
`/api/ollama/*`, and `/api/setup/status`. Codegen naming, `exactOptionalPropertyTypes`, and
`SecretStr` handling all hurt here first, at the cheapest moment to fix them.

It produces the form atoms every later page needs, each with a real consumer proving its props.

Settings must also absorb three things the wizard used to own, or they vanish entirely: the
`music_libraries` list that turns the library field into a select, the `*_from_env` flags that mark
deployment-provided fields as uneditable, and `data_dir_writable` with its uid/gid — the only
diagnostic for a Docker volume permission failure.

## Architectural Decisions

### Wizard Steps Become Routes

Both multi-step flows become route hierarchies rather than a `step` variable in component state.
Steps are deep-linkable, browser back works, and each step's precondition lives in its loader.

`/playlist/:mode/filters` is shared by both create modes; the filters step is byte-identical in the
legacy code and only the generate request differs. A `mode` outside the union throws a 404 from the
loader.

The results step is not a step. Both flows converge on `/result/:resultId`, which the legacy code
already does — `frontend/app.js:3138` for playlists and `frontend/app.js:4503` for recommendations
both `replaceState` to `#result/<id>` on completion. Making it a resource route removes an entire
class of "what happens on reload at results" questions.

### Loaders Read; Actions Spend

Loaders fetch only cheap, idempotent data. Every expensive or mutating call is an action.

This is not a style preference. `POST /api/recommend/questions` creates a server session and spends
two LLM calls. As a loader it would fire on every navigation, revalidation, and back-button press.

`shouldRevalidate` is set explicitly on the filters and recommend-setup routes so an action
elsewhere does not re-pull library statistics.

### Flow State Lives in Versioned Session Storage

Questions, answers, the seed track, selected dimensions, and the recommend `session_id` are produced
by spending money. They cannot be recomputed and must survive a refresh, so they go in a versioned
`sessionStorage` record owned by `libs/flowStore/`.

Each step loader then reads the flow and redirects to the flow's first step when a precondition is
missing. That is the only place step preconditions are expressed — no guard components, no context
provider, no redirect from an effect.

Session storage rather than local storage is deliberate: a second tab starts its own flow, matching
the fact that the server session is per-flow.

### The Recommend Session Is Allowed to Die

`SessionStore` expires sessions and drops the oldest past a cap
(`backend/recommender/sessions.py:154`, `:167`). A restored flow can therefore reference a dead
session, and generation answers 404.

Treat that 404 as a recoverable redirect back to the flow's first step, not an error page. It is the
same outcome as the legacy "start over", reached automatically.

After a successful generation, the session id is carried to `/result/:resultId` in router state. A
fresh deep link has no router state, so the id is absent and the follow-up actions hide themselves —
mirroring today's `sessionId === null` behaviour with no extra concept.

### One SSE Reader, Frame-Agnostic

The two streams do not agree on their terminal frame. `backend/generator/playlists.py:266` emits a
`complete` event; `backend/api/routes/recommend/generate.py:156` emits `result`. Playlists also
emits a bare `: heartbeat` comment frame to flush iOS buffers.

So the shared reader has no concept of a terminal frame — it ends when the body ends, and each
caller declares its own terminator. It is an async generator consumed with `for await`, which
replaces the nested callback recursion in the legacy reader, makes cancellation a plain
`AbortSignal`, and makes cleanup a `try/finally`.

Frame parsing is pure and separately tested: multi-line `data:`, comment frames, a frame split
across two chunk boundaries, and a trailing partial. The legacy buffering bug class becomes a unit
test.

The stale-chunk timeout is an option rather than two implementations: playlists pass 600s or 300s
depending on `is_local_provider`, recommendations pass 120s.

The iOS synthetic-completion fallback — accumulating track batches and fabricating a completion when
the body ends without one — stays in the playlist wrapper, not the shared reader.

### `.hidden` Does Not Enter the SPA

The legacy `.hidden { display: none !important }` utility is a vanilla-JS artifact: visibility was
toggled by class because there was no alternative. React's answer is conditional rendering.

This matters because `.hidden` appears in composed selectors throughout the stylesheet
(`.toast.hidden`, `.modal-overlay.hidden`, and others), and composed global selectors are the worst
case for CSS Modules. Removing the concept removes the hazard rather than scoping around it.

Elements that must stay mounted through a transition — modals, the bottom sheet, toasts — get an
`--open` modifier inside their own module instead.

The cutover check is one grep for `hidden` across `spa/src`, expecting only `aria-hidden` and the
`hidden` attribute.

### Six Overlays Become One

Roughly 620 lines of `frontend/style.css` are six near-duplicate overlay implementations —
`.loading-overlay`, `.success-modal`, `.sync-modal`, `.modal-overlay`, `.step-loading-overlay`, and
`.bottom-sheet` — each redefining its own backdrop, centering, and hidden state.

They collapse to one `atoms/Overlay` built on native `<dialog>`. `showModal()` supplies focus
trapping, Escape handling, top-layer stacking, a backdrop, and inertness of the rest of the page.
That deletes `focusManager` (`frontend/app.js:9-62`), the z-index tiers above the overlay level, and
the scroll-lock trio at `frontend/app.js:3331-3350`.

Spike this against jsdom in Phase 0 before committing to it: confirm `HTMLDialogElement.prototype.showModal`
exists under the installed jsdom and that Testing Library can drive it. Named fallback if not: a
`div` with `role="dialog"` plus a `useFocusTrap` hook ported from `focusManager`.

This is the one place the port deliberately does not mirror the legacy CSS structure. The rendered
result must match; the source will not.

### Cross-Cutting Responsive Blocks

Two blocks in `frontend/style.css` reach across unrelated components and block a clean per-component
split. They are handled differently because they are different problems.

The touch-target block applies 44px minimums to roughly fifteen components. It dissolves entirely
into a mixin each component includes in its own module. It exists only because a global stylesheet
had no other way to say "every interactive thing gets 44px on mobile".

The compact-mobile block changes layout composition — hiding nav entries, restacking home cards,
shrinking the stepper. It does not dissolve. Each rule moves into the module of the component it
names, wrapped in a breakpoint mixin. The nav-hiding rules stay CSS rather than becoming a media
query hook: no layout thrash, no first-paint flicker.

### Keyframes Are Mixins

CSS Modules hashes keyframe names per file, and `animation-name: :global(spin)` is an escape hatch
the module system cannot check. The shared keyframes are exposed as mixins instead, so a module that
animates gets its own locally-hashed copy. The cost is three or four duplicated six-line blocks in
the bundle, in exchange for no global-name dependencies.

### Test Queries

Tests query by role, label, and visible text. A failing accessible query is information: it usually
means the control is unlabelled or is a `div` pretending to be a button. A `data-testid` silences
that signal permanently, so every testid trades away a free accessibility check.

The legacy markup already carries real semantics — `role="checkbox"` on dimension cards,
`role="menuitem"` in the nav dropdown, `aria-current` on nav buttons, `aria-expanded` on the
dropdown trigger — so accessible queries mostly work, and the cases where they do not are findings.

A flat prohibition is worse than the rule, because it pushes tests toward brittle full-string text
matching, hashed class selectors, and positional `nth-child`. A testid is legitimate for scoping a
query to a layout region with no honest role, and for content the app does not control — a track
title can be anything, including empty. It is never legitimate on an interactive control, where it
is a bug report about the control.

Each one carries a one-line reason at the usage site, the same shape `CLAUDE.md` already requires
for module-level functions.

## Backend Defects

Four defects the port depends on, in descending order of importance.

**Configuring inference must never spend an inference call.** Both `POST /api/config` and
`POST /api/setup/validate-ai` run a real completion (`backend/api/probes.py:100`) whenever a field in
`CONNECTING` (`backend/config/models.py:404`) is present. Saving settings is therefore billable and
can block for `llm.request_timeout`. This is a backend defect to fix, not a constraint for the UI to
design around; the Settings slice assumes it is fixed rather than building a pending-and-abort
experience on top of it.

**`ResultDetail.snapshot` is `dict[str, Any]`**, against the house convention of strong typing via
pydantic models. As a discriminated union keyed on `type`, codegen produces a real TypeScript union
and the `/result/:resultId` switch becomes compiler-checked. Without it, the three highest-traffic
payloads in the app are untyped, which contradicts the generated-types rule in `spa/README.md`.

**`ConfigUpdate.changes()` filters on truthiness** (`backend/config/models.py:491`), so a cost of
`0.0` cannot be cleared and `context_window: 0` is dropped silently. An all-falsy body then returns 400. One-line fix. Until then the Settings form must refuse zero with a stated reason rather than
appear to save it.

**No route sets `operation_id`**, so codegen emits names like `_get_config_api_config_get`.
Mechanical to fix, and it improves `/docs` at the same time. Separately, both streaming routes are
`response_model=None`, so their payloads never enter the schema and cannot be generated at all.

## Prerequisites in `spa/`

Three items introduced during the scaffold, all Phase 0.

The BEM pattern in `spa/stylelint.config.js:10` permits a `--modifier` but rejects an `__element`,
and assumes kebab-case blocks. Class names are camelCase blocks with BEM parts — `trackRow`,
`trackRow__title`, `trackRow--active` — because CSS Module classes are read as JavaScript
properties, so `styles.trackRow__title` resolves where a kebab-case name would need bracket access.
The pattern must be replaced before the first module, or `npm run lint:css:check` fails on it.

`spa/index.html` is missing the skip link that `frontend/index.html:13` provides. Its CSS is already
in the must-stay-global set. Restoring it closes an accessibility regression that predates any port
work.

`spa/README.md:199` contradicts the cutover decision: definition-of-done item 5 requires legacy
behaviour to be gone from `frontend/app.js`, but `frontend/` is never edited during the port.
Resolve toward cutover — the item is satisfied once, by deleting the directory. The testid line in
the same file's rubber-stamp list also needs replacing with the scoping rule above, which it
currently reads as prohibiting outright.

## Verification

The owner runs the application; agents do not. Tests carry the weight, and each phase ships a short
manual script.

Every phase must leave `npm run build`, `lint:check`, `lint:css:check`, `format:check`, and
`test:run` green.

Four kinds of test, per phase. Component tests cover at minimum the loading, empty, error, and
populated states of anything that has them. Route contract tests drive `createMemoryRouter` against
msw and are the only way loaders, actions, redirects, and `shouldRevalidate` get covered; every step
route gets a "deep link with no flow state redirects to step one" case. Contract tests use msw
handlers typed from the generated client, so a fixture that drifts from the schema is a compile error
rather than a green test against a backend that does not exist. Stream tests drive a real
`ReadableStream` of frame bytes including a split frame, a comment frame, an error frame, and a body
that ends without a terminator.

CSS parity is a manual side-by-side at three widths per slice, against the still-present
`frontend/`. No visual-regression tooling is proposed.

## Cutover

`backend/api/routes/static.py` currently claims `/` exactly and mounts `/static`. `createBrowserRouter`
requires any unknown path to return `index.html`, so `/settings` 404s today. Cutover adds a catch-all
registered last that returns the index for unknown paths while still 404-ing JSON under `/api/`.
Vite content-hashes its assets, so the version-stamping in that module is deleted in favour of
`no-cache` on the index and immutable caching on the asset directory.

Old hash bookmarks break, because paths replace `#playlist-prompt`. A pure mapper translates the
seven legacy hashes and rewrites the URL before the router is created, in Phase 1. Delete it one
release after cutover, not at cutover.

`Dockerfile` gains a Node build stage producing the SPA bundle, copied into the runtime image, which
currently ships no frontend at all.

## Open: Onboarding

Deferred and undesigned. It may require backend changes, so it is not purely SPA work and is not
sequenced as a phase.

The SPA shipping without a wizard is the fix. What any future design must satisfy:

Completion is derived, not stored. There is no `setup_complete` field and no endpoint that sets one,
so the predicate is computed from `GET /api/setup/status`. This changes when onboarding appears,
whether it can be dismissed, and what skipping means.

Exit is navigation, not an API call. Nothing remains to post.

It must never pre-empt a deep link, and must be re-enterable at a stable URL — the precise failure
the legacy wizard exhibits today.

The AI step must collect a model and a context window, and per-provider field sets differ. Ollama
can auto-detect the context window from `/api/ollama/model-info`; a custom endpoint cannot and must
ask.

Settings covers most of this in the meantime, which is why it is Phase 2 and why its acceptance
criteria are stricter than a like-for-like port.

TODO(onboarding): decide whether `/api/setup/validate-plex` and `/api/setup/validate-ai` are reworked
or retired in favour of `POST /api/config`, which already probes then saves and returns a renderable 422.

## Sources

- [React Router — Modes](https://reactrouter.com/start/modes#data) — read 2026-08-23, React Router 8.3.0
