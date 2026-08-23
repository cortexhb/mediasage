import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Heading } from './Heading.tsx'

describe('Heading', () => {
  it.each([1, 2, 3] as const)('renders level %i in the outline', (level) => {
    render(<Heading level={level}>Settings</Heading>)

    expect(
      screen.getByRole('heading', { level, name: 'Settings' }),
    ).toBeVisible()
  })

  it('carries the level as an attribute, which is what sizes it', () => {
    render(<Heading level={3}>Plex Connection</Heading>)

    expect(
      screen.getByRole('heading', { name: 'Plex Connection' }),
    ).toHaveAttribute('data-level', '3')
  })

  it('takes markup, not only a string', () => {
    render(
      <Heading level={1}>
        <a href="/">MediaSage</a>
      </Heading>,
    )

    expect(screen.getByRole('link', { name: 'MediaSage' })).toBeVisible()
  })
})
