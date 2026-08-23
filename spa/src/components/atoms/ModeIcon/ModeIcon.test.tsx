import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Mode } from '../../../libs/modes/modes.ts'
import { ModeIcon } from './ModeIcon.tsx'

const MODES: Mode[] = [
  'prompt_playlist',
  'seed_playlist',
  'album_recommendation',
]

/** The `<svg>`, by testid: it is decorative and carries no role or name.

    The last match, since one test draws all three into the same document. */
function drawn(mode: Mode, size = 24): HTMLElement {
  render(<ModeIcon mode={mode} size={size} />)
  const latest = screen.getAllByTestId('modeIcon').at(-1)
  if (!latest) throw new Error('ModeIcon drew nothing')
  return latest
}

describe('ModeIcon', () => {
  it.each(MODES)('draws something for %s', (mode) => {
    expect(drawn(mode).innerHTML).toMatch(/<(path|circle)/)
  })

  it.each(MODES)('hides %s from assistive technology', (mode) => {
    // Every call site labels itself; the glyph would be a worse name.
    expect(drawn(mode)).toHaveAttribute('aria-hidden', 'true')
  })

  it('draws each mode differently, so the three are distinguishable', () => {
    const shapes = MODES.map((mode) => drawn(mode).innerHTML)

    expect(new Set(shapes).size).toBe(MODES.length)
  })

  it('draws the album mode as circles, having no path to give it', () => {
    expect(drawn('album_recommendation').innerHTML).toContain('<circle')
  })

  it('sizes to what it is given', () => {
    const svg = drawn('prompt_playlist', 16)

    expect(svg).toHaveAttribute('width', '16')
    expect(svg).toHaveAttribute('height', '16')
  })

  it('keeps the viewBox fixed, so a size never crops the shape', () => {
    // The call sites draw 40 and 16 from the same 24-unit paths.
    expect(drawn('seed_playlist', 40)).toHaveAttribute('viewBox', '0 0 24 24')
  })

  it('inherits its colour from whatever places it', () => {
    expect(drawn('album_recommendation')).toHaveAttribute(
      'stroke',
      'currentColor',
    )
  })
})
