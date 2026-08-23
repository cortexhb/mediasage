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

The design system is a sibling of `components/` and governs the whole look: tokens, mixins, codified sizes, layouts,
theme. It is extracted from the legacy
`frontend/style.css`, which stays in that directory as the working reference until the port is finished, and is then
deleted.

**A style enters the SPA only when a component actively uses it.** Nothing is copied across wholesale. The SPA carries
no dead CSS.

Component styles are CSS Modules (`.module.scss`), so scoping is automatic. BEM notation is still used _inside_ a module
to express element and modifier relationships legibly — not to prevent collisions, which the module already does.

Only two things are global: the design-system entry point and the reset.

## Testing

Vitest, React Testing Library, `user-event`, `jest-dom`. Network is mocked at the boundary, not by stubbing `fetch` per
test.

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
- reaches for a `data-testid` where a role, label, or visible text would work
- asserts on internal state, props, or a hook's return rather than what a user sees
- uses `fireEvent` where `user-event` models the real interaction
- covers only the success path of something that can fail

A component that can show a loading, empty, error, and populated state has at least four tests.

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
5. The legacy behaviour it replaces is gone from `frontend/app.js`, not duplicated.
