/**
 * The glyph for one of the three things the app makes.
 *
 * Copied from `frontend/index.html:186` (the home cards, at 24px) and
 * `frontend/app.js:720` (the history feed, at 16px), which drew the same three
 * Lucide shapes twice. One component with a `size` serves both.
 *
 * No stylesheet: it inherits `currentColor` from whatever places it.
 */
import type { Mode } from '../../../libs/modes/modes.ts'

/** Every shape is centred, so a circle is described by its radius alone. */
interface Shape {
  readonly paths: readonly string[]
  readonly radii: readonly number[]
}

const SHAPES: Record<Mode, Shape> = {
  prompt_playlist: {
    paths: [
      'M12 18V5',
      'M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4',
      'M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5',
      'M17.997 5.125a4 4 0 0 1 2.526 5.77',
      'M18 18a4 4 0 0 0 2-7.464',
      'M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517',
      'M6 18a4 4 0 0 1-2-7.464',
      'M6.003 5.125a4 4 0 0 0-2.526 5.77',
    ],
    radii: [],
  },
  seed_playlist: {
    paths: [
      'M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3',
      'M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4',
      'M5 21h14',
    ],
    radii: [],
  },
  album_recommendation: { paths: [], radii: [10, 2] },
}

export interface ModeIconProps {
  readonly mode: Mode
  /** Pixels, square. The two call sites use 24 and 16. */
  readonly size: number
}

export function ModeIcon({ mode, size }: ModeIconProps) {
  const shape = SHAPES[mode]

  return (
    <svg
      // Decorative: no role, no name, so no accessible handle.
      data-testid="modeIcon"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {shape.paths.map((path) => (
        <path key={path} d={path} />
      ))}
      {shape.radii.map((radius) => (
        <circle key={radius} cx="12" cy="12" r={radius} />
      ))}
    </svg>
  )
}
