# MediaSage SPA

The React front end. Replaces `frontend/app.js` — 5488 lines of hand-synced DOM — with typed components, colocated
tests, and a design system extracted from the stylesheet that app already ships.

Development runs two processes: this on `:5173`, the API on `:5765`. Vite proxies
`/api` to it, so the browser stays same-origin, `fetch` paths stay relative, and production needs no CORS.

## Structure

```
src/
    api/                    the API boundary: generated types, client, SSE
    components/
        atoms/              no domain knowledge; a Button, an Icon, a Field
        molecules/          atoms composed; a SearchBox, a TrackRow
        organisms/          domain-aware; a PlaylistTable, a FilterPanel
    design-system/          tokens, mixins, sizes, layouts, theme
    hooks/
    libs/
    pages/
    routes.ts               every route in the app, in one place
```

## Naming

| Kind            | Directory    | Files            |
| --------------- | ------------ | ---------------- |
| Component, page | `PascalCase` | `PascalCase.tsx` |
| Hook, lib       | `camelCase`  | `camelCase.ts`   |

One thing per directory, and the directory's name repeats in the file. Never
`index.ts`: a tree of them makes every editor tab, stack frame, and grep hit read identically.

## Components

```
Button/
    Button.tsx
    Button.test.tsx
    Button.module.scss
```

As generic as the layer allows. An atom that knows what a playlist is belongs in
`organisms/`. If two organisms need the same piece, it moves down a layer rather than being copied.

**A component file contains no styles.** No `style={{...}}` prop, no styled-anything, no class strings assembled from
conditionals that encode visual rules. Styles live in the `.module.scss` beside it, and the component imports class
names from it.

## Pages

```
Settings/
    Settings.tsx
    Settings.test.tsx
    Settings.module.scss
```

Pages compose organisms, own their route, and are where data fetching is triggered. A page is the only place allowed to
know how a screen is assembled.

## Hooks and libs

```
useTrackSync/
    useTrackSync.ts
    useTrackSync.test.ts

formatDuration/
    formatDuration.ts
    formatDuration.test.ts
```

`libs/` is for pure functions. Anything touching React state or effects is a hook. Anything touching the network is
`api/`.

## API

`src/api/` is the only place that knows the backend exists.

- Types are **generated** from the FastAPI OpenAPI schema, never hand-written. A field renamed in `backend/` becomes a
  compile error here, not a blank panel.
- One fetch client, one SSE reader. Components never call `fetch`.
- Every request carries an `AbortSignal`.

## Routing

React Router in [data mode](https://reactrouter.com/start/modes#data): routes are plain objects, loaders fetch a page's
data before it renders, and actions mutate and revalidate.

`src/routes.ts` holds all of them. It stays `.ts` rather than `.tsx` because data mode references components
(`Component: Settings`) instead of rendering them, so no markup lives there. The router itself is built in `main.tsx`,
once, outside the React tree — a data router held in React state is recreated on every render and loses its history.

**A page does not fetch from inside an effect.** Its loader runs before it renders, so there is no loading flash and no
`useEffect` race to abort. What a loader returns is read with `useLoaderData`.

`createBrowserRouter`, not hash routing — real paths, not `#playlist-prompt`. This needs whatever serves the built app to
return `index.html` for unknown paths.

## Styles

The design system is a sibling of `components/` and governs the whole look. It is extracted from the legacy
`frontend/style.css`, which stays in that directory as the working reference until the port is finished, and is then
deleted.

```
design-system/
    global.scss     the only global stylesheet: tokens, reset, skip link
    _tokens.scss    the palette, scales and timings, as custom properties
    _sizes.scss     what a media query needs, which var() cannot supply
    _mixins.scss    breakpoints, touch targets, animation
```

`design-system/` is on Sass's load path, so a module at any depth reaches it by name:

```scss
@use 'mixins' as ds;

.button {
  padding: var(--spacing-sm) var(--spacing-md);

  @include ds.on-mobile {
    @include ds.touch-target;
  }
}
```

Tokens are read as `var(--accent)`, never by `@use`ing `tokens` — that file emits a `:root` rule, and a second import
emits a second one.

**A style enters the SPA only when a component actively uses it.** Nothing is copied across wholesale. The SPA carries
no dead CSS. That applies to the design system too: a breakpoint or an animation with one caller belongs in that
caller's module, not here.

Component styles are CSS Modules (`.module.scss`), so scoping is automatic. BEM notation is still used _inside_ a module
to express element and modifier relationships legibly — not to prevent collisions, which the module already does.

Class names are camelCase blocks with BEM parts — `trackRow`, `trackRow__title`, `trackRow--active` — because CSS
Modules exposes them as JavaScript properties, and `styles.trackRow__title` resolves where a kebab-case name needs
bracket access. Mixins and Sass variables are kebab-case: nothing reads those from JavaScript, so they follow Sass.

**Every `className` is one static lookup.** A component never joins class strings, and no helper exists to do it.
Where a style depends on state, the stylesheet selects on the attribute that state is already in —
`.nav__trigger[aria-expanded='true']`, `.nav__item[aria-current]` — rather than the component picking a modifier. A
variant with no attribute to hang on is usually a missing one; declarations shared between two blocks go in a `%placeholder`.

Shared animations are mixins rather than global keyframes. CSS Modules hashes a keyframe name per file, so sharing one
would mean `animation-name: :global(spin)` — an escape hatch the module system cannot check. Including the mixin gives
each module its own hashed copy instead.

Only two things are global: the design-system entry point and the reset. Both live in `global.scss`.

## Testing

Vitest, React Testing Library, `user-event`, `jest-dom`. Network is mocked at the boundary, not by stubbing `fetch` per
test.

Two projects. **`unit`** runs under jsdom and is where a test goes unless there is a reason it cannot. **`dom`** runs in
real Chromium through Playwright, matches `*.browser.test.tsx`, and exists only for behaviour a DOM emulator does not
implement.

That bar is high on purpose — browser tests are slower and need `npx playwright install chromium` before they run.
Today one thing clears it: native `<dialog>`. jsdom 30.0.1 declares `HTMLDialogElement` but implements none of `show`,
`showModal` or `close`; happy-dom's `showModal` is `setAttribute('open', '')` with no focus management and no inertness.
Shimming either would mean the assertions described the shim rather than the platform, so `atoms/Overlay` is verified
where the behaviour is real.

Browser tests take input from `vitest/browser`, not `@testing-library/user-event`. Escape-to-close and the focus trap
are driven by the browser and ignore synthesised events — a synthetic Escape leaves a native dialog open. Queries stay
RTL's, so the role-and-label conventions below are the same in both projects.

Test wiring lives at the project root, not in `src/` — `vitest.config.ts` and `vitest.setup.ts`. The setup file owns the
mock server; tests import it as `@test`, so a component four directories deep does not reach it through a chain of `../`:

```ts
import { server } from '@test'

server.use(
  http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
)
```

An unhandled request fails the test rather than warning.

**Every component is tested before it is called done.** Happy path, every edge case, every failure mode. No stone
unturned.

No rubber-stamp assertions. Concretely, a test is not done if it:

- asserts something that cannot fail (`expect(x).toBeDefined()` on a literal)
- is a snapshot and nothing else
- puts a `data-testid` on an interactive control, or reaches for one where a role, label, or visible text would work
- asserts on internal state, props, or a hook's return rather than what a user sees
- uses `fireEvent` where `user-event` models the real interaction
- covers only the success path of something that can fail

A component that can show a loading, empty, error, and populated state has at least four tests.

A failing accessible query is information — usually that a control is unlabelled or is a `div`
pretending to be a button — so a `data-testid` on one silences a free accessibility check. Testids
are still legitimate for scoping a query to a layout region with no honest role, and for content the
app does not control, where a track title can be anything including empty. Each carries a one-line
reason at the usage site.

## Types

`strict` is on, along with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`,
`noImplicitOverride`, and `noImplicitReturns`. ESLint runs `strictTypeChecked`
against the compiler, so type-aware rules are live.

Errors are never swallowed:

- no floating promises — `void promise` is rejected too; rejection is handled
- no empty `catch`
- only `Error` is thrown
- no `!` non-null assertion
- no `any`
- every union `switch` is exhaustive

A `catch` that cannot do anything useful re-throws. It does not log and continue.

## Commands

```bash
npm run dev            # :5173, expects the API on :5765
npm run build          # tsc -b && vite build
npm run test           # vitest, watch mode
npm run test:run       # vitest, once
npm run test:coverage  # vitest with v8 coverage
npm run lint           # eslint --fix
npm run lint:css       # stylelint --fix
npm run format         # prettier --write
npm run gen:api        # regenerate src/api/generated from the live schema
```

**The fixing form is the default.** `lint`, `lint:css`, and `format` all write.
Nobody hand-applies a change a tool can apply, and nobody reads a diff full of
quote styles and blank lines.

Each has a read-only twin for CI and for checking a tree you do not want touched:

```bash
npm run lint:check
npm run lint:css:check
npm run format:check
```

## Definition of done

1. Types check, no `any`, no `!`.
2. `lint:check`, `lint:css:check`, `format:check` clean — with nothing left
   that the fixing form would have changed.
3. Tests cover happy path, edges, and failure modes — and would fail if the behaviour broke.
4. No styles in the component file, no dead CSS carried over.
5. The SPA route is the only implementation of the behaviour. `frontend/` is never edited during
   the port — it stays as the working reference and is deleted whole at cutover.
